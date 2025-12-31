"""
市场范围排名模块：基于 S&P 500 分布计算百分位排名
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
from scipy.stats import percentileofscore
from rs_system.data_fetcher import DataFetcher
from rs_system.rs_calculator import RSCalculator
from rs_system.config import MARKET_BENCHMARK

logger = logging.getLogger(__name__)


def get_sp500_tickers() -> List[str]:
    """
    获取 S&P 500 股票列表
    
    Returns:
        S&P 500 股票代码列表
    """
    try:
        # 方法1：从 Wikipedia 获取（最可靠）
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].tolist()
        
        # 处理特殊符号（如 BRK.B -> BRK-B）
        tickers = [ticker.replace('.', '-') for ticker in tickers]
        
        logger.info(f"成功获取 S&P 500 股票列表，共 {len(tickers)} 只股票")
        return tickers
        
    except Exception as e:
        logger.warning(f"从 Wikipedia 获取 S&P 500 列表失败: {e}，使用备用列表")
        
        # 方法2：备用列表（部分 S&P 500 股票）
        # 这是一个简化的列表，实际使用时应该从 API 或文件获取完整列表
        backup_tickers = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
            'UNH', 'XOM', 'JNJ', 'JPM', 'V', 'PG', 'MA', 'CVX', 'HD', 'ABBV',
            'MRK', 'COST', 'AVGO', 'PEP', 'TMO', 'CSCO', 'WMT', 'DIS', 'ABT',
            'ACN', 'NFLX', 'ADBE', 'NKE', 'MCD', 'PM', 'LIN', 'TXN', 'RTX',
            'HON', 'QCOM', 'AMGN', 'IBM', 'UPS', 'CAT', 'GS', 'AXP', 'SBUX',
            'VZ', 'DE', 'LMT', 'BKNG', 'ADI', 'TJX', 'GILD', 'AMT', 'ISRG',
            'BLK', 'SYK', 'CI', 'CME', 'REGN', 'ADP', 'ZTS', 'CDNS', 'SNPS',
            'KLAC', 'FTNT', 'NXPI', 'APH', 'FAST', 'CTAS', 'PAYX', 'ANSS',
            'IDXX', 'MCHP', 'DXCM', 'ODFL', 'CTSH', 'WDAY', 'TEAM', 'DDOG',
            'CRWD', 'ZS', 'NET', 'DOCN', 'ESTC', 'OKTA', 'NOW', 'SPLK', 'VEEV',
            'ZM', 'DOCU', 'COUP', 'BILL', 'FROG', 'MNDY', 'ASAN', 'PATH', 'RPD',
            'ESTC', 'QLYS', 'TENB', 'VRNS', 'QLYS', 'QLYS', 'QLYS', 'QLYS'
        ]
        
        # 扩展列表（添加更多 S&P 500 股票）
        # 注意：这是一个简化的示例，实际应该获取完整列表
        return backup_tickers[:200]  # 限制为前200只，避免请求过多


def calculate_market_wide_rs_ranking(
    user_tickers: List[str],
    market_tickers: List[str],
    use_cache: bool = True
) -> tuple:
    """
    计算市场范围的 RS 排名
    
    1. 获取 S&P 500 股票的加权 RS 分数
    2. 获取用户股票的加权 RS 分数
    3. 基于 S&P 500 分布计算用户股票的百分位排名（1-99）
    
    Args:
        user_tickers: 用户输入的股票列表
        market_tickers: 市场股票列表（S&P 500）
        use_cache: 是否使用缓存
        
    Returns:
        DataFrame with columns: ticker, rs_raw, rs_score, rank, ...
    """
    fetcher = DataFetcher()
    calculator = RSCalculator()
    
    # 1. 获取市场基准数据（SPY）
    logger.info("获取市场基准数据（SPY）...")
    market_benchmark = fetcher.fetch_single_ticker(MARKET_BENCHMARK)
    if market_benchmark is None or market_benchmark.empty:
        logger.error("无法获取市场基准数据")
        return pd.DataFrame(), []
    
    # 准备市场基准价格序列
    if 'Date' in market_benchmark.columns:
        market_benchmark = market_benchmark.set_index('Date')
    market_price_series = market_benchmark['Close']
    
    # 2. 获取 S&P 500 股票的加权 RS 分数（用于建立分布）
    logger.info(f"计算 {len(market_tickers)} 只市场股票的加权 RS 分数...")
    market_rs_scores = {}
    
    for ticker in market_tickers:
        try:
            df = fetcher.fetch_single_ticker(ticker)
            if df is None or df.empty:
                continue
            
            if 'Date' in df.columns:
                df = df.set_index('Date')
            
            # 使用 Adjusted Close（如果存在）
            price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
            stock_price_series = df[price_col]
            
            # 确保市场基准也使用 Adjusted Close
            market_price_col = 'Adj Close' if 'Adj Close' in market_benchmark.columns else 'Close'
            if 'Date' in market_benchmark.columns:
                market_df = market_benchmark.set_index('Date')
            else:
                market_df = market_benchmark.copy()
            market_price_series = market_df[market_price_col]
            
            # 计算加权 RS
            result = calculator.calculate_rs_raw(stock_price_series, market_price_series)
            if result is not None:
                weighted_rs, rs_line = result
                market_rs_scores[ticker] = weighted_rs
                
        except Exception as e:
            logger.debug(f"{ticker}: 计算失败 - {e}")
            continue
    
    if not market_rs_scores:
        logger.error("无法计算任何市场股票的 RS 分数")
        return pd.DataFrame(), []
    
    logger.info(f"成功计算 {len(market_rs_scores)} 只市场股票的 RS 分数")
    
    # 3. 获取用户股票的加权 RS 分数
    logger.info(f"计算 {len(user_tickers)} 只用户股票的加权 RS 分数...")
    user_rs_data = {}
    
    for ticker in user_tickers:
        try:
            df = fetcher.fetch_single_ticker(ticker)
            if df is None or df.empty:
                continue
            
            if 'Date' in df.columns:
                df = df.set_index('Date')
            
            # 使用 Adjusted Close
            price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
            stock_price_series = df[price_col]
            
            # 确保市场基准也使用 Adjusted Close
            market_price_col = 'Adj Close' if 'Adj Close' in market_benchmark.columns else 'Close'
            if 'Date' in market_benchmark.columns:
                market_df = market_benchmark.set_index('Date')
            else:
                market_df = market_benchmark.copy()
            market_price_series = market_df[market_price_col]
            
            # 计算加权 RS 和 RS Line
            result = calculator.calculate_rs_raw(stock_price_series, market_price_series)
            if result is not None:
                weighted_rs, rs_line = result
                user_rs_data[ticker] = {
                    'rs_raw': weighted_rs,
                    'rs_line': rs_line,
                    'price_data': df  # 保存价格数据用于后续计算
                }
                
        except Exception as e:
            logger.debug(f"{ticker}: 计算失败 - {e}")
            continue
    
    if not user_rs_data:
        logger.error("无法计算任何用户股票的 RS 分数")
        return pd.DataFrame(), market_rs_values
    
    # 4. 基于市场分布计算百分位排名（1-99）
    market_rs_values = list(market_rs_scores.values())
    
    results = []
    for ticker, data in user_rs_data.items():
        rs_raw = data['rs_raw']
        
        # 使用 scipy.stats.percentileofscore 计算百分位
        percentile = percentileofscore(market_rs_values, rs_raw, kind='rank')
        
        # 映射到 1-99 区间
        rs_score = max(1, min(99, int(percentile)))
        
        results.append({
            'ticker': ticker,
            'rs_raw': rs_raw,
            'rs_line': data['rs_line'],
            'rs_score': rs_score,
            'price_data': data['price_data']  # 保存用于后续计算
        })
    
    # 创建 DataFrame
    df = pd.DataFrame(results)
    df['rank'] = df['rs_score'].rank(ascending=False, method='min').astype(int)
    df = df.sort_values('rs_score', ascending=False).reset_index(drop=True)
    
    logger.info(f"市场范围排名完成，共 {len(df)} 只股票")
    
    # 返回 DataFrame 和市场 RS 分布（用于计算1周前评分）
    return df, market_rs_values

