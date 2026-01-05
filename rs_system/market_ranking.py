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
    logger.info("开始获取 NASDAQ 100 股票列表...")
    try:
        url = "https://en.wikipedia.org/wiki/NASDAQ-100"
        logger.info(f"正在从 {url} 抓取数据...")
        tables = pd.read_html(url)
        logger.info(f"成功解析 {len(tables)} 个表格")
        
        # 尝试多个可能的表格索引
        nasdaq_table = None
        for idx in [4, 3, 2, 1, 0]:
            if idx < len(tables):
                table = tables[idx]
                # 检查是否包含股票代码列
                if 'Ticker' in table.columns or 'Symbol' in table.columns or len(table.columns) > 0:
                    nasdaq_table = table
                    logger.info(f"使用表格索引 {idx}，包含 {len(table)} 行数据")
                    break
        
        if nasdaq_table is None:
            logger.warning("未找到合适的 NASDAQ 100 表格，使用第一个表格")
            nasdaq_table = tables[0] if tables else None
        
        if nasdaq_table is None:
            logger.error("无法解析 NASDAQ 100 表格")
            return []
        
        # 提取股票代码
        if 'Ticker' in nasdaq_table.columns:
            tickers = nasdaq_table['Ticker'].tolist()
            logger.info("使用 'Ticker' 列")
        elif 'Symbol' in nasdaq_table.columns:
            tickers = nasdaq_table['Symbol'].tolist()
            logger.info("使用 'Symbol' 列")
        else:
            # 尝试第一列
            tickers = nasdaq_table.iloc[:, 0].tolist()
            logger.info("使用第一列作为股票代码")
        
        # 清理和过滤
        tickers = [str(t).replace('.', '-').upper() for t in tickers if pd.notna(t)]
        tickers = [t for t in tickers if t and len(t) <= 5 and t.replace('-', '').isalnum()]  # 过滤有效股票代码
        
        logger.info(f"✅ 成功获取 NASDAQ 100 股票列表，共 {len(tickers)} 只股票")
        if len(tickers) < 50:
            logger.warning(f"⚠️ NASDAQ 100 股票数量异常少（{len(tickers)}），可能抓取失败")
        return tickers
    except Exception as e:
        logger.error(f"❌ 从 Wikipedia 获取 NASDAQ 100 列表失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return []


def get_russell1000_static_list() -> List[str]:
    """
    获取 Russell 1000 静态股票列表（作为后备方案）
    
    优先从项目根目录读取 `tickers.csv` 文件：
    - 路径：项目根目录 / tickers.csv
    - 列：优先使用名为 `ticker` 的列，否则使用第一列
    
    如果读取失败或文件不存在，则使用一个简短的硬编码列表作为兜底，
    仅用于保证系统可运行，而不是覆盖完整的 Russell 1000。
    """
    # 1. 优先从 tickers.csv 读取
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        csv_path = os.path.join(project_root, "tickers.csv")
        if os.path.exists(csv_path):
            logger.info(f"尝试从 {csv_path} 读取股票池 tickers.csv ...")
            df = pd.read_csv(csv_path)
            if df.empty:
                logger.warning("tickers.csv 文件为空，将使用兜底静态列表")
            else:
                if "ticker" in df.columns:
                    raw_tickers = df["ticker"]
                else:
                    # 使用第一列作为股票代码列
                    first_col = df.columns[0]
                    raw_tickers = df[first_col]
                tickers = [
                    str(t).strip().upper()
                    for t in raw_tickers
                    if pd.notna(t) and str(t).strip() != ""
                ]
                # 去重和基本过滤
                unique_tickers = sorted(list(set(tickers)))
                valid_tickers = [
                    t
                    for t in unique_tickers
                    if t
                    and len(t) <= 5
                    and t.replace("-", "").replace(".", "").isalnum()
                ]
                logger.info(
                    f"从 tickers.csv 读取到 {len(valid_tickers)} 只有效股票代码 "
                    "(作为 Russell 1000 静态列表)"
                )
                if len(valid_tickers) == 0:
                    logger.warning("tickers.csv 中没有解析出任何有效股票代码，将使用兜底静态列表")
                else:
                    return valid_tickers
        else:
            logger.warning(f"未找到 tickers.csv 文件（路径: {csv_path}），将使用兜底静态列表")
    except Exception as e:
        logger.warning(f"读取 tickers.csv 失败，将使用兜底静态列表 - {type(e).__name__}: {e}")
    
    # 2. 兜底：简短硬编码列表（仅用于保证系统可运行，不追求覆盖全部成分股）
    fallback_tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "BRK-B", "UNH", "XOM",
        "JNJ", "JPM", "V", "PG", "MA",
        "LLY", "HD", "COST", "AVGO", "PEP",
        "TMO", "CSCO", "WMT", "DIS", "MRK",
        "ABBV", "AMD", "INTC", "QCOM", "TXN",
        "AMAT", "LRCX", "KLAC", "NXPI", "MU",
    ]
    unique_tickers = sorted(list(set([t.upper() for t in fallback_tickers])))
    valid_tickers = [
        t
        for t in unique_tickers
        if t and len(t) <= 5 and t.replace("-", "").replace(".", "").isalnum()
    ]
    
    logger.info(
        f"使用兜底 Russell 1000 静态列表，共 {len(valid_tickers)} 只股票 "
        "(请在项目根目录提供 tickers.csv 以获得完整股票池)"
    )
    return valid_tickers


def get_combined_index_tickers() -> List[str]:
    """
    整合标普500、纳斯达克100与罗素1000指数作为基准
    移除重复标的
    
    如果在线获取失败，使用完整的 Russell 1000 静态列表作为后备
    
    Returns:
        整合后的股票代码列表（去重，至少 1000 只）
    """
    logger.info("=" * 60)
    logger.info("开始获取整合股票池（S&P 500 + NASDAQ 100 + Russell 1000）")
    logger.info("=" * 60)
    
    all_tickers = []
    
    # 1. 尝试获取 S&P 500
    logger.info("\n[步骤 1/3] 获取 S&P 500 股票列表...")
    sp500_tickers = get_sp500_tickers()
    if sp500_tickers:
        all_tickers.extend(sp500_tickers)
        logger.info(f"✅ S&P 500: 成功获取 {len(sp500_tickers)} 只股票")
    else:
        logger.warning("❌ S&P 500 获取失败，将使用静态列表")
    
    # 2. 尝试获取 NASDAQ 100
    logger.info("\n[步骤 2/3] 获取 NASDAQ 100 股票列表...")
    nasdaq100_tickers = get_nasdaq100_tickers()
    if nasdaq100_tickers:
        all_tickers.extend(nasdaq100_tickers)
        logger.info(f"✅ NASDAQ 100: 成功获取 {len(nasdaq100_tickers)} 只股票")
    else:
        logger.warning("❌ NASDAQ 100 获取失败，将使用静态列表")
    
    # 3. 始终使用完整的 Russell 1000 静态列表作为补充（确保覆盖完整）
    logger.info("\n[步骤 3/3] 添加 Russell 1000 静态列表以确保完整覆盖...")
    russell_static = get_russell1000_static_list()
    all_tickers.extend(russell_static)
    logger.info(f"✅ Russell 1000 静态列表: {len(russell_static)} 只股票")
    
    # 去重并排序
    logger.info("\n[合并阶段] 去重并过滤无效股票代码...")
    unique_tickers = sorted(list(set(all_tickers)))
    logger.info(f"去重前: {len(all_tickers)} 只，去重后: {len(unique_tickers)} 只")
    
    # 过滤掉无效的股票代码
    valid_tickers = [t for t in unique_tickers if t and len(t) <= 5 and t.replace('-', '').replace('.', '').isalnum()]
    logger.info(f"过滤后: {len(valid_tickers)} 只有效股票代码")
    
    logger.info(f"\n📊 整合后共 {len(valid_tickers)} 只唯一股票（S&P 500 + NASDAQ 100 + Russell 1000）")
    
    # 确保至少有 1000 只股票（最少要求，即使抓取失败也有1000+只）
    min_tickers = 1000
    
    # 如果在线获取失败或数量不足，始终使用静态列表补充
    if len(valid_tickers) < min_tickers:
        logger.warning(f"⚠️ 股票数量不足 {min_tickers} 只（{len(valid_tickers)}），使用静态列表补充")
        russell_static = get_russell1000_static_list()
        all_combined = list(set(valid_tickers + russell_static))
        valid_tickers = sorted(all_combined)
        logger.info(f"补充后共 {len(valid_tickers)} 只股票")
    
    # 如果仍然不足，记录警告但返回所有可用的股票
    if len(valid_tickers) < min_tickers:
        logger.warning(f"⚠️ 股票数量仍然不足 {min_tickers} 只（{len(valid_tickers)}），静态列表可能需要扩展")
    
    # 返回所有获取到的股票（移除任何数量限制，确保完整分析）
    final_tickers = valid_tickers
    
    logger.info("=" * 60)
    logger.info(f"✅ 最终使用 {len(final_tickers)} 只股票进行市场分布计算")
    logger.info(f"   目标: 至少 {min_tickers} 只，实际: {len(final_tickers)} 只")
    logger.info("=" * 60)
    
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
        # 获取股票数据
        df = fetcher.fetch_single_ticker(ticker)
        if df is None or df.empty:
            logger.warning(f"❌ {ticker}: 数据获取失败或为空")
            return None
        
        if 'Date' in df.columns:
            df = df.set_index('Date')
        
        # 使用 Adjusted Close（优先）
        price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
        if price_col not in df.columns:
            logger.warning(f"❌ {ticker}: 缺少价格列（Adj Close 和 Close 都不存在）")
            return None
        
        stock_price_series = df[price_col]
        
        # 放宽数据长度要求：至少需要 63 天（3个月）的数据，而不是 252 天
        # 这样可以包含次新股
        min_data_points = 63  # 3个月 = 63个交易日
        if len(stock_price_series) < min_data_points:
            logger.warning(f"❌ {ticker}: 数据点不足（{len(stock_price_series)} < {min_data_points}），跳过")
            return None
        
        # 检查数据质量：有效数据点应该至少占 80%
        valid_data_ratio = stock_price_series.notna().sum() / len(stock_price_series)
        if valid_data_ratio < 0.8:
            logger.warning(f"❌ {ticker}: 有效数据比例过低（{valid_data_ratio:.1%} < 80%），跳过")
            return None
        
        # 确保市场基准也使用 Adjusted Close（统一处理，避免重复判断）
        # market_benchmark 应该已经在外部统一处理过 Adj Close
        if 'Date' in market_benchmark.columns:
            market_df = market_benchmark.set_index('Date')
        else:
            market_df = market_benchmark.copy()
        
        # 统一使用 Adj Close（如果存在）
        market_price_col = 'Adj Close' if 'Adj Close' in market_df.columns else 'Close'
        if market_price_col not in market_df.columns:
            logger.warning(f"❌ {ticker}: 市场基准缺少价格列")
            return None
        
        market_price_series = market_df[market_price_col]
        
        # 计算加权 RS 和 RS Line（RS Line 现在是完整时间序列）
        result = calculator.calculate_rs_raw(stock_price_series, market_price_series)
        if result is not None:
            weighted_rs, rs_line_series = result
            logger.debug(f"✅ {ticker}: RS计算成功 (weighted_rs={weighted_rs:.2f}, rs_line长度={len(rs_line_series)}, 数据天数={len(stock_price_series)})")
            return (ticker, weighted_rs, rs_line_series, df)
        else:
            logger.warning(f"❌ {ticker}: RS计算返回 None（可能是数据对齐或计算问题）")
            return None
    except Exception as e:
        logger.warning(f"❌ {ticker}: 计算失败 - {type(e).__name__}: {str(e)}")
        import traceback
        logger.debug(f"{ticker}: 详细错误信息:\n{traceback.format_exc()}")
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
    max_workers: int = 4
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
        logger.info("=" * 60)
        logger.info(f"开始并行计算 {len(market_tickers)} 只市场股票的 RS 分数...")
        logger.info(f"并发配置: max_workers={max_workers}, 预计耗时: {len(market_tickers) / max_workers * 0.5:.1f} 秒")
        logger.info("=" * 60)
        
        # 数据质量监控：统计成功和失败数量
        success_count = 0
        fail_count = 0
        failed_tickers = []  # 记录失败的股票代码和原因
        
        # 使用线程池并行计算（添加延迟以避免请求过快）
        import time
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            futures = {}
            for idx, ticker in enumerate(market_tickers):
                future = executor.submit(_calculate_single_ticker_rs, ticker, market_benchmark, fetcher, calculator)
                futures[future] = ticker
                # 每 10 个请求添加一个小延迟，避免请求过快被拦截
                if (idx + 1) % 10 == 0:
                    time.sleep(0.1)
            
            # 处理完成的任务
            completed = 0
            for future in as_completed(futures):
                completed += 1
                ticker = futures[future]
                
                # 每处理 50 只股票输出一次进度
                if completed % 50 == 0:
                    success_rate = (success_count / completed * 100) if completed > 0 else 0
                    logger.info(f"📊 进度: {completed}/{len(market_tickers)} ({completed/len(market_tickers)*100:.1f}%) | "
                              f"成功: {success_count} | 失败: {fail_count} | 成功率: {success_rate:.1f}%")
                
                try:
                    result = future.result()
                    if result is not None:
                        ticker, weighted_rs, rs_line_series, price_data = result
                        market_rs_scores[ticker] = weighted_rs
                        success_count += 1
                        # 注意：rs_line_series 在这里不需要保存，因为只用于排名
                    else:
                        fail_count += 1
                        failed_tickers.append((ticker, "RS计算返回None"))
                except Exception as e:
                    fail_count += 1
                    failed_tickers.append((ticker, f"异常: {type(e).__name__}: {str(e)}"))
        
        # 计算成功率并记录日志
        total_attempted = success_count + fail_count
        logger.info("=" * 60)
        if total_attempted > 0:
            success_rate = (success_count / total_attempted) * 100
            logger.info(f"✅ 市场股票 RS 计算完成:")
            logger.info(f"   总尝试: {total_attempted} 只")
            logger.info(f"   成功: {success_count} 只 ({success_rate:.1f}%)")
            logger.info(f"   失败: {fail_count} 只 ({100-success_rate:.1f}%)")
            
            # 如果成功率<50%，输出警告
            if success_rate < 50:
                logger.warning(f"⚠️ 数据质量警告: 市场股票 RS 计算成功率过低 ({success_rate:.1f}%)，可能影响排名准确性")
            
            # 输出前 20 个失败的股票代码和原因
            if failed_tickers:
                logger.warning(f"\n❌ 失败的股票列表（前 20 个）:")
                for ticker, reason in failed_tickers[:20]:
                    logger.warning(f"   - {ticker}: {reason}")
                if len(failed_tickers) > 20:
                    logger.warning(f"   ... 还有 {len(failed_tickers) - 20} 只股票失败")
        else:
            logger.error("❌ 所有市场股票 RS 计算均失败")
        logger.info("=" * 60)
        
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

