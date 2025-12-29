"""
配置文件：股票列表、参数配置
"""
import os

# ==================== 股票列表配置 ====================
# 默认使用 S&P 500 股票列表（部分示例，实际使用时可以扩展）
# 也可以从文件读取或使用 API 获取完整列表
DEFAULT_TICKERS = [
    # 科技股
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
    # 金融股
    'JPM', 'BAC', 'WFC', 'GS', 'MS',
    # 消费股
    'WMT', 'HD', 'MCD', 'NKE', 'SBUX',
    # 医疗股
    'JNJ', 'PFE', 'UNH', 'ABT', 'TMO',
    # 工业股
    'BA', 'CAT', 'GE', 'HON', 'UPS',
    # 能源股
    'XOM', 'CVX', 'SLB', 'COP', 'EOG',
    # 通信股
    'VZ', 'T', 'CMCSA', 'DIS', 'NFLX',
    # 其他
    'BRK.B', 'V', 'MA', 'PG', 'KO'
]

# 从环境变量或文件读取股票列表的路径（可选）
TICKER_LIST_FILE = os.getenv('TICKER_LIST_FILE', None)

# ==================== RS 计算参数 ====================
# 计算周期：252 个交易日 ≈ 12 个月
LOOKBACK_PERIOD = 252

# 未来扩展：多周期加权（暂未实现）
# MULTI_PERIOD_WEIGHTS = {
#     252: 0.6,  # 12个月权重
#     126: 0.3,  # 6个月权重
#     63: 0.1    # 3个月权重
# }

# ==================== 数据源配置 ====================
# 使用 yfinance，默认参数
YFINANCE_PERIOD = "2y"  # 获取2年数据以确保有足够的历史数据
YFINANCE_INTERVAL = "1d"

# 数据获取超时设置
DATA_FETCH_TIMEOUT = 30  # 秒

# SSL 验证设置（如果遇到证书问题，可以设置为 False）
VERIFY_SSL = False  # 设置为 False 可跳过 SSL 证书验证

# 批量获取时的批次大小（避免请求过多）
BATCH_SIZE = 50

# ==================== 输出配置 ====================
OUTPUT_DIR = "output"
RANKINGS_CSV = os.path.join(OUTPUT_DIR, "rs_rankings.csv")
LOG_FILE = os.path.join(OUTPUT_DIR, "rs_system.log")

# 控制台输出 Top N
TOP_N_DISPLAY = 20

# ==================== 调度配置 ====================
# 默认运行时间（美东时间，交易日）
SCHEDULE_TIME = "16:00"  # 市场收盘后
SCHEDULE_TIMEZONE = "America/New_York"

# ==================== 数据质量要求 ====================
# 最小数据点要求（如果数据不足，跳过该股票）
MIN_DATA_POINTS = LOOKBACK_PERIOD + 10  # 需要至少262个数据点

# 缺失数据处理
MISSING_DATA_THRESHOLD = 0.1  # 允许10%的数据缺失

