"""
RS 计算模块：计算股票的 Relative Strength 原始值
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from rs_system.config import LOOKBACK_PERIOD

logger = logging.getLogger(__name__)


class RSCalculator:
    """RS 计算器"""
    
    def __init__(self, lookback_period: int = LOOKBACK_PERIOD):
        """
        初始化 RS 计算器
        
        Args:
            lookback_period: 回看周期（交易日数），默认 252
        """
        self.lookback_period = lookback_period
    
    def calculate_rs_raw(self, price_series: pd.Series) -> Optional[float]:
        """
        计算单只股票的 RS 原始值
        
        公式：RS_raw = (Close_today / Close_N_days_ago - 1) * 100
        
        Args:
            price_series: 收盘价序列（按日期排序，最新的在最后）
            
        Returns:
            RS 原始值（百分比），如果计算失败返回 None
        """
        if price_series is None or len(price_series) < self.lookback_period + 1:
            return None
        
        try:
            # 确保数据按日期排序（最新的在最后）
            price_series = price_series.sort_index()
            
            # 获取当前价格和 N 天前的价格
            current_price = price_series.iloc[-1]
            past_price = price_series.iloc[-(self.lookback_period + 1)]
            
            # 处理异常值
            if pd.isna(current_price) or pd.isna(past_price):
                return None
            
            if past_price <= 0:
                logger.warning(f"历史价格为 0 或负数: {past_price}")
                return None
            
            # 计算涨幅百分比
            rs_raw = (current_price / past_price - 1) * 100
            
            return rs_raw
            
        except Exception as e:
            logger.error(f"计算 RS 失败: {str(e)}")
            return None
    
    def calculate_rs_for_all(
        self, 
        ticker_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, float]:
        """
        批量计算所有股票的 RS 原始值
        
        Args:
            ticker_data: Dict[ticker, DataFrame]，包含每只股票的历史数据
            
        Returns:
            Dict[ticker, rs_raw]
        """
        rs_results = {}
        
        logger.info(f"开始计算 {len(ticker_data)} 只股票的 RS 值...")
        
        for ticker, df in ticker_data.items():
            if 'Close' not in df.columns:
                logger.warning(f"{ticker}: 缺少 Close 列，跳过")
                continue
            
            # 使用 Date 作为索引（如果存在）
            if 'Date' in df.columns:
                df = df.set_index('Date')
            
            price_series = df['Close']
            rs_raw = self.calculate_rs_raw(price_series)
            
            if rs_raw is not None:
                rs_results[ticker] = rs_raw
            else:
                logger.warning(f"{ticker}: RS 计算失败，跳过")
        
        logger.info(f"RS 计算完成，成功计算 {len(rs_results)}/{len(ticker_data)} 只股票")
        return rs_results
    
    def calculate_multi_period_rs(
        self, 
        price_series: pd.Series,
        periods: Dict[int, float] = None
    ) -> Optional[float]:
        """
        计算多周期加权 RS（进阶功能，预留接口）
        
        Args:
            price_series: 收盘价序列
            periods: Dict[周期天数, 权重]，例如 {252: 0.6, 126: 0.3, 63: 0.1}
            
        Returns:
            加权 RS 值
        """
        if periods is None:
            # 默认使用单周期
            return self.calculate_rs_raw(price_series)
        
        weighted_rs = 0.0
        total_weight = 0.0
        
        for period, weight in periods.items():
            # 临时修改 lookback_period
            original_period = self.lookback_period
            self.lookback_period = period
            
            rs = self.calculate_rs_raw(price_series)
            if rs is not None:
                weighted_rs += rs * weight
                total_weight += weight
            
            # 恢复原始周期
            self.lookback_period = original_period
        
        if total_weight == 0:
            return None
        
        return weighted_rs / total_weight

