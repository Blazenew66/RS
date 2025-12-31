"""
RS 计算模块：计算股票的 Relative Strength 原始值
基于 IBD (Investor's Business Daily) 的 RS Rating 方法
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import logging
from rs_system.config import (
    LOOKBACK_PERIOD,
    MARKET_BENCHMARK,
    RS_PERIOD_3M,
    RS_PERIOD_6M,
    RS_PERIOD_9M,
    RS_PERIOD_12M,
    RS_WEIGHTS
)

logger = logging.getLogger(__name__)


class RSCalculator:
    """IBD 风格的 RS 计算器"""
    
    def __init__(self, lookback_period: int = LOOKBACK_PERIOD):
        """
        初始化 RS 计算器
        
        Args:
            lookback_period: 回看周期（交易日数），默认 252
        """
        self.lookback_period = lookback_period
        self.market_benchmark = MARKET_BENCHMARK
    
    def calculate_period_return(
        self, 
        price_series: pd.Series, 
        period_days: int
    ) -> Optional[float]:
        """
        计算指定周期的收益率
        
        Args:
            price_series: 收盘价序列（按日期排序，最新的在最后）
            period_days: 回看天数
            
        Returns:
            收益率（百分比），如果计算失败返回 None
        """
        if price_series is None or len(price_series) < period_days + 1:
            return None
        
        try:
            # 确保数据按日期排序（最新的在最后）
            price_series = price_series.sort_index()
            
            # 获取当前价格和 N 天前的价格
            current_price = price_series.iloc[-1]
            past_price = price_series.iloc[-(period_days + 1)]
            
            # 处理异常值
            if pd.isna(current_price) or pd.isna(past_price):
                return None
            
            if past_price <= 0:
                logger.warning(f"历史价格为 0 或负数: {past_price}")
                return None
            
            # 计算收益率百分比
            return (current_price / past_price - 1) * 100
            
        except Exception as e:
            logger.debug(f"计算 {period_days} 天收益率失败: {str(e)}")
            return None
    
    def calculate_weighted_rs(
        self,
        stock_returns: Dict[int, float],
        market_returns: Dict[int, float]
    ) -> Optional[float]:
        """
        计算加权相对强度（相对于市场基准）
        
        公式：加权 RS = Σ((股票收益率_i - 市场收益率_i) × 权重_i)
        
        Args:
            stock_returns: Dict[周期天数, 股票收益率]
            market_returns: Dict[周期天数, 市场收益率]
            
        Returns:
            加权 RS 值，如果计算失败返回 None
        """
        if not stock_returns or not market_returns:
            return None
        
        weighted_rs = 0.0
        total_weight = 0.0
        
        for period, weight in RS_WEIGHTS.items():
            stock_return = stock_returns.get(period)
            market_return = market_returns.get(period)
            
            if stock_return is not None and market_return is not None:
                # 计算相对强度：股票表现 - 市场表现
                relative_strength = stock_return - market_return
                weighted_rs += relative_strength * weight
                total_weight += weight
        
        if total_weight == 0:
            return None
        
        # 归一化（如果权重总和不是1.0）
        if total_weight != 1.0:
            weighted_rs = weighted_rs / total_weight
        
        return weighted_rs
    
    def calculate_rs_raw(
        self,
        stock_price_series: pd.Series,
        market_price_series: pd.Series
    ) -> Optional[Tuple[float, float]]:
        """
        计算单只股票的 IBD 风格 RS 原始值和 RS Line
        
        Args:
            stock_price_series: 股票收盘价序列（按日期排序，最新的在最后）
            market_price_series: 市场基准（SPY）收盘价序列
            
        Returns:
            (加权 RS 值, RS Line 当前值) 元组，如果计算失败返回 None
            RS Line = 当前股价 / 当前市场基准价格
        """
        if stock_price_series is None or market_price_series is None:
            return None
        
        try:
            # 确保数据按日期排序
            stock_prices = stock_price_series.sort_index()
            market_prices = market_price_series.sort_index()
            
            # 对齐日期索引（只保留两个序列都有的日期）
            common_dates = stock_prices.index.intersection(market_prices.index)
            if len(common_dates) < max(RS_PERIOD_12M + 1, 10):
                logger.warning(f"数据日期对齐后不足，只有 {len(common_dates)} 个交易日")
                return None
            
            stock_prices = stock_prices.loc[common_dates].sort_index()
            market_prices = market_prices.loc[common_dates].sort_index()
            
            # 使用 Adjusted Close（如果存在）
            if 'Adj Close' in stock_price_series.index.names or hasattr(stock_prices, 'name'):
                # 如果已经是 Series，检查是否有 Adj Close
                pass
            # 注意：这里假设传入的已经是正确的价格序列（Adj Close 或 Close）
            
            # 计算各周期的股票收益率
            stock_returns = {}
            for period in [RS_PERIOD_3M, RS_PERIOD_6M, RS_PERIOD_9M, RS_PERIOD_12M]:
                return_val = self.calculate_period_return(stock_prices, period)
                if return_val is not None:
                    stock_returns[period] = return_val
            
            # 计算各周期的市场收益率
            market_returns = {}
            for period in [RS_PERIOD_3M, RS_PERIOD_6M, RS_PERIOD_9M, RS_PERIOD_12M]:
                return_val = self.calculate_period_return(market_prices, period)
                if return_val is not None:
                    market_returns[period] = return_val
            
            # 计算加权 RS
            weighted_rs = self.calculate_weighted_rs(stock_returns, market_returns)
            if weighted_rs is None:
                return None
            
            # 计算 RS Line（当前股价 / 当前市场基准价格）
            current_stock_price = stock_prices.iloc[-1]
            current_market_price = market_prices.iloc[-1]
            
            if pd.isna(current_stock_price) or pd.isna(current_market_price):
                return None
            
            if current_market_price <= 0:
                logger.warning(f"市场基准价格为 0 或负数: {current_market_price}")
                return None
            
            rs_line = current_stock_price / current_market_price
            
            return (weighted_rs, rs_line)
            
        except Exception as e:
            logger.error(f"计算 RS 失败: {str(e)}")
            return None
    
    def calculate_rs_for_all(
        self,
        ticker_data: Dict[str, pd.DataFrame],
        market_data: pd.DataFrame
    ) -> Dict[str, Tuple[float, float]]:
        """
        批量计算所有股票的 IBD 风格 RS 原始值和 RS Line
        
        Args:
            ticker_data: Dict[ticker, DataFrame]，包含每只股票的历史数据
            market_data: 市场基准（SPY）的 DataFrame
            
        Returns:
            Dict[ticker, (加权 RS 值, RS Line 值)]
        """
        rs_results = {}
        
        logger.info(f"开始计算 {len(ticker_data)} 只股票的 IBD RS 值...")
        
        # 准备市场基准数据
        if 'Close' not in market_data.columns:
            logger.error("市场基准数据缺少 Close 列")
            return rs_results
        
        # 使用 Date 作为索引（如果存在）
        if 'Date' in market_data.columns:
            market_df = market_data.set_index('Date')
        else:
            market_df = market_data.copy()
        
        market_price_series = market_df['Close']
        
        # 计算每只股票的 RS
        for ticker, df in ticker_data.items():
            if 'Close' not in df.columns:
                logger.warning(f"{ticker}: 缺少 Close 列，跳过")
                continue
            
            # 使用 Date 作为索引（如果存在）
            if 'Date' in df.columns:
                df = df.set_index('Date')
            
            stock_price_series = df['Close']
            
            result = self.calculate_rs_raw(stock_price_series, market_price_series)
            
            if result is not None:
                rs_results[ticker] = result
            else:
                logger.warning(f"{ticker}: RS 计算失败，跳过")
        
        logger.info(f"RS 计算完成，成功计算 {len(rs_results)}/{len(ticker_data)} 只股票")
        return rs_results
    
    def calculate_multi_period_rs(
        self,
        stock_price_series: pd.Series,
        market_price_series: pd.Series,
        periods: Dict[int, float] = None
    ) -> Optional[float]:
        """
        计算多周期加权 RS（使用自定义权重）
        
        Args:
            stock_price_series: 股票收盘价序列
            market_price_series: 市场基准收盘价序列
            periods: Dict[周期天数, 权重]，如果为 None 则使用默认权重
            
        Returns:
            加权 RS 值
        """
        if periods is None:
            # 使用默认权重
            result = self.calculate_rs_raw(stock_price_series, market_price_series)
            if result:
                return result[0]  # 返回加权 RS 值
            return None
        
        # 使用自定义权重计算
        stock_returns = {}
        market_returns = {}
        
        for period in periods.keys():
            stock_return = self.calculate_period_return(stock_price_series, period)
            market_return = self.calculate_period_return(market_price_series, period)
            
            if stock_return is not None:
                stock_returns[period] = stock_return
            if market_return is not None:
                market_returns[period] = market_return
        
        # 使用自定义权重
        weighted_rs = 0.0
        total_weight = 0.0
        
        for period, weight in periods.items():
            stock_return = stock_returns.get(period)
            market_return = market_returns.get(period)
            
            if stock_return is not None and market_return is not None:
                relative_strength = stock_return - market_return
                weighted_rs += relative_strength * weight
                total_weight += weight
        
        if total_weight == 0:
            return None
        
        return weighted_rs / total_weight if total_weight != 0 else None
