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
    解析单个 Stooq 数据文件
    - 列名映射: <DATE> -> Date, <CLOSE> -> Adj Close
    - 日期格式: YYYYMMDD -> datetime
    - 忽略成交量为 0 的行
    """
    try:
        df = pd.read_csv(file_path)
        
        # 1. 列名映射与检查
        required_cols = {'<DATE>', '<CLOSE>'}
        if not required_cols.issubset(df.columns):
            logger.warning(f"文件 {os.path.basename(file_path)} 缺少必要列: {required_cols - set(df.columns)}")
            return None
            
        df.rename(columns={
            '<DATE>': 'Date',
            '<CLOSE>': 'Adj Close', # 为了兼容性，我们将 CLOSE 视为 Adj Close
            '<OPEN>': 'Open',
            '<HIGH>': 'High',
            '<LOW>': 'Low',
            '<VOL>': 'Volume',
            '<TICKER>': 'Ticker' # 保留 Ticker 列
        }, inplace=True)

        # 2. 日期格式转换
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
        
        # 3. 过滤成交量为 0 的异常数据点 (Stooq 特有)
        if 'Volume' in df.columns:
            initial_rows = len(df)
            df = df[df['Volume'] > 0].copy()
            if len(df) < initial_rows:
                logger.debug(f"{os.path.basename(file_path)}: 移除了 {initial_rows - len(df)} 行成交量为 0 的数据")

        # 4. 处理 Ticker 后缀
        if 'Ticker' in df.columns:
            df['Ticker'] = df['Ticker'].str.replace('.US', '', regex=False)

        # 只保留需要的列
        final_cols = ['Date', 'Open', 'High', 'Low', 'Adj Close', 'Volume']
        df = df[[col for col in final_cols if col in df.columns]]
        
        return df
        
    except Exception as e:
        logger.error(f"解析 Stooq 文件失败 {file_path} - {type(e).__name__}: {e}")
        return None

def load_stooq_data_for_ticker(ticker: str, data_dir: str) -> Optional[pd.DataFrame]:
    """
    为单个股票加载 Stooq 数据。
    """
    # 查找 .US.txt 或 .US.csv 文件
    base_path = os.path.join(data_dir, f"{ticker.upper()}.US")
    txt_path = f"{base_path}.txt"
    csv_path = f"{base_path}.csv"

    file_path = None
    if os.path.exists(txt_path):
        file_path = txt_path
    elif os.path.exists(csv_path):
        file_path = csv_path
    
    if not file_path:
        logger.debug(f"{ticker}: 在 {data_dir} 中未找到 Stooq 数据文件")
        return None

    # 解析本地 Stooq 文件
    df = parse_stooq_file(file_path)
    if df is None or df.empty:
        return None

    logger.debug(f"{ticker}: 成功从 {os.path.basename(file_path)} 加载 {len(df)} 条本地数据")

    # 增量补丁更新逻辑
    from rs_system.config import STOOQ_DATA_PATCH
    if STOOQ_DATA_PATCH:
        from datetime import datetime, timedelta
        import yfinance as yf

        last_date = df['Date'].max()
        today = datetime.now()

        # 如果数据不是最新的 (至少差一个交易日)
        if last_date.date() < today.date() - timedelta(days=1):
            start_date = last_date + timedelta(days=1)
            logger.info(f"{ticker}: 本地数据截止于 {last_date.date()}，尝试从 yfinance 获取自 {start_date.date()} 的增量数据...")
            
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
                    
                    # 准备要追加的数据 (Stooq 格式)
                    patch_to_append = patch_df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
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
                    
                    logger.info(f"{ticker}: 成功追加 {len(patch_df)} 条新数据到 {os.path.basename(file_path)}")

                    # 准备合并到当前 DataFrame (yfinance 格式)
                    patch_df.rename(columns={'Close': 'Adj Close'}, inplace=True)
                    final_cols = ['Date', 'Open', 'High', 'Low', 'Adj Close', 'Volume']
                    patch_df_filtered = patch_df[[col for col in final_cols if col in patch_df.columns]]
                    
                    df = pd.concat([df, patch_df_filtered], ignore_index=True).sort_values(by='Date').reset_index(drop=True)
                    logger.debug(f"{ticker}: 返回合并后的数据，共 {len(df)} 条")

            except Exception as e:
                logger.warning(f"{ticker}: yfinance 增量更新失败 - {type(e).__name__}: {e}")

    return df

