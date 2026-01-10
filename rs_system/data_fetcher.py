"""
数据获取模块：支持本地 Stooq 和 yfinance 数据源
"""
import yfinance as yf
import pandas as pd
import time
from typing import List, Dict, Optional
import logging
import ssl
import urllib3
import os
import pickle
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from rs_system.config import (
    DATA_SOURCE_MODE,
    STOOQ_DATA_DIR,
    YFINANCE_PERIOD,
    YFINANCE_INTERVAL,
    DATA_FETCH_TIMEOUT,
    MIN_DATA_POINTS,
    MISSING_DATA_THRESHOLD,
    VERIFY_SSL
)
from rs_system.stooq_data_loader import load_stooq_data_for_ticker

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '.cache')
os.makedirs(CACHE_DIR, exist_ok=True)

class DataFetcher:
    """股票数据获取器"""
    
    def __init__(self):
        self.price_cache = {}  # 内存缓存：价格数据
        self.meta_cache = {}   # 内存缓存：元数据
        if not VERIFY_SSL:
            try:
                ssl._create_default_https_context = ssl._create_unverified_context
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                logger.info("已禁用 SSL 证书验证（仅用于解决证书问题）")
            except Exception as e:
                logger.warning(f"设置 SSL 上下文失败: {e}")

    def fetch_single_ticker(self, ticker: str, retry_count: int = 2) -> Optional[pd.DataFrame]:
        """
        获取单个股票的历史数据。
        根据 config.DATA_SOURCE_MODE 决定数据源:
        - 'local_stooq': 优先从本地 Stooq 文件加载，失败则回退到 yfinance。
        - 'yfinance': 直接使用 yfinance。
        """
        # 模式1: Stooq 本地优先
        if DATA_SOURCE_MODE == 'local_stooq':
            df = load_stooq_data_for_ticker(ticker, STOOQ_DATA_DIR)
            if df is not None and not df.empty:
                logger.debug(f"{ticker}: 成功使用本地 Stooq 数据源")
                return df
            else:
                logger.info(f"{ticker}: 本地 Stooq 数据未找到或加载失败，回退到 yfinance")

        # 模式2: yfinance (或 Stooq 回退)
        logger.debug(f"{ticker}: 正在从 yfinance 获取数据...")
        df = None
        last_error = None
        
        for attempt in range(retry_count):
            try:
                df = yf.download(
                    ticker,
                    period=YFINANCE_PERIOD,
                    interval=YFINANCE_INTERVAL,
                    timeout=DATA_FETCH_TIMEOUT,
                    threads=False,
                    progress=False,
                    verify=False  # 强制跳过 SSL 证书验证
                )
                if isinstance(df.columns, pd.MultiIndex):
                    df = df.droplevel(0, axis=1)
                
                if df is not None and not df.empty:
                    break
                elif attempt < retry_count - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
            except Exception as e:
                last_error = e
                if attempt < retry_count - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    logger.error(f"{ticker}: 获取数据失败（已重试 {retry_count} 次）- {type(e).__name__}: {e}")
                    return None
        
        if df is None or df.empty:
            if last_error:
                logger.warning(f"{ticker}: 获取价格数据失败 - {last_error}")
            else:
                logger.warning(f"{ticker}: 价格数据为空")
            return None
        
        df.reset_index(inplace=True)
        if len(df) < MIN_DATA_POINTS:
            logger.debug(f"{ticker}: 数据点不足 ({len(df)} < {MIN_DATA_POINTS})")
            return None
        
        missing_ratio = df['Close'].isna().sum() / len(df)
        if missing_ratio > MISSING_DATA_THRESHOLD:
            logger.debug(f"{ticker}: 缺失数据过多 ({missing_ratio:.2%})")
            return None
        
        df['Close'] = df['Close'].ffill().bfill()
        df['Adj Close'] = df['Adj Close'].ffill().bfill()
        
        logger.debug(f"{ticker}: 成功获取 {len(df)} 条价格数据")
        return df

    def _fetch_single_metadata(self, ticker: str) -> Dict:
        """获取单个股票的元数据（用于并行处理）"""
        if ticker in self.meta_cache:
            return self.meta_cache[ticker]
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.get_info() or {}
            
            meta = {
                'ticker': ticker,
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'marketCap': info.get('marketCap'),
                'trailingEps': info.get('trailingEps'),
                'revenueGrowth': info.get('revenueGrowth')
            }
            self.meta_cache[ticker] = meta
            return meta
        except Exception as e:
            logger.debug(f"{ticker}: 获取元数据失败 - {type(e).__name__}: {str(e)}")
            return {'ticker': ticker, 'sector': None, 'industry': None, 'marketCap': None, 'trailingEps': None, 'revenueGrowth': None}

    def fetch_multiple_metadata(self, tickers: List[str], max_workers: int = 10) -> pd.DataFrame:
        """
        并行获取多只股票的元数据，并使用磁盘缓存。
        """
        cache_file = os.path.join(CACHE_DIR, 'metadata_cache.pkl')
        
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                cache_time = cached_data.get('timestamp')
                cached_df = cached_data.get('data')
                
                if cache_time and (datetime.now() - cache_time) < timedelta(hours=24):
                    logger.info(f"从磁盘缓存加载 {len(cached_df)} 条元数据")
                    return cached_df[cached_df['ticker'].isin(tickers)]
        except Exception as e:
            logger.warning(f"加载元数据缓存失败: {e}")

        logger.info(f"开始并行获取 {len(tickers)} 只股票的元数据...")
        all_meta = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._fetch_single_metadata, ticker): ticker for ticker in tickers}
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 50 == 0:
                    logger.info(f"已获取 {completed}/{len(tickers)} 只股票的元数据...")
                all_meta.append(future.result())
        
        meta_df = pd.DataFrame(all_meta)
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump({'timestamp': datetime.now(), 'data': meta_df}, f)
            logger.info(f"元数据已保存到磁盘缓存 ({len(meta_df)} 条)")
        except Exception as e:
            logger.warning(f"保存元数据缓存失败: {e}")
            
        return meta_df
