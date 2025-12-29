# 美股 RS 相对强度排名系统

一个完整的 Python 程序，用于自动计算和排名美股的 Relative Strength (RS) 指标，基于 IBD (Investor's Business Daily) 的经典排名方法。

## 功能特性

- ✅ 自动从 yfinance 获取美股历史价格数据
- ✅ 计算 IBD 风格的 RS 相对强度指标（252 交易日周期）
- ✅ 将 RS 原始值映射为 1-99 的排名分数
- ✅ 生成 CSV 排名报告和控制台输出
- ✅ 支持每日自动更新（定时任务）
- ✅ 完善的异常处理和数据验证
- ✅ 模块化设计，易于扩展

## 系统架构

```
rs_system/
│
├── config.py          # 股票列表、参数配置
├── data_fetcher.py    # 数据获取模块（yfinance）
├── rs_calculator.py   # RS 计算模块
├── ranker.py          # 排名与标准化（1-99）
├── reporter.py        # 导出 CSV / 打印结果
├── scheduler.py       # 自动更新逻辑
├── main.py            # 程序入口
└── __init__.py

output/                # 输出目录（自动创建）
├── rs_rankings.csv    # 排名结果 CSV
└── rs_system.log      # 日志文件
```

## 安装步骤

### 1. 克隆或下载项目

```bash
cd E:\PythonFile\RS
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `yfinance`: 股票数据获取
- `pandas`: 数据处理
- `numpy`: 数值计算
- `schedule`: 任务调度

### 3. 验证安装

```bash
python -m rs_system.main --help
```

## 使用方法

### 方式一：执行一次（推荐首次使用）

```bash
python -m rs_system.main --mode once
```

或者直接运行：

```bash
python -m rs_system.main
```

### 方式二：自定义股票列表

```bash
python -m rs_system.main --tickers AAPL MSFT GOOGL AMZN TSLA
```

### 方式三：定时自动更新

```bash
# 每天 16:00（美东时间）自动执行
python -m rs_system.main --mode schedule

# 自定义执行时间（例如每天 17:00）
python -m rs_system.main --mode schedule --time 17:00
```

### 方式四：仅生成数据，不打印报告

```bash
python -m rs_system.main --no-report
```

## 输出结果

### 1. CSV 文件 (`output/rs_rankings.csv`)

包含以下字段：
- `ticker`: 股票代码
- `rs_raw`: RS 原始值（百分比）
- `rs_score`: RS 排名分数（1-99）
- `rank`: 排名（1 为最高）

示例：
```csv
ticker,rs_raw,rs_score,rank
NVDA,45.23,95,1
AAPL,32.15,88,2
MSFT,28.76,85,3
...
```

### 2. 控制台输出

程序会打印：
- 统计信息（总股票数、RS 分数范围、平均值等）
- RS Top 20 股票列表
- RS Bottom 5 股票列表

### 3. 日志文件 (`output/rs_system.log`)

记录详细的执行日志，包括：
- 数据获取进度
- RS 计算过程
- 错误和警告信息

## RS 计算逻辑

### 公式

```
RS_raw = (Close_today / Close_252_days_ago - 1) × 100
```

### 排名映射

1. 计算所有股票的 RS_raw 值
2. 对 RS_raw 进行百分位排名（0-1）
3. 映射到 1-99 区间：
   ```
   rs_score = 1 + (percentile × 98)
   ```

### 数据要求

- 需要至少 262 个交易日的历史数据
- 自动处理缺失数据和异常值
- 数据不足的股票会被跳过

## 配置说明

编辑 `rs_system/config.py` 可以修改：

- **股票列表**: 修改 `DEFAULT_TICKERS` 或设置 `TICKER_LIST_FILE`
- **计算周期**: 修改 `LOOKBACK_PERIOD`（默认 252 交易日）
- **输出目录**: 修改 `OUTPUT_DIR`
- **调度时间**: 修改 `SCHEDULE_TIME`

## 进阶功能（预留接口）

系统已预留以下扩展接口，可根据需要实现：

1. **多周期加权 RS** (`rs_calculator.py` 中的 `calculate_multi_period_rs`)
2. **实时数据源切换** (替换 `data_fetcher.py` 中的数据源)
3. **Web API / Streamlit 可视化** (新增模块)
4. **技术指标过滤** (如 50 日线过滤)

## 常见问题

### Q: 数据获取失败怎么办？

A: 
- 检查网络连接
- yfinance 可能因请求频率限制而失败，程序会自动重试和跳过
- 查看日志文件了解详细错误

### Q: 如何添加更多股票？

A: 
- 方法1: 修改 `config.py` 中的 `DEFAULT_TICKERS`
- 方法2: 创建股票列表文件，设置 `TICKER_LIST_FILE` 环境变量
- 方法3: 使用命令行参数 `--tickers`

### Q: 如何实现每周更新？

A: 修改 `scheduler.py`，使用 `schedule.every().week.at(time_str).do(...)`

### Q: 可以计算 A 股吗？

A: yfinance 支持部分 A 股（需要添加 `.SS` 或 `.SZ` 后缀），但本系统主要针对美股设计。

## 性能说明

- 默认股票列表（约 40 只）: 约 1-2 分钟
- S&P 500 全量（500 只）: 约 10-15 分钟（受网络影响）

建议：
- 首次使用先用小列表测试
- 批量获取时程序会自动控制请求频率

## 许可证

MIT License

## 作者

Quantitative Engineer

## 更新日志

### v1.0.0 (2024)
- 初始版本
- 实现基础 RS 计算和排名功能
- 支持自动更新调度

