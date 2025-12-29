"""
数据获取模块：从 yfinance 获取股票历史价格数据
"""
import yfinance as yf
import pandas as pd
import time
from typing import List, Dict, Optional
import logging
import ssl
import urllib.request
import urllib3
import os
from rs_system.config import (
    YFINANCE_PERIOD,
    YFINANCE_INTERVAL,
    DATA_FETCH_TIMEOUT,
    BATCH_SIZE,
    MIN_DATA_POINTS,
    MISSING_DATA_THRESHOLD,
    VERIFY_SSL
)

logger = logging.getLogger(__name__)

# 尝试找到证书文件路径
def _get_cert_path():
    """尝试找到证书文件路径"""
    try:
        import certifi
        cert_path = certifi.where()
        if os.path.exists(cert_path):
            return cert_path
    except:
        pass
    return None

# 设置证书路径（优先使用 certifi 的证书）
cert_path = _get_cert_path()
if cert_path:
    os.environ['CURL_CA_BUNDLE'] = cert_path
    os.environ['REQUESTS_CA_BUNDLE'] = cert_path
    os.environ['SSL_CERT_FILE'] = cert_path
    logger.info(f"已设置证书路径: {cert_path}")
elif not VERIFY_SSL:
    # 如果禁用验证且找不到证书，清空环境变量
    os.environ['CURL_CA_BUNDLE'] = ''
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    os.environ['SSL_CERT_FILE'] = ''
    logger.warning("未找到证书文件，已禁用 SSL 验证")


class DataFetcher:
    """股票数据获取器"""
    
    def __init__(self):
        self.cache = {}  # 可选：缓存机制
        # 如果禁用 SSL 验证，设置全局 SSL 上下文和警告
        if not VERIFY_SSL:
            try:
                ssl._create_default_https_context = ssl._create_unverified_context
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                import warnings
                warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)
                logger.info("已禁用 SSL 证书验证（仅用于解决证书问题）")
            except Exception as e:
                logger.warning(f"设置 SSL 上下文失败: {e}")
    
    def fetch_single_ticker(self, ticker: str, retry_count: int = 2) -> Optional[pd.DataFrame]:
        """
        获取单个股票的历史数据
        
        Args:
            ticker: 股票代码
            retry_count: 重试次数
            
        Returns:
            DataFrame with columns: Date, Open, High, Low, Close, Volume
            如果获取失败，返回 None
        """
        # 如果禁用 SSL 验证，忽略警告
        if not VERIFY_SSL:
            import warnings
            warnings.filterwarnings('ignore', message='Unverified HTTPS request')
            warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)
        
        df = None
        last_error = None
        
        # 重试机制
        for attempt in range(retry_count):
            try:
                # 方法1：优先使用 download 函数（通常更稳定）
                try:
                    df = yf.download(
                        ticker,
                        period=YFINANCE_PERIOD,
                        interval=YFINANCE_INTERVAL,
                        timeout=DATA_FETCH_TIMEOUT,
                        progress=False,
                        show_errors=False
                    )
                    
                    # download 返回的可能是多级索引，需要处理
                    if isinstance(df.columns, pd.MultiIndex):
                        df = df.droplevel(0, axis=1)
                    
                except Exception as e1:
                    last_error = e1
                    # 方法2：如果 download 失败，尝试 Ticker.history
                    try:
                        stock = yf.Ticker(ticker)
                        df = stock.history(
                            period=YFINANCE_PERIOD,
                            interval=YFINANCE_INTERVAL,
                            timeout=DATA_FETCH_TIMEOUT
                        )
                    except Exception as e2:
                        last_error = e2
                        if attempt < retry_count - 1:
                            logger.debug(f"{ticker}: 获取失败，{0.5 * (attempt + 1)}秒后重试...")
                            time.sleep(0.5 * (attempt + 1))  # 递增延迟
                            continue
                        else:
                            logger.error(f"{ticker}: 所有方法都失败 - {e2}")
                            return None
                
                # 如果获取到数据，跳出重试循环
                if df is not None and not df.empty:
                    break
                elif attempt < retry_count - 1:
                    logger.debug(f"{ticker}: 数据为空，{0.5 * (attempt + 1)}秒后重试...")
                    time.sleep(0.5 * (attempt + 1))
                    continue
                    
            except Exception as e:
                last_error = e
                if attempt < retry_count - 1:
                    logger.debug(f"{ticker}: 获取失败，{0.5 * (attempt + 1)}秒后重试...")
                    time.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    logger.error(f"{ticker}: 获取数据失败（已重试 {retry_count} 次）- {str(e)}")
                    return None
        
        # 如果所有重试都失败
        if df is None or df.empty:
            if last_error:
                logger.error(f"{ticker}: 获取数据失败 - {last_error}")
            else:
                logger.warning(f"{ticker}: 数据为空")
            return None
        
        try:
            # 重置索引，将 Date 转为列
            df.reset_index(inplace=True)
            
            # 检查数据量是否足够
            if len(df) < MIN_DATA_POINTS:
                logger.warning(f"{ticker}: 数据点不足 ({len(df)} < {MIN_DATA_POINTS})")
                return None
            
            # 检查缺失数据比例
            missing_ratio = df['Close'].isna().sum() / len(df)
            if missing_ratio > MISSING_DATA_THRESHOLD:
                logger.warning(f"{ticker}: 缺失数据过多 ({missing_ratio:.2%})")
                return None
            
            # 填充缺失值（使用前向填充和后向填充）
            df['Close'] = df['Close'].ffill().bfill()
            
            logger.info(f"{ticker}: 成功获取 {len(df)} 条数据")
            return df
            
        except Exception as e:
            logger.error(f"{ticker}: 获取数据失败 - {str(e)}")
            return None
    
    def fetch_multiple_tickers(
        self, 
        tickers: List[str], 
        batch_size: int = BATCH_SIZE,
        delay: float = 0.1
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取多个股票的数据
        
        Args:
            tickers: 股票代码列表
            batch_size: 每批处理的股票数量
            delay: 批次之间的延迟（秒），避免请求过快
            
        Returns:
            Dict[ticker, DataFrame]
        """
        results = {}
        total = len(tickers)
        
        logger.info(f"开始获取 {total} 只股票的数据...")
        
        for i, ticker in enumerate(tickers, 1):
            df = self.fetch_single_ticker(ticker)
            if df is not None:
                results[ticker] = df
            
            # 每批之间延迟（避免请求过快）
            if i % batch_size == 0:
                logger.info(f"已处理 {i}/{total} 只股票...")
                time.sleep(delay)
            else:
                # 每个请求之间也稍微延迟
                time.sleep(0.05)
        
        logger.info(f"数据获取完成，成功获取 {len(results)}/{total} 只股票的数据")
        return results
    
    def validate_data(self, df: pd.DataFrame, ticker: str) -> bool:
        """
        验证数据质量
        
        Args:
            df: 股票数据 DataFrame
            ticker: 股票代码（用于日志）
            
        Returns:
            bool: 数据是否有效
        """
        if df is None or df.empty:
            return False
        
        if 'Close' not in df.columns:
            logger.error(f"{ticker}: 缺少 Close 列")
            return False
        
        if len(df) < MIN_DATA_POINTS:
            return False
        
        # 检查是否有足够的有效收盘价
        valid_closes = df['Close'].notna().sum()
        if valid_closes < MIN_DATA_POINTS:
            return False
        
        return True

