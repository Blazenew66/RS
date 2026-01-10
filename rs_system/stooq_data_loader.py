"""
Stooq 本地数据加载器
- 适配 Stooq.com 下载的 .txt/.csv 数据格式
- 支持 yfinance 增量补丁更新
"""
import os
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def parse_stooq_file(file_path: str) -> Optional[pd.DataFrame]:
    """
    解析单个 Stooq 数据文件，并进行健壮性检查。
    - 列名映射: <DATE> -> Date, <CLOSE> -> Adj Close
    - 日期格式: YYYYMMDD -> datetime
    - 忽略成交量为 0 的行
    """
    try:
        # 检查文件是否为空
        if os.path.getsize(file_path) == 0:
            logger.warning(f"Stooq 数据文件为空: {os.path.basename(file_path)}")
            return None

        df = pd.read_csv(file_path)
        if df.empty:
            logger.warning(f"Stooq 数据文件读取后内容为空: {os.path.basename(file_path)}")
            return None

        # 1. 列名映射与检查
        required_cols = {'<DATE>', '<CLOSE>'}
        if not required_cols.issubset(df.columns):
            logger.error(f"❌ 文件 {os.path.basename(file_path)} 缺少必要列: {required_cols - set(df.columns)}")
            return None

        df.rename(columns={
            '<DATE>': 'Date',
            '<CLOSE>': 'Adj Close',  # 为了兼容性，我们将 CLOSE 视为 Adj Close
            '<OPEN>': 'Open',
            '<HIGH>': 'High',
            '<LOW>': 'Low',
            '<VOL>': 'Volume',
            '<TICKER>': 'Ticker'
        }, inplace=True)

        # 2. 日期格式转换
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d', errors='coerce')
        # 移除无法解析的日期行
        invalid_dates = df['Date'].isna().sum()
        if invalid_dates > 0:
            logger.warning(f"{os.path.basename(file_path)}: 移除了 {invalid_dates} 行无效日期格式的数据")
            df.dropna(subset=['Date'], inplace=True)

        if df.empty:
            logger.warning(f"在处理日期后，文件 {os.path.basename(file_path)} 内容为空")
            return None

        # 3. 过滤成交量为 0 的异常数据点
        if 'Volume' in df.columns:
            initial_rows = len(df)
            df = df[df['Volume'] > 0].copy()
            if len(df) < initial_rows:
                logger.debug(f"{os.path.basename(file_path)}: 移除了 {initial_rows - len(df)} 行成交量为 0 的数据")

        # 4. 处理 Ticker 后缀
        if 'Ticker' in df.columns:
            df['Ticker'] = df['Ticker'].str.replace('.US', '', regex=False)

        # 只保留标准列
        final_cols = ['Date', 'Open', 'High', 'Low', 'Adj Close', 'Volume']
        df = df[[col for col in final_cols if col in df.columns]]

        return df

    except Exception as e:
        import traceback
        logger.error(f"❌ 解析 Stooq 文件时发生严重错误 {file_path} - {type(e).__name__}: {e}")
        logger.debug(traceback.format_exc())
        return None

def load_stooq_data_for_ticker(ticker: str, data_dir: str) -> Optional[pd.DataFrame]:
    """
    为单个股票加载 Stooq 数据，并根据需要应用 yfinance 增量补丁。
    """
    # 查找 .us.txt、.US.txt、.us.csv、.US.csv 文件（大小写不敏感）
    ticker_upper = ticker.upper()
    # 尝试多种大小写组合
    possible_paths = [
        os.path.join(data_dir, f"{ticker_upper}.US.txt"),
        os.path.join(data_dir, f"{ticker_upper}.us.txt"),
        os.path.join(data_dir, f"{ticker_upper}.US.csv"),
        os.path.join(data_dir, f"{ticker_upper}.us.csv"),
    ]

    file_path = None
    for path in possible_paths:
        if os.path.exists(path):
            file_path = path
            break

    if not file_path:
        logger.debug(f"{ticker}: 在 {data_dir} 中未找到 Stooq 数据文件，将尝试 yfinance。")
        return None

    df = parse_stooq_file(file_path)
    if df is None or df.empty:
        logger.warning(f"本地文件 {os.path.basename(file_path)} 解析失败或为空，将尝试 yfinance。")
        return None

    logger.debug(f"{ticker}: 成功从 {os.path.basename(file_path)} 加载 {len(df)} 条本地数据")

    # 增量补丁更新逻辑
    from rs_system.config import STOOQ_DATA_PATCH
    if STOOQ_DATA_PATCH:
        from datetime import datetime, timedelta
        import yfinance as yf

        last_date = df['Date'].max()
        today = datetime.now()

        if last_date.date() < today.date() - timedelta(days=1):
            start_date = last_date + timedelta(days=1)
            logger.info(f"ℹ️ {ticker}: 本地数据截止于 {last_date.date()}，尝试从 yfinance 获取自 {start_date.date()} 的增量数据...")

            try:
                patch_df = yf.download(
                    ticker,
                    start=start_date.strftime('%Y-%m-%d'),
                    end=today.strftime('%Y-%m-%d'),
                    progress=False,
                    verify=False,
                    threads=False
                )

                if not patch_df.empty:
                    patch_df.reset_index(inplace=True)

                    # 验证 yfinance 返回的数据是否包含必要列
                    required_patch_cols = {'Date', 'Open', 'High', 'Low', 'Close', 'Volume'}
                    if not required_patch_cols.issubset(patch_df.columns):
                        logger.warning(f"{ticker}: yfinance 增量数据缺少必要列，无法追加。")
                        return df # 返回原始的本地数据

                    # 准备要追加的数据 (Stooq 格式)
                    patch_to_append = patch_df[list(required_patch_cols)].copy()
                    patch_to_append.rename(columns={
                        'Date': '<DATE>',
                        'Open': '<OPEN>',
                        'High': '<HIGH>',
                        'Low': '<LOW>',
                        'Close': '<CLOSE>',
                        'Volume': '<VOL>'
                    }, inplace=True)
                    patch_to_append['<DATE>'] = patch_to_append['<DATE>'].dt.strftime('%Y%m%d')

                    # 追加到原始 Stooq 文件
                    with open(file_path, 'a', newline='') as f:
                        patch_to_append.to_csv(f, header=False, index=False)

                    logger.info(f"✅ {ticker}: 成功追加 {len(patch_df)} 条新数据到 {os.path.basename(file_path)}")

                    # 准备合并到当前 DataFrame (yfinance 格式)
                    patch_df.rename(columns={'Close': 'Adj Close'}, inplace=True)
                    final_cols = ['Date', 'Open', 'High', 'Low', 'Adj Close', 'Volume']
                    patch_df_filtered = patch_df[[col for col in final_cols if col in patch_df.columns]]

                    df = pd.concat([df, patch_df_filtered], ignore_index=True).sort_values(by='Date').reset_index(drop=True)
                    logger.debug(f"{ticker}: 返回合并后的数据，共 {len(df)} 条")

            except Exception as e:
                logger.warning(f"⚠️ {ticker}: yfinance 增量更新失败 - {type(e).__name__}: {e}")

    return df