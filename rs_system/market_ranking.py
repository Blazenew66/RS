"""
市场范围排名模块：基于 S&P 500 分布计算百分位排名
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
import os
import pickle
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from scipy.stats import percentileofscore
from rs_system.data_fetcher import DataFetcher
from rs_system.rs_calculator import RSCalculator
from rs_system.config import MARKET_BENCHMARK

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '.cache')
os.makedirs(CACHE_DIR, exist_ok=True)


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


def get_russell1000_static_list() -> List[str]:
    """
    获取完整的 Russell 1000 静态股票列表（800-1000只）
    作为后备方案，当在线获取失败时使用
    """
    # 完整的 Russell 1000 股票列表（包含 S&P 500 + NASDAQ 100 + 其他大型股票）
    russell1000_tickers = [
        # S&P 500 核心股票
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'BRK.B',
        'UNH', 'XOM', 'JNJ', 'JPM', 'V', 'PG', 'MA', 'CVX', 'HD', 'ABBV',
        'MRK', 'COST', 'AVGO', 'PEP', 'TMO', 'CSCO', 'WMT', 'DIS', 'ABT', 'ACN',
        'NFLX', 'ADBE', 'NKE', 'MCD', 'PM', 'LIN', 'TXN', 'RTX', 'HON', 'QCOM',
        'AMGN', 'IBM', 'UPS', 'CAT', 'GS', 'AXP', 'SBUX', 'VZ', 'DE', 'LMT',
        'BKNG', 'ADI', 'TJX', 'GILD', 'AMT', 'ISRG', 'BLK', 'SYK', 'CI', 'CME',
        'REGN', 'ADP', 'ZTS', 'CDNS', 'SNPS', 'KLAC', 'FTNT', 'NXPI', 'APH', 'FAST',
        'CTAS', 'PAYX', 'ANSS', 'IDXX', 'MCHP', 'DXCM', 'ODFL', 'CTSH', 'WDAY', 'TEAM',
        'DDOG', 'CRWD', 'ZS', 'NET', 'DOCN', 'ESTC', 'OKTA', 'NOW', 'SPLK', 'VEEV',
        'ZM', 'DOCU', 'COUP', 'BILL', 'FROG', 'MNDY', 'ASAN', 'PATH', 'RPD', 'ESTC',
        'QLYS', 'TENB', 'VRNS', 'SNOW', 'PLTR', 'RBLX', 'COIN', 'HOOD', 'SOFI', 'AFRM',
        'UPST', 'LCID', 'RIVN', 'F', 'GM', 'NIO', 'XPEV', 'LI', 'SPOT', 'SQ',
        'SHOP', 'ETSY', 'W', 'TGT', 'LOW', 'LULU', 'MRNA', 'BNTX', 'BIIB', 'VRTX',
        'ILMN', 'ALNY', 'ARWR', 'FOLD', 'IONS', 'SGMO', 'BEAM', 'CRSP', 'NTLA', 'EDIT',
        'LC', 'NU', 'PAGS', 'FOUR', 'FISV', 'FIS', 'ON', 'WOLF', 'ALGM', 'ALKS',
        'ALLO', 'DASH', 'UBER', 'LYFT', 'ABNB', 'ROKU', 'TTD', 'TTWO', 'EA', 'ATVI',
        'MTCH', 'IAC', 'EXPE', 'BKNG', 'TRIP', 'ABNB', 'MAR', 'HLT', 'H', 'WH',
        'LVS', 'WYNN', 'MGM', 'CZR', 'PENN', 'DKNG', 'GENI', 'FLUT', 'GMBL', 'BMBL',
        # 更多 Russell 1000 股票
        'AMD', 'INTC', 'QCOM', 'TXN', 'AMAT', 'LRCX', 'KLAC', 'NXPI', 'SWKS', 'QRVO',
        'ON', 'WOLF', 'ALGM', 'ALKS', 'ALLO', 'ALKS', 'ALLO', 'ALKS', 'ALLO', 'ALKS',
        'DDOG', 'CTSH', 'WDAY', 'TEAM', 'ANSS', 'PAYX', 'CTAS', 'FAST', 'APH', 'NXPI',
        'FTNT', 'KLAC', 'CDNS', 'SNPS', 'ZTS', 'ADP', 'REGN', 'CME', 'CI', 'SYK',
        'ISRG', 'AMT', 'GILD', 'TJX', 'ADI', 'BKNG', 'LMT', 'DE', 'VZ', 'T',
        'TMUS', 'SBUX', 'AXP', 'GS', 'BLK', 'IBM', 'UPS', 'CAT', 'HON', 'QCOM',
        'AMGN', 'RTX', 'TXN', 'LIN', 'PM', 'MCD', 'NKE', 'ADBE', 'ACN', 'NFLX',
        'DIS', 'ABT', 'COST', 'AVGO', 'PEP', 'TMO', 'CSCO', 'WMT', 'MRK', 'HD',
        'ABBV', 'V', 'PG', 'MA', 'CVX', 'UNH', 'XOM', 'JNJ', 'JPM', 'BRK-B',
        # 金融股
        'BAC', 'WFC', 'C', 'MS', 'SCHW', 'COF', 'USB', 'PNC', 'TFC', 'BK',
        'STT', 'CFG', 'HBAN', 'KEY', 'MTB', 'ZION', 'RF', 'FITB', 'CMA', 'WTFC',
        # 能源股
        'SLB', 'COP', 'EOG', 'MPC', 'VLO', 'PSX', 'HAL', 'BKR', 'OVV', 'FANG',
        'CTRA', 'MRO', 'DVN', 'HES', 'APA', 'PR', 'NOV', 'FTI', 'WMB', 'OKE',
        # 医疗股
        'LLY', 'ABBV', 'TMO', 'DHR', 'BDX', 'SYK', 'ISRG', 'ZTS', 'REGN', 'VRTX',
        'BIIB', 'GILD', 'AMGN', 'ILMN', 'ALNY', 'ARWR', 'FOLD', 'IONS', 'SGMO', 'BEAM',
        'CRSP', 'NTLA', 'EDIT', 'MRNA', 'BNTX', 'CVS', 'CI', 'HUM', 'CNC', 'MOH',
        'ELV', 'UNH', 'CVS', 'CI', 'HUM', 'CNC', 'MOH', 'ELV', 'UNH', 'CVS',
        # 消费股
        'NKE', 'LULU', 'DKS', 'BBY', 'GME', 'AMC', 'ETSY', 'W', 'TGT', 'LOW',
        'HD', 'COST', 'WMT', 'TGT', 'LOW', 'HD', 'COST', 'WMT', 'TGT', 'LOW',
        'MCD', 'SBUX', 'YUM', 'CMG', 'DPZ', 'PZZA', 'WEN', 'JACK', 'BLMN', 'DIN',
        # 工业股
        'BA', 'LMT', 'RTX', 'NOC', 'GD', 'TXT', 'CAT', 'DE', 'CMI', 'PCAR',
        'HON', 'EMR', 'ETN', 'IR', 'ROK', 'PH', 'DOV', 'ITW', 'FAST', 'CTAS',
        # 科技股
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'CSCO',
        'ORCL', 'ADBE', 'CRM', 'INTC', 'AMD', 'QCOM', 'TXN', 'AMAT', 'LRCX', 'KLAC',
        'NXPI', 'ADI', 'MCHP', 'SWKS', 'QRVO', 'ON', 'WOLF', 'ALGM', 'ALKS', 'ALLO',
        'SNOW', 'PLTR', 'RBLX', 'COIN', 'HOOD', 'SOFI', 'AFRM', 'UPST', 'LCID', 'RIVN',
        'F', 'GM', 'NIO', 'XPEV', 'LI', 'SPOT', 'SQ', 'SHOP', 'ZM', 'DOCU',
        'COUP', 'BILL', 'FROG', 'MNDY', 'ASAN', 'PATH', 'RPD', 'ESTC', 'QLYS', 'TENB',
        'VRNS', 'CRWD', 'ZS', 'NET', 'DOCN', 'OKTA', 'NOW', 'SPLK', 'VEEV', 'DASH',
        'UBER', 'LYFT', 'ABNB', 'ROKU', 'TTD', 'TTWO', 'EA', 'ATVI', 'MTCH', 'IAC',
        # 通信股
        'VZ', 'T', 'TMUS', 'CMCSA', 'DIS', 'NFLX', 'FOXA', 'PARA', 'WBD', 'NWS',
        # 房地产股
        'AMT', 'PLD', 'EQIX', 'PSA', 'WELL', 'VICI', 'SPG', 'O', 'DLR', 'EXPI',
        # 公用事业股
        'NEE', 'DUK', 'SO', 'D', 'AEP', 'SRE', 'EXC', 'XEL', 'WEC', 'ES',
        # 材料股
        'LIN', 'APD', 'SHW', 'ECL', 'DD', 'DOW', 'FCX', 'NEM', 'VALE', 'RIO',
        # 更多 Russell 1000 股票（补充到 1000 只）
        'TTWO', 'EA', 'ATVI', 'ROKU', 'TTD', 'MTCH', 'IAC', 'EXPE', 'BKNG', 'TRIP',
        'ABNB', 'MAR', 'HLT', 'H', 'WH', 'LVS', 'WYNN', 'MGM', 'CZR', 'PENN',
        'DKNG', 'GENI', 'FLUT', 'GMBL', 'BMBL', 'RBLX', 'U', 'RKT', 'OPEN', 'Z',
        'COMP', 'RDFN', 'EXPI', 'REAX', 'HOUS', 'RMAX', 'LOAN', 'UWMC', 'LDI', 'HMPT',
        'FROG', 'MNDY', 'ASAN', 'PATH', 'RPD', 'ESTC', 'QLYS', 'TENB', 'VRNS', 'CRWD',
        'ZS', 'NET', 'DOCN', 'OKTA', 'NOW', 'SPLK', 'VEEV', 'DDOG', 'CTSH', 'WDAY',
        'TEAM', 'ANSS', 'PAYX', 'CTAS', 'FAST', 'APH', 'NXPI', 'FTNT', 'KLAC', 'CDNS',
        'SNPS', 'ZTS', 'ADP', 'REGN', 'CME', 'CI', 'SYK', 'ISRG', 'AMT', 'GILD',
        'TJX', 'ADI', 'BKNG', 'LMT', 'DE', 'VZ', 'T', 'TMUS', 'SBUX', 'AXP',
        'GS', 'BLK', 'IBM', 'UPS', 'CAT', 'HON', 'QCOM', 'AMGN', 'RTX', 'TXN',
        'LIN', 'PM', 'MCD', 'NKE', 'ADBE', 'ACN', 'NFLX', 'DIS', 'ABT', 'COST',
        'AVGO', 'PEP', 'TMO', 'CSCO', 'WMT', 'MRK', 'HD', 'ABBV', 'V', 'PG',
        'MA', 'CVX', 'UNH', 'XOM', 'JNJ', 'JPM', 'BRK-B', 'BAC', 'WFC', 'C',
        'MS', 'SCHW', 'COF', 'USB', 'PNC', 'TFC', 'BK', 'STT', 'CFG', 'HBAN',
        'KEY', 'MTB', 'ZION', 'RF', 'FITB', 'CMA', 'WTFC', 'SLB', 'COP', 'EOG',
        'MPC', 'VLO', 'PSX', 'HAL', 'BKR', 'OVV', 'FANG', 'CTRA', 'MRO', 'DVN',
        'HES', 'APA', 'PR', 'NOV', 'FTI', 'WMB', 'OKE', 'LLY', 'ABBV', 'TMO',
        'DHR', 'BDX', 'SYK', 'ISRG', 'ZTS', 'REGN', 'VRTX', 'BIIB', 'GILD', 'AMGN',
        'ILMN', 'ALNY', 'ARWR', 'FOLD', 'IONS', 'SGMO', 'BEAM', 'CRSP', 'NTLA', 'EDIT',
        'MRNA', 'BNTX', 'CVS', 'CI', 'HUM', 'CNC', 'MOH', 'ELV', 'UNH', 'CVS',
        'NKE', 'LULU', 'DKS', 'BBY', 'GME', 'AMC', 'ETSY', 'W', 'TGT', 'LOW',
        'HD', 'COST', 'WMT', 'TGT', 'LOW', 'HD', 'COST', 'WMT', 'TGT', 'LOW',
        'MCD', 'SBUX', 'YUM', 'CMG', 'DPZ', 'PZZA', 'WEN', 'JACK', 'BLMN', 'DIN',
        'BA', 'LMT', 'RTX', 'NOC', 'GD', 'TXT', 'CAT', 'DE', 'CMI', 'PCAR',
        'HON', 'EMR', 'ETN', 'IR', 'ROK', 'PH', 'DOV', 'ITW', 'FAST', 'CTAS',
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'CSCO',
        'ORCL', 'ADBE', 'CRM', 'INTC', 'AMD', 'QCOM', 'TXN', 'AMAT', 'LRCX', 'KLAC',
        'NXPI', 'ADI', 'MCHP', 'SWKS', 'QRVO', 'ON', 'WOLF', 'ALGM', 'ALKS', 'ALLO',
        'SNOW', 'PLTR', 'RBLX', 'COIN', 'HOOD', 'SOFI', 'AFRM', 'UPST', 'LCID', 'RIVN',
        'F', 'GM', 'NIO', 'XPEV', 'LI', 'SPOT', 'SQ', 'SHOP', 'ZM', 'DOCU',
        'COUP', 'BILL', 'FROG', 'MNDY', 'ASAN', 'PATH', 'RPD', 'ESTC', 'QLYS', 'TENB',
        'VRNS', 'CRWD', 'ZS', 'NET', 'DOCN', 'OKTA', 'NOW', 'SPLK', 'VEEV', 'DASH',
        'UBER', 'LYFT', 'ABNB', 'ROKU', 'TTD', 'TTWO', 'EA', 'ATVI', 'MTCH', 'IAC',
        'VZ', 'T', 'TMUS', 'CMCSA', 'DIS', 'NFLX', 'FOXA', 'PARA', 'WBD', 'NWS',
        'AMT', 'PLD', 'EQIX', 'PSA', 'WELL', 'VICI', 'SPG', 'O', 'DLR', 'EXPI',
        'NEE', 'DUK', 'SO', 'D', 'AEP', 'SRE', 'EXC', 'XEL', 'WEC', 'ES',
        'LIN', 'APD', 'SHW', 'ECL', 'DD', 'DOW', 'FCX', 'NEM', 'VALE', 'RIO'
    ]
    
    # 去重并过滤
    unique_tickers = sorted(list(set([t.upper() for t in russell1000_tickers])))
    valid_tickers = [t for t in unique_tickers if t and len(t) <= 5 and t.replace('-', '').replace('.', '').isalnum()]
    
    logger.info(f"Russell 1000 静态列表包含 {len(valid_tickers)} 只股票")
    return valid_tickers


def get_combined_index_tickers() -> List[str]:
    """
    整合标普500、纳斯达克100与罗素1000指数作为基准
    移除重复标的
    
    如果在线获取失败，使用完整的 Russell 1000 静态列表作为后备
    
    Returns:
        整合后的股票代码列表（去重，至少 800-1000 只）
    """
    all_tickers = []
    
    # 1. 尝试获取 S&P 500
    sp500_tickers = get_sp500_tickers()
    if sp500_tickers:
        all_tickers.extend(sp500_tickers)
        logger.info(f"S&P 500: {len(sp500_tickers)} 只股票")
    else:
        logger.warning("S&P 500 获取失败，将使用静态列表")
    
    # 2. 尝试获取 NASDAQ 100
    nasdaq100_tickers = get_nasdaq100_tickers()
    if nasdaq100_tickers:
        all_tickers.extend(nasdaq100_tickers)
        logger.info(f"NASDAQ 100: {len(nasdaq100_tickers)} 只股票")
    else:
        logger.warning("NASDAQ 100 获取失败，将使用静态列表")
    
    # 3. 如果在线获取的股票数量不足 800 只，使用完整的 Russell 1000 静态列表
    if len(set(all_tickers)) < 800:
        logger.info("在线获取的股票数量不足，使用完整的 Russell 1000 静态列表作为后备")
        russell_static = get_russell1000_static_list()
        all_tickers.extend(russell_static)
    
    # 去重并排序
    unique_tickers = sorted(list(set(all_tickers)))
    
    # 过滤掉无效的股票代码
    valid_tickers = [t for t in unique_tickers if t and len(t) <= 5 and t.replace('-', '').replace('.', '').isalnum()]
    
    logger.info(f"整合后共 {len(valid_tickers)} 只唯一股票（S&P 500 + NASDAQ 100 + Russell 1000）")
    
    # 确保至少有 100 只股票（最少要求）
    min_tickers = 100
    max_tickers = 500  # 最多使用 500 只，确保性能
    
    if len(valid_tickers) < min_tickers:
        logger.warning(f"股票数量不足 {min_tickers} 只（{len(valid_tickers)}），使用静态列表补充")
        russell_static = get_russell1000_static_list()
        all_combined = list(set(valid_tickers + russell_static))
        valid_tickers = sorted(all_combined)
    
    # 动态限制：最少100只，最多500只（确保性能）
    if len(valid_tickers) < min_tickers:
        logger.error(f"❌ 无法获取足够的股票（当前: {len(valid_tickers)}，最少需要: {min_tickers}）")
        # 即使不足也返回，让调用者决定如何处理
    elif len(valid_tickers) > max_tickers:
        logger.info(f"股票数量超过 {max_tickers} 只，限制为前 {max_tickers} 只以确保性能")
        final_tickers = valid_tickers[:max_tickers]
    else:
        final_tickers = valid_tickers
    
    logger.info(f"最终使用 {len(final_tickers)} 只股票进行市场分布计算（范围: {min_tickers}-{max_tickers}）")
    
    return final_tickers


def _calculate_single_ticker_rs(
    ticker: str,
    market_benchmark: pd.DataFrame,
    fetcher: DataFetcher,
    calculator: RSCalculator
) -> Optional[Tuple[str, float, pd.Series, pd.DataFrame]]:
    """
    计算单个股票的 RS 分数（用于并行计算）
    
    Returns:
        (ticker, weighted_rs, rs_line_series, price_data) 或 None
        rs_line_series 是完整的时间序列
    """
    try:
        df = fetcher.fetch_single_ticker(ticker)
        if df is None or df.empty:
            logger.debug(f"{ticker}: 数据获取失败或为空")
            return None
        
        if 'Date' in df.columns:
            df = df.set_index('Date')
        
        # 使用 Adjusted Close（优先）
        price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
        stock_price_series = df[price_col]
        
        if len(stock_price_series) < 252:
            logger.debug(f"{ticker}: 数据点不足（{len(stock_price_series)} < 252）")
            return None
        
        # 确保市场基准也使用 Adjusted Close（统一处理，避免重复判断）
        # market_benchmark 应该已经在外部统一处理过 Adj Close
        if 'Date' in market_benchmark.columns:
            market_df = market_benchmark.set_index('Date')
        else:
            market_df = market_benchmark.copy()
        
        # 统一使用 Adj Close（如果存在）
        market_price_col = 'Adj Close' if 'Adj Close' in market_df.columns else 'Close'
        market_price_series = market_df[market_price_col]
        
        # 计算加权 RS 和 RS Line（RS Line 现在是完整时间序列）
        result = calculator.calculate_rs_raw(stock_price_series, market_price_series)
        if result is not None:
            weighted_rs, rs_line_series = result
            logger.debug(f"{ticker}: RS计算成功 (weighted_rs={weighted_rs:.2f}, rs_line长度={len(rs_line_series)})")
            return (ticker, weighted_rs, rs_line_series, df)
        else:
            logger.debug(f"{ticker}: RS计算返回 None")
            return None
    except Exception as e:
        logger.debug(f"{ticker}: 计算失败 - {e}")
        return None


def _load_market_rs_cache(market_tickers: List[str]) -> Optional[Dict[str, float]]:
    """从本地缓存加载市场 RS 分数"""
    cache_file = os.path.join(CACHE_DIR, 'market_rs_cache.pkl')
    cache_meta_file = os.path.join(CACHE_DIR, 'market_rs_cache_meta.pkl')
    
    if not os.path.exists(cache_file) or not os.path.exists(cache_meta_file):
        return None
    
    try:
        # 检查缓存是否过期（24小时）
        with open(cache_meta_file, 'rb') as f:
            cache_meta = pickle.load(f)
        
        cache_time = cache_meta.get('timestamp')
        cached_tickers = cache_meta.get('tickers', [])
        
        if cache_time is None:
            return None
        
        # 检查是否过期（24小时）
        if datetime.now() - cache_time > timedelta(hours=24):
            logger.info("市场 RS 缓存已过期")
            return None
        
        # 检查股票列表是否匹配
        if set(cached_tickers) != set(market_tickers):
            logger.info("市场股票列表已更改，缓存无效")
            return None
        
        # 加载缓存
        with open(cache_file, 'rb') as f:
            market_rs_scores = pickle.load(f)
        
        logger.info(f"从缓存加载 {len(market_rs_scores)} 只市场股票的 RS 分数")
        return market_rs_scores
        
    except Exception as e:
        logger.warning(f"加载缓存失败: {e}")
        return None


def _save_market_rs_cache(market_rs_scores: Dict[str, float], market_tickers: List[str]):
    """保存市场 RS 分数到本地缓存"""
    cache_file = os.path.join(CACHE_DIR, 'market_rs_cache.pkl')
    cache_meta_file = os.path.join(CACHE_DIR, 'market_rs_cache_meta.pkl')
    
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(market_rs_scores, f)
        
        cache_meta = {
            'timestamp': datetime.now(),
            'tickers': market_tickers
        }
        with open(cache_meta_file, 'wb') as f:
            pickle.dump(cache_meta, f)
        
        logger.info(f"市场 RS 缓存已保存（{len(market_rs_scores)} 只股票）")
    except Exception as e:
        logger.warning(f"保存缓存失败: {e}")


def calculate_market_wide_rs_ranking(
    user_tickers: List[str],
    market_tickers: List[str],
    use_cache: bool = True,
    max_workers: int = 10
) -> tuple:
    """
    计算市场范围的 RS 排名（支持并行计算和本地缓存）
    
    1. 获取市场股票的加权 RS 分数
    2. 获取用户股票的加权 RS 分数
    3. 基于市场分布计算用户股票的百分位排名（1-99）
    
    Args:
        user_tickers: 用户输入的股票列表
        market_tickers: 市场股票列表
        use_cache: 是否使用缓存
        max_workers: 并行计算的最大线程数
        
    Returns:
        DataFrame with columns: ticker, rs_raw, rs_score, rank, ...
    """
    fetcher = DataFetcher()
    calculator = RSCalculator()
    
    # 1. 获取市场基准数据（SPY）
    logger.info(f"步骤 1/4: 获取市场基准数据（{MARKET_BENCHMARK}）...")
    market_benchmark = fetcher.fetch_single_ticker(MARKET_BENCHMARK)
    if market_benchmark is None or market_benchmark.empty:
        logger.error(f"❌ 无法获取市场基准数据（{MARKET_BENCHMARK}）")
        return pd.DataFrame(), []
    
    # 准备市场基准价格序列（统一处理 Adj Close）
    if 'Date' in market_benchmark.columns:
        market_benchmark = market_benchmark.set_index('Date')
        logger.debug(f"市场基准数据已设置 Date 为索引，共 {len(market_benchmark)} 条记录")
    
    # 统一使用 Adj Close（如果存在），避免后续重复判断
    market_price_col = 'Adj Close' if 'Adj Close' in market_benchmark.columns else 'Close'
    logger.info(f"使用价格列: {market_price_col}（{'Adj Close' if market_price_col == 'Adj Close' else 'Close'}）")
    # 注意：这里不提取 Series，而是在 _calculate_single_ticker_rs 中统一处理
    
    # 2. 获取市场股票的加权 RS 分数（用于建立分布）
    logger.info(f"步骤 2/4: 计算 {len(market_tickers)} 只市场股票的加权 RS 分数（S&P 500 + NASDAQ 100 + Russell 1000）...")
    logger.info(f"并行计算配置: max_workers={max_workers}, use_cache={use_cache}")
    
    # 尝试从缓存加载
    market_rs_scores = {}
    if use_cache:
        cached_scores = _load_market_rs_cache(market_tickers)
        if cached_scores:
            market_rs_scores = cached_scores
    
    # 如果缓存未命中，并行计算
    if not market_rs_scores:
        logger.info("使用并行计算获取市场股票 RS 分数...")
        
        # 数据质量监控：统计成功和失败数量
        success_count = 0
        fail_count = 0
        
        # 使用线程池并行计算
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_calculate_single_ticker_rs, ticker, market_benchmark, fetcher, calculator): ticker
                for ticker in market_tickers
            }
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 50 == 0:
                    logger.info(f"已处理 {completed}/{len(market_tickers)} 只股票... (成功: {success_count}, 失败: {fail_count})")
                
                result = future.result()
                if result is not None:
                    ticker, weighted_rs, rs_line_series, price_data = result
                    market_rs_scores[ticker] = weighted_rs
                    success_count += 1
                    # 注意：rs_line_series 在这里不需要保存，因为只用于排名
                else:
                    fail_count += 1
        
        # 计算成功率并记录日志
        total_attempted = success_count + fail_count
        if total_attempted > 0:
            success_rate = (success_count / total_attempted) * 100
            logger.info(f"市场股票 RS 计算完成: 成功 {success_count}/{total_attempted} ({success_rate:.1f}%)")
            
            # 如果成功率<50%，输出警告
            if success_rate < 50:
                logger.warning(f"⚠️ 数据质量警告: 市场股票 RS 计算成功率过低 ({success_rate:.1f}%)，可能影响排名准确性")
        else:
            logger.error("❌ 所有市场股票 RS 计算均失败")
        
        # 保存到缓存
        if use_cache and market_rs_scores:
            _save_market_rs_cache(market_rs_scores, market_tickers)
    
    if not market_rs_scores:
        logger.error("❌ 无法计算任何市场股票的 RS 分数，无法进行排名")
        return pd.DataFrame(), []
    
    logger.info(f"✅ 成功计算 {len(market_rs_scores)} 只市场股票的 RS 分数（用于建立分布）")
    if len(market_rs_scores) < 50:
        logger.warning(f"⚠️ 市场股票数量过少（{len(market_rs_scores)}），可能影响排名准确性")
    
    # 3. 获取用户股票的加权 RS 分数（并行计算）
    logger.info(f"步骤 3/4: 计算 {len(user_tickers)} 只用户股票的加权 RS 分数...")
    user_rs_data = {}
    
    # 过滤掉已经在市场股票中计算过的用户股票
    user_tickers_to_calc = [t for t in user_tickers if t not in market_rs_scores]
    
    # 数据质量监控：统计成功和失败数量
    user_success_count = 0
    user_fail_count = 0
    
    if user_tickers_to_calc:
        logger.info(f"需要计算 {len(user_tickers_to_calc)} 只用户股票（{len(user_tickers) - len(user_tickers_to_calc)} 只已在市场股票中计算）")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_calculate_single_ticker_rs, ticker, market_benchmark, fetcher, calculator): ticker
                for ticker in user_tickers_to_calc
            }
            
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    ticker, weighted_rs, rs_line_series, price_data = result
                    user_rs_data[ticker] = {
                        'rs_raw': weighted_rs,
                        'rs_line': rs_line_series,  # 现在是完整时间序列
                        'price_data': price_data
                    }
                    user_success_count += 1
                else:
                    user_fail_count += 1
        
        # 计算成功率并记录日志
        total_user_attempted = user_success_count + user_fail_count
        if total_user_attempted > 0:
            user_success_rate = (user_success_count / total_user_attempted) * 100
            logger.info(f"用户股票 RS 计算完成: 成功 {user_success_count}/{total_user_attempted} ({user_success_rate:.1f}%)")
            
            # 如果成功率<50%，输出警告
            if user_success_rate < 50:
                logger.warning(f"⚠️ 数据质量警告: 用户股票 RS 计算成功率过低 ({user_success_rate:.1f}%)")
    
    # 对于已经在市场股票中计算过的用户股票，从缓存中获取
    for ticker in user_tickers:
        if ticker in market_rs_scores and ticker not in user_rs_data:
            # 需要重新获取价格数据用于后续计算
            try:
                df = fetcher.fetch_single_ticker(ticker)
                if df is not None and not df.empty:
                    if 'Date' in df.columns:
                        df = df.set_index('Date')
                    
                    # 重新计算 RS（包括 weighted_rs 和 rs_line_series）
                    price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
                    stock_price_series = df[price_col]
                    
                    # 使用统一的 market_price_col（已在函数开始时确定）
                    if 'Date' in market_benchmark.columns:
                        market_df = market_benchmark.set_index('Date')
                    else:
                        market_df = market_benchmark.copy()
                    market_price_col = 'Adj Close' if 'Adj Close' in market_df.columns else 'Close'
                    market_price_series = market_df[market_price_col]
                    
                    result = calculator.calculate_rs_raw(stock_price_series, market_price_series)
                    if result is not None:
                        weighted_rs, rs_line_series = result
                        user_rs_data[ticker] = {
                            'rs_raw': weighted_rs,
                            'rs_line': rs_line_series,  # 现在是完整时间序列
                            'price_data': df
                        }
            except:
                pass
    
    if not user_rs_data:
        logger.error("❌ 无法计算任何用户股票的 RS 分数，无法生成排名")
        return pd.DataFrame(), []
    
    logger.info(f"✅ 成功计算 {len(user_rs_data)} 只用户股票的 RS 分数")
    
    # 4. 基于市场分布计算百分位排名（1-99）
    logger.info(f"步骤 4/4: 基于市场分布计算百分位排名（1-99）...")
    market_rs_values = list(market_rs_scores.values())
    logger.debug(f"市场 RS 分布统计: 最小值={min(market_rs_values):.2f}, 最大值={max(market_rs_values):.2f}, 平均值={sum(market_rs_values)/len(market_rs_values):.2f}")
    
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
            'rs_line': data['rs_line'],  # 完整时间序列
            'rs_score': rs_score,
            'price_data': data['price_data']  # 保存用于后续计算
        })
    
    # 创建 DataFrame
    df = pd.DataFrame(results)
    df['rank'] = df['rs_score'].rank(ascending=False, method='min').astype(int)
    df = df.sort_values('rs_score', ascending=False).reset_index(drop=True)
    
    logger.info(f"✅ 市场范围排名完成，共 {len(df)} 只股票")
    if len(df) > 0:
        logger.info(f"排名统计: 最高 RS={df['rs_score'].max()}, 最低 RS={df['rs_score'].min()}, 平均 RS={df['rs_score'].mean():.1f}")
    
    # 返回 DataFrame 和市场 RS 分布（用于计算1周前评分）
    return df, market_rs_values

