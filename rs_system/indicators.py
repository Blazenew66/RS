"""
技术指标计算模块：SMA50、RS Trend、Volume Surge
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def calculate_sma50_distance(price_data: pd.DataFrame) -> Optional[float]:
    """
    计算当前价格相对于 50 日移动平均线的距离（百分比）
    
    Args:
        price_data: 包含价格数据的 DataFrame（必须有 'Close' 或 'Adj Close' 列）
        
    Returns:
        距离百分比（正数表示在均线上方，负数表示在均线下方），如果计算失败返回 None
    """
    try:
        # 使用 Adjusted Close（如果存在）
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        
        if price_col not in price_data.columns:
            return None
        
        prices = price_data[price_col].dropna()
        
        if len(prices) < 50:
            return None
        
        # 计算 50 日移动平均线
        sma50 = prices.rolling(window=50).mean().iloc[-1]
        current_price = prices.iloc[-1]
        
        if pd.isna(sma50) or pd.isna(current_price) or sma50 == 0:
            return None
        
        # 计算距离百分比
        distance_pct = ((current_price - sma50) / sma50) * 100
        
        return distance_pct
        
    except Exception as e:
        logger.debug(f"计算 SMA50 距离失败: {e}")
        return None


def calculate_rs_trend(
    stock_price_data: pd.DataFrame,
    market_price_data: pd.DataFrame,
    days: int = 20
) -> Tuple[Optional[float], str]:
    """
    计算 RS Line 的趋势（斜率）
    
    Args:
        stock_price_data: 股票价格数据
        market_price_data: 市场基准价格数据
        days: 计算趋势的天数（默认 20 天）
        
    Returns:
        (斜率值, 趋势箭头) 元组
        趋势箭头: ⬆️ (上升), → (横盘), ⬇️ (下降)
    """
    try:
        # 对齐日期
        if 'Date' in stock_price_data.columns:
            stock_price_data = stock_price_data.set_index('Date')
        if 'Date' in market_price_data.columns:
            market_price_data = market_price_data.set_index('Date')
        
        # 使用 Adjusted Close
        stock_col = 'Adj Close' if 'Adj Close' in stock_price_data.columns else 'Close'
        market_col = 'Adj Close' if 'Adj Close' in market_price_data.columns else 'Close'
        
        stock_prices = stock_price_data[stock_col].dropna()
        market_prices = market_price_data[market_col].dropna()
        
        # 对齐日期
        common_dates = stock_prices.index.intersection(market_prices.index)
        if len(common_dates) < days:
            return None, "→"
        
        stock_prices = stock_prices.loc[common_dates].sort_index()
        market_prices = market_prices.loc[common_dates].sort_index()
        
        # 计算 RS Line（最后 N 天）
        recent_stock = stock_prices.tail(days)
        recent_market = market_prices.tail(days)
        
        rs_line = recent_stock / recent_market
        
        if len(rs_line) < 2:
            return None, "→"
        
        # 计算斜率（线性回归）
        x = np.arange(len(rs_line))
        y = rs_line.values
        
        # 简单线性回归
        slope = np.polyfit(x, y, 1)[0]
        
        # 转换为百分比变化（相对于起始值）
        if rs_line.iloc[0] != 0:
            slope_pct = (slope / rs_line.iloc[0]) * 100
        else:
            slope_pct = 0
        
        # 确定趋势箭头
        if slope_pct > 0.5:
            arrow = "⬆️"
        elif slope_pct < -0.5:
            arrow = "⬇️"
        else:
            arrow = "→"
        
        return slope_pct, arrow
        
    except Exception as e:
        logger.debug(f"计算 RS Trend 失败: {e}")
        return None, "→"


def calculate_volume_surge(price_data: pd.DataFrame) -> Optional[float]:
    """
    计算成交量激增：当前成交量 / 50 日平均成交量
    
    Args:
        price_data: 包含成交量数据的 DataFrame（必须有 'Volume' 列）
        
    Returns:
        成交量比率（1.0 表示正常，>1.0 表示放量，<1.0 表示缩量），如果计算失败返回 None
    """
    try:
        if 'Volume' not in price_data.columns:
            return None
        
        volumes = price_data['Volume'].dropna()
        
        if len(volumes) < 50:
            return None
        
        current_volume = volumes.iloc[-1]
        avg_volume_50 = volumes.tail(50).mean()
        
        if pd.isna(current_volume) or pd.isna(avg_volume_50) or avg_volume_50 == 0:
            return None
        
        volume_ratio = current_volume / avg_volume_50
        
        return volume_ratio
        
    except Exception as e:
        logger.debug(f"计算 Volume Surge 失败: {e}")
        return None


def check_rs_line_52w_high(
    stock_price_data: pd.DataFrame,
    market_price_data: pd.DataFrame
) -> bool:
    """
    检查 RS Line 是否达到 52 周新高
    
    Args:
        stock_price_data: 股票价格数据
        market_price_data: 市场基准价格数据
        
    Returns:
        True 如果 RS Line 当前处于 52 周新高，否则 False
    """
    try:
        # 对齐日期
        if 'Date' in stock_price_data.columns:
            stock_price_data = stock_price_data.set_index('Date')
        if 'Date' in market_price_data.columns:
            market_price_data = market_price_data.set_index('Date')
        
        # 使用 Adjusted Close
        stock_col = 'Adj Close' if 'Adj Close' in stock_price_data.columns else 'Close'
        market_col = 'Adj Close' if 'Adj Close' in market_price_data.columns else 'Close'
        
        stock_prices = stock_price_data[stock_col].dropna()
        market_prices = market_price_data[market_col].dropna()
        
        # 对齐日期
        common_dates = stock_prices.index.intersection(market_prices.index)
        if len(common_dates) < 252:  # 需要至少52周数据
            return False
        
        stock_prices = stock_prices.loc[common_dates].sort_index()
        market_prices = market_prices.loc[common_dates].sort_index()
        
        # 计算 RS Line
        rs_line = stock_prices / market_prices
        
        # 获取最近52周的数据
        rs_line_52w = rs_line.tail(252)
        
        if len(rs_line_52w) == 0:
            return False
        
        # 当前 RS Line 值
        current_rs = rs_line_52w.iloc[-1]
        
        # 52周最高值（不包括当前值）
        max_rs_52w = rs_line_52w.iloc[:-1].max()
        
        # 如果当前值 >= 52周最高值，说明达到新高
        is_new_high = current_rs >= max_rs_52w
        
        return is_new_high
        
    except Exception as e:
        logger.debug(f"检查 RS Line 52周新高失败: {e}")
        return False


def calculate_sma200(price_data: pd.DataFrame) -> Optional[float]:
    """
    计算 200 日移动平均线
    
    Args:
        price_data: 包含价格数据的 DataFrame
        
    Returns:
        200 日移动平均线值，如果计算失败返回 None
    """
    try:
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        
        if price_col not in price_data.columns:
            return None
        
        prices = price_data[price_col].dropna()
        
        if len(prices) < 200:
            return None
        
        sma200 = prices.rolling(window=200).mean().iloc[-1]
        
        return sma200 if not pd.isna(sma200) else None
        
    except Exception as e:
        logger.debug(f"计算 SMA200 失败: {e}")
        return None


def calculate_sma50(price_data: pd.DataFrame) -> Optional[float]:
    """
    计算 50 日移动平均线
    
    Args:
        price_data: 包含价格数据的 DataFrame
        
    Returns:
        50 日移动平均线值，如果计算失败返回 None
    """
    try:
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        
        if price_col not in price_data.columns:
            return None
        
        prices = price_data[price_col].dropna()
        
        if len(prices) < 50:
            return None
        
        sma50 = prices.rolling(window=50).mean().iloc[-1]
        
        return sma50 if not pd.isna(sma50) else None
        
    except Exception as e:
        logger.debug(f"计算 SMA50 失败: {e}")
        return None


def is_leader_stock(
    price_data: pd.DataFrame,
    rs_score: float
) -> bool:
    """
    判断股票是否符合"领导者"条件：
    - Price > 50-day SMA
    - 50-day SMA > 200-day SMA
    - RS Rating > 80
    
    Args:
        price_data: 价格数据
        rs_score: RS Rating 分数
        
    Returns:
        True 如果符合所有条件，否则 False
    """
    try:
        # 检查 RS Rating
        if rs_score <= 80:
            return False
        
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        if price_col not in price_data.columns:
            return False
        
        prices = price_data[price_col].dropna()
        
        if len(prices) < 200:
            return False
        
        # 计算移动平均线
        sma50 = prices.rolling(window=50).mean().iloc[-1]
        sma200 = prices.rolling(window=200).mean().iloc[-1]
        current_price = prices.iloc[-1]
        
        if pd.isna(sma50) or pd.isna(sma200) or pd.isna(current_price):
            return False
        
        # 检查条件
        price_above_sma50 = current_price > sma50
        sma50_above_sma200 = sma50 > sma200
        
        return price_above_sma50 and sma50_above_sma200
        
    except Exception as e:
        logger.debug(f"判断领导者股票失败: {e}")
        return False

