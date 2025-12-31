"""
RS 历史数据计算模块：计算1周前的 RS Rating
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from scipy.stats import percentileofscore
from rs_system.data_fetcher import DataFetcher
from rs_system.rs_calculator import RSCalculator
from rs_system.config import MARKET_BENCHMARK

logger = logging.getLogger(__name__)


def calculate_rs_1w_ago(
    ticker: str,
    price_data: pd.DataFrame,
    market_rs_distribution: list,
    market_benchmark: pd.DataFrame
) -> Optional[int]:
    """
    计算1周前（约5个交易日）的 RS Rating
    
    Args:
        ticker: 股票代码
        price_data: 当前价格数据
        market_rs_distribution: 市场 RS 分布（用于百分位排名）
        market_benchmark: 市场基准数据
        
    Returns:
        1周前的 RS Rating（1-99），如果计算失败返回 None
    """
    try:
        # 需要至少5个交易日前的数据
        if len(price_data) < 10:
            return None
        
        # 准备数据（使用5个交易日前）
        days_back = 5
        
        if 'Date' in price_data.columns:
            df = price_data.set_index('Date')
        else:
            df = price_data.copy()
        
        # 获取5个交易日前的数据
        if len(df) < days_back + 1:
            return None
        
        # 截取到5个交易日前的数据
        df_1w_ago = df.iloc[:-days_back].copy()
        
        if len(df_1w_ago) < 252:  # 需要足够的历史数据
            return None
        
        # 使用 Adjusted Close
        price_col = 'Adj Close' if 'Adj Close' in df_1w_ago.columns else 'Close'
        stock_price_series = df_1w_ago[price_col]
        
        # 准备市场基准数据（也截取到5个交易日前）
        if 'Date' in market_benchmark.columns:
            market_df = market_benchmark.set_index('Date')
        else:
            market_df = market_benchmark.copy()
        
        # 对齐日期
        common_dates = stock_price_series.index.intersection(market_df.index)
        if len(common_dates) < 252:
            return None
        
        # 截取市场数据到相同日期
        market_df_1w_ago = market_df.loc[common_dates].iloc[:-days_back]
        market_price_col = 'Adj Close' if 'Adj Close' in market_df_1w_ago.columns else 'Close'
        market_price_series = market_df_1w_ago[market_price_col]
        
        # 对齐股票数据
        stock_price_series = stock_price_series.loc[common_dates].iloc[:-days_back]
        
        # 计算1周前的加权 RS
        calculator = RSCalculator()
        result = calculator.calculate_rs_raw(stock_price_series, market_price_series)
        
        if result is None:
            return None
        
        rs_raw_1w_ago, _ = result
        
        # 基于市场分布计算百分位排名
        percentile = percentileofscore(market_rs_distribution, rs_raw_1w_ago, kind='rank')
        rs_score_1w_ago = max(1, min(99, int(percentile)))
        
        return rs_score_1w_ago
        
    except Exception as e:
        logger.debug(f"{ticker}: 计算1周前 RS Rating 失败 - {e}")
        return None

