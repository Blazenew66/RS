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
    """获取 S&P 500 股票列表"""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].tolist()
        tickers = [ticker.replace('.', '-') for ticker in tickers]
        logger.info(f"成功获取 S&P 500 股票列表，共 {len(tickers)} 只股票")
        return tickers
    except Exception as e:
        logger.warning(f"从 Wikipedia 获取 S&P 500 列表失败: {e}")
        return []


def get_nasdaq100_tickers() -> List[str]:
    """获取 NASDAQ 100 股票列表"""
    try:
        url = "https://en.wikipedia.org/wiki/NASDAQ-100"
        tables = pd.read_html(url)
        nasdaq_table = tables[4] if len(tables) > 4 else tables[0]  # 通常第5个表格是成分股列表
        if 'Ticker' in nasdaq_table.columns:
            tickers = nasdaq_table['Ticker'].tolist()
        elif 'Symbol' in nasdaq_table.columns:
            tickers = nasdaq_table['Symbol'].tolist()
        else:
            # 尝试第一列
            tickers = nasdaq_table.iloc[:, 0].tolist()
        
        tickers = [str(t).replace('.', '-').upper() for t in tickers if pd.notna(t)]
        tickers = [t for t in tickers if t and len(t) <= 5]  # 过滤有效股票代码
        logger.info(f"成功获取 NASDAQ 100 股票列表，共 {len(tickers)} 只股票")
        return tickers
    except Exception as e:
        logger.warning(f"从 Wikipedia 获取 NASDAQ 100 列表失败: {e}")
        return []


def get_combined_index_tickers() -> List[str]:
    """
    整合标普500、纳斯达克100与罗素1000指数作为基准
    移除重复标的
    
    Returns:
        整合后的股票代码列表（去重）
    """
    all_tickers = []
    
    # 1. 获取 S&P 500
    sp500_tickers = get_sp500_tickers()
    all_tickers.extend(sp500_tickers)
    logger.info(f"S&P 500: {len(sp500_tickers)} 只股票")
    
    # 2. 获取 NASDAQ 100
    nasdaq100_tickers = get_nasdaq100_tickers()
    all_tickers.extend(nasdaq100_tickers)
    logger.info(f"NASDAQ 100: {len(nasdaq100_tickers)} 只股票")
    
    # 3. 添加 Russell 1000 额外股票（不在 S&P 500 和 NASDAQ 100 中的）
    russell_additional = [
        # 成长型科技股
        'SNOW', 'PLTR', 'RBLX', 'COIN', 'HOOD', 'SOFI', 'AFRM', 'UPST',
        'LCID', 'RIVN', 'F', 'GM', 'NIO', 'XPEV', 'LI', 'SPOT', 'SQ',
        'SHOP', 'ZM', 'DOCU', 'COUP', 'BILL', 'FROG', 'MNDY', 'ASAN',
        'PATH', 'RPD', 'ESTC', 'QLYS', 'TENB', 'VRNS', 'CRWD', 'ZS',
        'NET', 'DOCN', 'OKTA', 'NOW', 'SPLK', 'VEEV', 'DASH', 'UBER',
        'LYFT', 'ABNB', 'ETSY', 'W', 'TGT', 'LOW', 'LULU',
        # 生物科技
        'MRNA', 'BNTX', 'BIIB', 'VRTX', 'ILMN', 'ALNY', 'ARWR', 'FOLD',
        'IONS', 'SGMO', 'BEAM', 'CRSP', 'NTLA', 'EDIT',
        # 金融科技
        'LC', 'NU', 'PAGS', 'FOUR', 'FISV', 'FIS',
        # 其他中大型股票
        'ON', 'WOLF', 'ALGM', 'ALKS', 'ALLO',
        # 更多 Russell 1000 股票
        'DDOG', 'CTSH', 'WDAY', 'TEAM', 'ANSS', 'PAYX', 'CTAS', 'FAST',
        'APH', 'NXPI', 'FTNT', 'KLAC', 'CDNS', 'SNPS', 'ZTS', 'ADP',
        'REGN', 'CME', 'CI', 'SYK', 'ISRG', 'AMT', 'GILD', 'TJX',
        'ADI', 'BKNG', 'LMT', 'DE', 'VZ', 'T', 'TMUS',
        'SBUX', 'AXP', 'GS', 'BLK', 'IBM', 'UPS', 'CAT',
        'HON', 'QCOM', 'AMGN', 'RTX', 'TXN', 'LIN', 'PM',
        'MCD', 'NKE', 'ADBE', 'ACN', 'NFLX', 'DIS', 'ABT',
        'COST', 'AVGO', 'PEP', 'TMO', 'CSCO', 'WMT',
        'MRK', 'HD', 'ABBV', 'V', 'PG', 'MA', 'CVX',
        'UNH', 'XOM', 'JNJ', 'JPM', 'BRK-B'
    ]
    all_tickers.extend(russell_additional)
    
    # 去重并排序
    unique_tickers = sorted(list(set(all_tickers)))
    
    # 过滤掉无效的股票代码
    valid_tickers = [t for t in unique_tickers if t and len(t) <= 5 and t.replace('-', '').isalnum()]
    
    logger.info(f"整合后共 {len(valid_tickers)} 只唯一股票（S&P 500 + NASDAQ 100 + Russell 1000）")
    
    # 返回至少 100 只股票（如果不够则使用备用列表补充）
    if len(valid_tickers) < 100:
        logger.warning(f"股票数量不足 100 只（{len(valid_tickers)}），使用备用列表补充")
        backup = [
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
            'ESTC', 'QLYS', 'TENB', 'VRNS', 'SNOW', 'PLTR', 'RBLX', 'COIN',
            'HOOD', 'SOFI', 'AFRM', 'UPST', 'LCID', 'RIVN', 'F', 'GM', 'NIO'
        ]
        all_backup = list(set(valid_tickers + backup))
        valid_tickers = sorted(all_backup)[:300]
    
    return valid_tickers[:300]  # 限制为 300 只，确保性能


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
    
    # 2. 获取市场股票的加权 RS 分数（用于建立分布）
    logger.info(f"计算 {len(market_tickers)} 只市场股票的加权 RS 分数（S&P 500 + NASDAQ 100 + Russell 1000）...")
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

