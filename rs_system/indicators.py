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
    stock_price_data: pd.DataFrame = None,
    market_price_data: pd.DataFrame = None,
    rs_line_series: pd.Series = None
) -> bool:
    """
    检查 RS Line 是否达到 252 日（52周）新高
    
    Args:
        stock_price_data: 股票价格数据（如果 rs_line_series 为 None 则必需）
        market_price_data: 市场基准价格数据（如果 rs_line_series 为 None 则必需）
        rs_line_series: RS Line 时间序列（如果提供则直接使用，避免重复计算）
        
    Returns:
        True 如果 RS Line 当前处于 252 日新高，否则 False
    """
    try:
        # 如果提供了 rs_line_series，直接使用
        if rs_line_series is not None and len(rs_line_series) > 0:
            rs_line = rs_line_series.sort_index()
        else:
            # 否则从价格数据计算
            if stock_price_data is None or market_price_data is None:
                return False
            
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
            if len(common_dates) < 252:  # 需要至少252个交易日（52周）
                return False
            
            stock_prices = stock_prices.loc[common_dates].sort_index()
            market_prices = market_prices.loc[common_dates].sort_index()
            
            # 计算 RS Line
            rs_line = stock_prices / market_prices
        
        # 获取最近252个交易日的数据
        rs_line_252d = rs_line.tail(252)
        
        if len(rs_line_252d) == 0:
            return False
        
        # 当前 RS Line 值
        current_rs = rs_line_252d.iloc[-1]
        
        # 252日最高值（不包括当前值）
        max_rs_252d = rs_line_252d.iloc[:-1].max()
        
        # 严格的新高检测：当前值必须严格大于历史最高值才算新高
        # 如果当前值等于历史最高值，说明是"等于历史高点"而不是"突破新高"
        is_new_high = current_rs > max_rs_252d
        
        return is_new_high
        
    except Exception as e:
        logger.debug(f"检查 RS Line 252日新高失败: {e}")
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


def calculate_trend_strength_score(price_data: pd.DataFrame) -> Optional[float]:
    """
    计算趋势强度分数（SCTR风格）
    基于：
    1. 股价 vs SMA200 的加权平均（40%）
    2. 6个月变化率（30%）
    3. RSI（30%）
    
    Args:
        price_data: 包含价格数据的 DataFrame
        
    Returns:
        趋势强度分数（0-100），如果计算失败返回 None
    """
    try:
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        if price_col not in price_data.columns:
            return None
        
        prices = price_data[price_col].dropna()
        
        if len(prices) < 200:
            return None
        
        # 1. 计算股价 vs SMA200 的百分比（40%权重）
        sma200 = prices.rolling(window=200).mean().iloc[-1]
        current_price = prices.iloc[-1]
        
        if pd.isna(sma200) or pd.isna(current_price) or sma200 == 0:
            return None
        
        price_vs_sma200_pct = ((current_price - sma200) / sma200) * 100
        # 归一化到 0-100（假设 -50% 到 +50% 的范围）
        score1 = max(0, min(100, 50 + price_vs_sma200_pct))
        
        # 2. 计算6个月变化率（30%权重）
        if len(prices) < 126:  # 6个月约126个交易日
            return None
        
        price_6m_ago = prices.iloc[-126]
        if pd.isna(price_6m_ago) or price_6m_ago == 0:
            return None
        
        change_6m_pct = ((current_price - price_6m_ago) / price_6m_ago) * 100
        # 归一化到 0-100（假设 -50% 到 +50% 的范围）
        score2 = max(0, min(100, 50 + change_6m_pct))
        
        # 3. 计算RSI（30%权重）
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        if len(gain) == 0 or len(loss) == 0:
            return None
        
        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0
        rsi = 100 - (100 / (1 + rs)) if not pd.isna(rs) else 50
        score3 = rsi  # RSI 本身就在 0-100 范围内
        
        # 加权平均
        trend_score = (score1 * 0.40 + score2 * 0.30 + score3 * 0.30)
        
        return round(trend_score, 2)
        
    except Exception as e:
        logger.debug(f"计算趋势强度分数失败: {e}")
        return None


def calculate_volatility_contraction(price_data: pd.DataFrame, days: int = 10) -> Optional[float]:
    """
    计算波动率收缩：10日最高价与10日最低价之间的距离（百分比）
    
    Args:
        price_data: 包含价格数据的 DataFrame
        days: 计算天数（默认10天）
        
    Returns:
        波动率收缩百分比（最高价与最低价之间的距离），如果计算失败返回 None
    """
    try:
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        if price_col not in price_data.columns:
            return None
        
        prices = price_data[price_col].dropna()
        
        if len(prices) < days:
            return None
        
        # 获取最近N天的最高价和最低价
        recent_prices = prices.tail(days)
        high_10d = recent_prices.max()
        low_10d = recent_prices.min()
        
        if pd.isna(high_10d) or pd.isna(low_10d) or low_10d == 0:
            return None
        
        # 计算距离百分比
        volatility_pct = ((high_10d - low_10d) / low_10d) * 100
        
        return round(volatility_pct, 2)
        
    except Exception as e:
        logger.debug(f"计算波动率收缩失败: {e}")
        return None


def is_stage2_trend(price_data: pd.DataFrame) -> bool:
    """
    判断股票是否处于第二阶段趋势（强化版）：
    - Price > SMA50 > SMA150 > SMA200
    - SMA50 与 SMA200 至少相差 15%（趋势足够陡峭）
    - 最近一段时间（默认 6 个月）最大回撤不超过约 30%
    
    Args:
        price_data: 包含价格数据的 DataFrame
        
    Returns:
        True 如果符合第二阶段趋势，否则 False
    """
    try:
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        if price_col not in price_data.columns:
            return False
        
        prices = price_data[price_col].dropna()
        
        if len(prices) < 200:
            return False
        
        # 计算移动平均线
        sma50 = prices.rolling(window=50).mean().iloc[-1]
        sma150 = prices.rolling(window=150).mean().iloc[-1]
        sma200 = prices.rolling(window=200).mean().iloc[-1]
        current_price = prices.iloc[-1]
        
        if pd.isna(sma50) or pd.isna(sma150) or pd.isna(sma200) or pd.isna(current_price):
            return False
        
        # 基本第二阶段趋势条件
        basic_stage2 = (current_price > sma50 and 
                        sma50 > sma150 and 
                        sma150 > sma200)
        if not basic_stage2:
            return False
        
        # 强化条件1：SMA50 与 SMA200 至少相差 15%
        if sma200 == 0 or pd.isna(sma200):
            return False
        sma50_vs_200_pct = (sma50 - sma200) / sma200 * 100
        if sma50_vs_200_pct < 15.0:
            return False
        
        # 强化条件2：最近约 6 个月（126 个交易日）最大回撤不超过 30%
        lookback_days = 126
        if len(prices) >= lookback_days:
            recent_prices = prices.tail(lookback_days)
        else:
            recent_prices = prices
        
        rolling_max = recent_prices.cummax()
        drawdown_series = (recent_prices / rolling_max - 1.0) * 100  # 负数表示回撤
        max_drawdown = drawdown_series.min()  # 最严重的回撤（最小的负数）
        
        if pd.isna(max_drawdown):
            return False
        
        # 要求最大回撤不小于 -30%（例如 -25% / -20% 可以接受）
        if max_drawdown < -30.0:
            return False
        
        return True
        
    except Exception as e:
        logger.debug(f"判断第二阶段趋势失败: {e}")
        return False


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


def calculate_avg_dollar_volume(price_data: pd.DataFrame, days: int = 50) -> Optional[float]:
    """
    计算最近 N 日平均成交额（美元），用于流动性过滤。
    
    Args:
        price_data: 包含价格和成交量的 DataFrame（需要 'Volume' 和价格列）
        days: 计算天数（默认 50 日）
    
    Returns:
        平均每日成交额（美元），如果计算失败返回 None
    """
    try:
        if 'Volume' not in price_data.columns:
            return None
        
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        if price_col not in price_data.columns:
            return None
        
        df = price_data[[price_col, 'Volume']].dropna()
        if len(df) < days:
            return None
        
        recent = df.tail(days)
        dollar_volume = recent[price_col] * recent['Volume']
        avg_dollar_volume = float(dollar_volume.mean())
        return avg_dollar_volume
    except Exception as e:
        logger.debug(f"计算平均成交额失败: {e}")
        return None


def calculate_atr_pct(price_data: pd.DataFrame, period: int = 14) -> Optional[float]:
    """
    计算 ATR 占当前价格的百分比（粗略日波动率），用于风险过滤。
    
    Args:
        price_data: 包含 High/Low/Close 的 DataFrame
        period: ATR 计算周期（默认 14 日）
    
    Returns:
        ATR 百分比（ATR / Close * 100），如果计算失败返回 None
    """
    try:
        required_cols = {'High', 'Low', 'Close'}
        if not required_cols.issubset(set(price_data.columns)):
            return None
        
        df = price_data[['High', 'Low', 'Close']].dropna()
        if len(df) < period + 1:
            return None
        
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean().iloc[-1]
        current_price = close.iloc[-1]
        
        if pd.isna(atr) or pd.isna(current_price) or current_price == 0:
            return None
        
        atr_pct = float(atr / current_price * 100.0)
        return round(atr_pct, 2)
    except Exception as e:
        logger.debug(f"计算 ATR 百分比失败: {e}")
        return None


def calculate_price_52w_distance(price_data: pd.DataFrame) -> Optional[float]:
    """
    计算当前价格距离 52 周（252 日）最高价的距离（百分比）。
    
    正值表示“距离新高还有多少百分比”，用于筛选接近新高的股票。
    例如：distance = 3.0 表示当前价格比 52 周高点低 3%。
    """
    try:
        price_col = 'Adj Close' if 'Adj Close' in price_data.columns else 'Close'
        if price_col not in price_data.columns:
            return None
        
        prices = price_data[price_col].dropna()
        if len(prices) < 20:
            return None
        
        recent_252 = prices.tail(252)
        high_52w = recent_252.max()
        current_price = prices.iloc[-1]
        
        if pd.isna(high_52w) or pd.isna(current_price) or high_52w == 0:
            return None
        
        distance_pct = (high_52w - current_price) / high_52w * 100.0
        return round(distance_pct, 2)
    except Exception as e:
        logger.debug(f"计算价格距离52周新高失败: {e}")
        return None

