"""
行业相对强度分析模块
基于马克·米勒维尼的《超级绩效》方法
计算行业ETF的相对强度，识别强势行业
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# 主要行业ETF列表（SPDR Sector ETFs）
INDUSTRY_ETFS = {
    'XLK': 'Technology',  # 科技
    'XLE': 'Energy',  # 能源
    'XLF': 'Financial',  # 金融
    'XLV': 'Healthcare',  # 医疗
    'XLI': 'Industrial',  # 工业
    'XLP': 'Consumer Staples',  # 必需消费品
    'XLY': 'Consumer Discretionary',  # 可选消费品
    'XLU': 'Utilities',  # 公用事业
    'XLB': 'Materials',  # 材料
    'XLRE': 'Real Estate',  # 房地产
    'XLC': 'Communication Services',  # 通信服务
}

# 股票到行业的映射（简化版，实际应该从数据源获取）
STOCK_TO_INDUSTRY = {
    # 科技
    'AAPL': 'XLK', 'MSFT': 'XLK', 'GOOGL': 'XLK', 'GOOG': 'XLK', 'AMZN': 'XLK',
    'META': 'XLK', 'NVDA': 'XLK', 'TSLA': 'XLK', 'INTC': 'XLK', 'AMD': 'XLK',
    'CRM': 'XLK', 'ORCL': 'XLK', 'ADBE': 'XLK', 'NFLX': 'XLK',
    # 金融
    'JPM': 'XLF', 'BAC': 'XLF', 'WFC': 'XLF', 'GS': 'XLF', 'MS': 'XLF',
    'C': 'XLF', 'BLK': 'XLF', 'SCHW': 'XLF',
    # 医疗
    'JNJ': 'XLV', 'PFE': 'XLV', 'UNH': 'XLV', 'ABT': 'XLV', 'TMO': 'XLV',
    'ABBV': 'XLV', 'MRK': 'XLV', 'LLY': 'XLV',
    # 能源
    'XOM': 'XLE', 'CVX': 'XLE', 'SLB': 'XLE', 'COP': 'XLE', 'EOG': 'XLE',
    # 工业
    'BA': 'XLI', 'CAT': 'XLI', 'GE': 'XLI', 'HON': 'XLI', 'UPS': 'XLI',
    # 消费
    'WMT': 'XLP', 'HD': 'XLY', 'MCD': 'XLY', 'NKE': 'XLY', 'SBUX': 'XLY',
    'TGT': 'XLY', 'LOW': 'XLY',
    # 通信
    'VZ': 'XLC', 'T': 'XLC', 'CMCSA': 'XLC', 'DIS': 'XLC',
}


def get_stock_industry(ticker: str) -> Optional[str]:
    """
    获取股票所属的行业ETF代码
    
    Args:
        ticker: 股票代码
        
    Returns:
        行业ETF代码，如果无法确定则返回 None
    """
    return STOCK_TO_INDUSTRY.get(ticker.upper())


def calculate_industry_rs(
    industry_etf: str,
    market_benchmark: pd.DataFrame,
    fetcher
) -> Optional[Dict]:
    """
    计算行业ETF的相对强度
    
    Args:
        industry_etf: 行业ETF代码（如 'XLK'）
        market_benchmark: 市场基准数据（SPY）
        fetcher: DataFetcher 实例
        
    Returns:
        行业RS分析结果
        {
            'industry_etf': str,
            'industry_name': str,
            'rs_score': float,  # RS评分（1-99）
            'rs_trend': str,  # 'Up', 'Down', 'Sideways'
            'vs_market': float,  # 相对于市场的表现（%）
            'data_available': bool
        }
    """
    try:
        # 获取行业ETF数据
        industry_data = fetcher.fetch_single_ticker(industry_etf)
        if industry_data is None or industry_data.empty:
            return None
        
        # 计算RS（使用与股票相同的计算方法）
        from rs_system.rs_calculator import RSCalculator
        calculator = RSCalculator()
        
        # 准备数据
        if 'Date' in industry_data.columns:
            industry_data = industry_data.set_index('Date')
        if 'Date' in market_benchmark.columns:
            market_benchmark = market_benchmark.set_index('Date')
        
        price_col = 'Adj Close' if 'Adj Close' in industry_data.columns else 'Close'
        market_col = 'Adj Close' if 'Adj Close' in market_benchmark.columns else 'Close'
        
        industry_prices = industry_data[price_col].dropna()
        market_prices = market_benchmark[market_col].dropna()
        
        # 计算RS
        result = calculator.calculate_rs_raw(industry_prices, market_prices)
        if result is None:
            return None
        
        rs_raw, _ = result
        
        # 计算趋势
        from rs_system.indicators import calculate_rs_trend
        rs_slope, rs_arrow = calculate_rs_trend(industry_data, market_benchmark)
        
        # 计算相对于市场的表现（最近3个月）
        if len(industry_prices) >= 63 and len(market_prices) >= 63:
            industry_return = (industry_prices.iloc[-1] - industry_prices.iloc[-63]) / industry_prices.iloc[-63] * 100
            market_return = (market_prices.iloc[-1] - market_prices.iloc[-63]) / market_prices.iloc[-63] * 100
            vs_market = industry_return - market_return
        else:
            vs_market = None
        
        # 将RS原始值转换为1-99评分（简化版，实际应该基于市场分布）
        # 这里使用线性映射作为近似
        rs_score = max(1, min(99, int(50 + rs_raw * 10)))
        
        # 确定趋势
        if rs_arrow == "⬆️":
            rs_trend = "Up"
        elif rs_arrow == "⬇️":
            rs_trend = "Down"
        else:
            rs_trend = "Sideways"
        
        return {
            'industry_etf': industry_etf,
            'industry_name': INDUSTRY_ETFS.get(industry_etf, industry_etf),
            'rs_score': rs_score,
            'rs_trend': rs_trend,
            'vs_market': round(vs_market, 2) if vs_market is not None else None,
            'data_available': True
        }
        
    except Exception as e:
        logger.warning(f"计算行业 {industry_etf} RS失败: {e}")
        return None


def analyze_all_industries(
    market_benchmark: pd.DataFrame,
    fetcher
) -> Dict[str, Dict]:
    """
    分析所有行业的相对强度
    
    Args:
        market_benchmark: 市场基准数据
        fetcher: DataFetcher 实例
        
    Returns:
        行业RS分析结果字典 {industry_etf: analysis_result}
    """
    results = {}
    
    for industry_etf in INDUSTRY_ETFS.keys():
        analysis = calculate_industry_rs(industry_etf, market_benchmark, fetcher)
        if analysis and analysis.get('data_available'):
            results[industry_etf] = analysis
    
    # 按RS评分排序
    sorted_results = dict(sorted(
        results.items(),
        key=lambda x: x[1].get('rs_score', 0),
        reverse=True
    ))
    
    return sorted_results


def get_stock_industry_rs(
    ticker: str,
    market_benchmark: pd.DataFrame,
    fetcher
) -> Optional[Dict]:
    """
    获取股票所属行业的相对强度
    
    Args:
        ticker: 股票代码
        market_benchmark: 市场基准数据
        fetcher: DataFetcher 实例
        
    Returns:
        行业RS分析结果
    """
    industry_etf = get_stock_industry(ticker)
    if not industry_etf:
        return None
    
    return calculate_industry_rs(industry_etf, market_benchmark, fetcher)

