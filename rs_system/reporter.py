"""
报告生成模块：导出 CSV 和打印控制台报告
"""
import pandas as pd
import os
from datetime import datetime
from typing import Optional
import logging
from rs_system.config import OUTPUT_DIR, RANKINGS_CSV, TOP_N_DISPLAY

logger = logging.getLogger(__name__)


class Reporter:
    """报告生成器"""
    
    def __init__(self, output_dir: str = OUTPUT_DIR):
        """
        初始化报告生成器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        self.ensure_output_dir()
    
    def ensure_output_dir(self):
        """确保输出目录存在"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logger.info(f"创建输出目录: {self.output_dir}")
    
    def save_to_csv(
        self, 
        rankings_df: pd.DataFrame, 
        filename: str = RANKINGS_CSV
    ) -> str:
        """
        保存排名结果到 CSV 文件
        
        Args:
            rankings_df: 排名 DataFrame
            filename: 输出文件名（可以是相对路径或绝对路径）
            
        Returns:
            保存的文件路径
        """
        # 如果是相对路径，使用输出目录
        if not os.path.isabs(filename):
            filepath = os.path.join(self.output_dir, filename)
        else:
            filepath = filename
        
        try:
            rankings_df.to_csv(filepath, index=False, encoding='utf-8-sig')
            logger.info(f"排名结果已保存到: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存 CSV 失败: {str(e)}")
            raise
    
    def print_console_report(
        self, 
        rankings_df: pd.DataFrame, 
        top_n: int = TOP_N_DISPLAY
    ):
        """
        打印控制台报告
        
        Args:
            rankings_df: 排名 DataFrame
            top_n: 显示前 N 名
        """
        print("\n" + "=" * 80)
        print(f"美股 RS 相对强度排名报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        if rankings_df.empty:
            print("警告：没有可用的排名数据")
            return
        
        # 显示统计信息
        print(f"\n统计信息:")
        print(f"  - 总股票数: {len(rankings_df)}")
        print(f"  - RS 分数范围: {rankings_df['rs_score'].min()} - {rankings_df['rs_score'].max()}")
        print(f"  - 平均 RS 分数: {rankings_df['rs_score'].mean():.2f}")
        print(f"  - 中位数 RS 分数: {rankings_df['rs_score'].median():.2f}")
        
        # 显示 Top N
        top_df = rankings_df.head(top_n)
        print(f"\n{'=' * 80}")
        print(f"RS Top {top_n} 股票:")
        print("=" * 80)
        
        # 格式化输出
        print(f"{'排名':<6} {'股票代码':<10} {'RS分数':<10} {'RS原始值':<15} {'涨幅%':<10}")
        print("-" * 80)
        
        for _, row in top_df.iterrows():
            print(
                f"{row['rank']:<6} "
                f"{row['ticker']:<10} "
                f"{row['rs_score']:<10} "
                f"{row['rs_raw']:<15.2f} "
                f"{row['rs_raw']:<10.2f}"
            )
        
        # 显示 Bottom N（可选）
        print(f"\n{'=' * 80}")
        print(f"RS Bottom {min(5, len(rankings_df))} 股票:")
        print("=" * 80)
        
        bottom_df = rankings_df.tail(min(5, len(rankings_df)))
        print(f"{'排名':<6} {'股票代码':<10} {'RS分数':<10} {'RS原始值':<15} {'涨幅%':<10}")
        print("-" * 80)
        
        for _, row in bottom_df.iterrows():
            print(
                f"{row['rank']:<6} "
                f"{row['ticker']:<10} "
                f"{row['rs_score']:<10} "
                f"{row['rs_raw']:<15.2f} "
                f"{row['rs_raw']:<10.2f}"
            )
        
        print("\n" + "=" * 80)
    
    def generate_summary_stats(self, rankings_df: pd.DataFrame) -> dict:
        """
        生成统计摘要
        
        Args:
            rankings_df: 排名 DataFrame
            
        Returns:
            统计信息字典
        """
        if rankings_df.empty:
            return {}
        
        return {
            'total_stocks': len(rankings_df),
            'min_rs_score': float(rankings_df['rs_score'].min()),
            'max_rs_score': float(rankings_df['rs_score'].max()),
            'mean_rs_score': float(rankings_df['rs_score'].mean()),
            'median_rs_score': float(rankings_df['rs_score'].median()),
            'std_rs_score': float(rankings_df['rs_score'].std()),
            'stocks_above_70': len(rankings_df[rankings_df['rs_score'] >= 70]),
            'stocks_above_80': len(rankings_df[rankings_df['rs_score'] >= 80]),
            'stocks_above_90': len(rankings_df[rankings_df['rs_score'] >= 90]),
        }

