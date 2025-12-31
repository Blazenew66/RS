"""
排名模块：将 RS 原始值转换为 1-99 的排名分数
"""
import pandas as pd
import numpy as np
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class Ranker:
    """RS 排名器"""
    
    def __init__(self, min_score: int = 1, max_score: int = 99):
        """
        初始化排名器
        
        Args:
            min_score: 最低排名分数，默认 1
            max_score: 最高排名分数，默认 99
        """
        self.min_score = min_score
        self.max_score = max_score
    
    def rank_rs_scores(self, rs_raw_dict: Dict[str, tuple]) -> pd.DataFrame:
        """
        将 RS 原始值转换为排名分数并排序（IBD 风格）
        
        算法：
        1. 将所有加权 RS 值排序
        2. 使用百分位排名映射到 1-99 区间
        3. 生成最终排名
        
        Args:
            rs_raw_dict: Dict[ticker, (加权 RS 值, RS Line 值)]
            
        Returns:
            DataFrame with columns: ticker, rs_raw, rs_line, rs_score, rank
            按 rs_score 降序排列
        """
        if not rs_raw_dict:
            logger.warning("RS 原始值字典为空")
            return pd.DataFrame(columns=['ticker', 'rs_raw', 'rs_line', 'rs_score', 'rank'])
        
        # 转换为 DataFrame（处理元组格式）
        data_list = []
        for ticker, rs_data in rs_raw_dict.items():
            if isinstance(rs_data, tuple) and len(rs_data) == 2:
                rs_raw, rs_line = rs_data
                data_list.append({
                    'ticker': ticker,
                    'rs_raw': rs_raw,
                    'rs_line': rs_line
                })
            else:
                # 兼容旧格式（只有 rs_raw）
                logger.warning(f"{ticker}: RS 数据格式异常，跳过")
                continue
        
        if not data_list:
            logger.warning("没有有效的 RS 数据")
            return pd.DataFrame(columns=['ticker', 'rs_raw', 'rs_line', 'rs_score', 'rank'])
        
        df = pd.DataFrame(data_list)
        
        # 计算百分位排名（0-1 之间）
        df['percentile'] = df['rs_raw'].rank(pct=True, method='min')
        
        # 映射到 1-99 区间
        # 公式：rs_score = min_score + (percentile * (max_score - min_score))
        df['rs_score'] = (
            self.min_score + 
            (df['percentile'] * (self.max_score - self.min_score))
        ).round(0).astype(int)
        
        # 确保边界值正确
        df.loc[df['rs_score'] < self.min_score, 'rs_score'] = self.min_score
        df.loc[df['rs_score'] > self.max_score, 'rs_score'] = self.max_score
        
        # 计算排名（1 为最高）
        df['rank'] = df['rs_score'].rank(ascending=False, method='min').astype(int)
        
        # 按 rs_score 降序排列
        df = df.sort_values('rs_score', ascending=False).reset_index(drop=True)
        
        # 重新排列列顺序
        df = df[['ticker', 'rs_raw', 'rs_line', 'rs_score', 'rank']]
        
        logger.info(f"排名完成，共 {len(df)} 只股票")
        logger.info(f"RS 分数范围: {df['rs_score'].min()} - {df['rs_score'].max()}")
        
        return df
    
    def get_top_n(self, rankings_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
        """
        获取 Top N 股票
        
        Args:
            rankings_df: 排名 DataFrame
            n: 返回前 N 名
            
        Returns:
            Top N 的 DataFrame
        """
        return rankings_df.head(n)

