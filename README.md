# 美股 RS 相对强度排名系统

一个完整的 Python 程序，用于自动计算和排名美股的 Relative Strength (RS) 指标，**基于 IBD (Investor's Business Daily) 的经典排名方法**。

## 功能特性

- ✅ **IBD 风格 RS Rating**：相对于市场基准（SPY）的加权相对强度计算
- ✅ **加权机制**：过去 12 个月，近期权重更高（最近 3 个月权重 40%）
- ✅ **RS Line 计算**：股价/市场基准比率，用于识别领先股票
- ✅ **百分位排名**：1-99 分排名系统，符合 IBD 标准
- ✅ 自动从 yfinance 获取美股历史价格数据
- ✅ 生成 CSV 排名报告和控制台输出
- ✅ **Streamlit Web 界面**：可视化排名结果
- ✅ 支持每日自动更新（定时任务）
- ✅ 完善的异常处理和数据验证
- ✅ 模块化设计，易于扩展

## 系统架构

```
rs_system/
│
├── config.py          # 股票列表、IBD 参数配置
├── data_fetcher.py    # 数据获取模块（yfinance）
├── rs_calculator.py   # IBD 风格 RS 计算模块
├── ranker.py          # 排名与标准化（1-99）
├── reporter.py        # 导出 CSV / 打印结果
├── scheduler.py       # 自动更新逻辑
├── main.py            # 程序入口
├── app.py             # Streamlit Web 界面
└── __init__.py

output/                # 输出目录（自动创建）
├── rs_rankings.csv    # 排名结果 CSV
└── rs_system.log      # 日志文件
```

## 安装步骤

### 1. 克隆或下载项目

```bash
git clone <your-repo-url>
cd RS
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `yfinance`: 股票数据获取
- `pandas`: 数据处理
- `numpy`: 数值计算
- `streamlit`: Web 界面
- `schedule`: 任务调度

### 3. 验证安装

```bash
python -m rs_system.main --help
```

## 使用方法

### 方式一：Streamlit Web 界面（推荐）

```bash
streamlit run rs_system/app.py
```

在浏览器中打开显示的 URL（通常是 `http://localhost:8501`），即可使用可视化界面。

### 方式二：命令行执行

```bash
# 执行一次
python -m rs_system.main

# 或使用模式参数
python -m rs_system.main --mode once
```

### 方式三：自定义股票列表

```bash
python -m rs_system.main --tickers AAPL MSFT GOOGL AMZN TSLA
```

### 方式四：定时自动更新

```bash
# 每天 16:00（美东时间）自动执行
python -m rs_system.main --mode schedule

# 自定义执行时间（例如每天 17:00）
python -m rs_system.main --mode schedule --time 17:00
```

### 方式五：仅生成数据，不打印报告

```bash
python -m rs_system.main --no-report
```

## 输出结果

### 1. CSV 文件 (`output/rs_rankings.csv`)

包含以下字段：
- `ticker`: 股票代码
- `rs_raw`: 加权 RS 值（相对于市场基准）
- `rs_line`: RS Line 值（股价/市场基准比率）
- `rs_score`: RS 排名分数（1-99）
- `rank`: 排名（1 为最高）

示例：
```csv
ticker,rs_raw,rs_line,rs_score,rank
NVDA,12.45,2.3456,95,1
AAPL,8.32,1.8765,88,2
MSFT,6.21,1.5432,85,3
...
```

### 2. 控制台输出

程序会打印：
- 统计信息（总股票数、RS 分数范围、平均值等）
- RS Top 20 股票列表（包含 RS Line）
- RS Bottom 5 股票列表

### 3. 日志文件 (`output/rs_system.log`)

记录详细的执行日志，包括：
- 数据获取进度
- RS 计算过程
- 错误和警告信息

## RS 计算逻辑（IBD 风格）

### 核心原理

本系统实现了 **IBD (Investor's Business Daily) 风格的 RS Rating**，与简单的价格涨幅排名不同：

1. **相对于市场基准**：不是计算股票自身的涨幅，而是计算相对于市场基准（SPY）的表现
2. **加权计算**：过去 12 个月的表现，但近期权重更高
3. **百分位排名**：将所有股票的加权 RS 值进行百分位排名，映射到 1-99 分

### 计算公式

#### 1. 各周期收益率计算

```
股票收益率_3M = (当前价格 / 3个月前价格 - 1) × 100
股票收益率_6M = (当前价格 / 6个月前价格 - 1) × 100
股票收益率_9M = (当前价格 / 9个月前价格 - 1) × 100
股票收益率_12M = (当前价格 / 12个月前价格 - 1) × 100

市场收益率_3M = (当前SPY价格 / 3个月前SPY价格 - 1) × 100
市场收益率_6M = (当前SPY价格 / 6个月前SPY价格 - 1) × 100
市场收益率_9M = (当前SPY价格 / 9个月前SPY价格 - 1) × 100
市场收益率_12M = (当前SPY价格 / 12个月前SPY价格 - 1) × 100
```

#### 2. 加权相对强度计算

```
加权 RS = Σ((股票收益率_i - 市场收益率_i) × 权重_i)

权重配置：
- 最近 3 个月：40%  （最重要）
- 最近 6 个月：25%
- 最近 9 个月：20%
- 过去 12 个月：15%
```

#### 3. RS Line 计算

```
RS Line = 当前股价 / 当前市场基准价格（SPY）
```

RS Line 用于识别领先股票：当股价还在盘整，但 RS Line 率先创新高时，是较好的买入信号。

#### 4. 百分位排名（1-99 分）

```
1. 计算所有股票的加权 RS 值
2. 对加权 RS 进行百分位排名（0-1）
3. 映射到 1-99 区间：
   rs_score = 1 + (percentile × 98)
```

### 选股建议（基于 IBD 原则）

- **RS 80+**：最低门槛，只关注 RS 80 以上的股票
- **RS 90+**：领头羊股票，重点关注
- **RS Line 先行**：当股价盘整但 RS Line 创新高时，是较好的买入信号
- **避免 RS 70 以下**：这些股票相对强度较弱，通常不是好的选择

### 数据要求

- 需要至少 262 个交易日的历史数据（约 12 个月）
- 自动处理缺失数据和异常值
- 数据不足的股票会被跳过
- 自动获取市场基准（SPY）数据

## 配置说明

编辑 `rs_system/config.py` 可以修改：

- **股票列表**: 修改 `DEFAULT_TICKERS` 或设置 `TICKER_LIST_FILE`
- **市场基准**: 修改 `MARKET_BENCHMARK`（默认 SPY）
- **加权权重**: 修改 `RS_WEIGHTS` 字典（调整各周期权重）
- **计算周期**: 修改 `RS_PERIOD_*` 常量
- **输出目录**: 修改 `OUTPUT_DIR`
- **调度时间**: 修改 `SCHEDULE_TIME`

## Streamlit Web 界面

启动 Web 界面后，你可以：

1. **选择股票列表**：使用默认列表或自定义输入
2. **一键计算**：点击"开始计算"按钮
3. **查看排名**：实时查看 RS Top 20 和完整排名
4. **统计信息**：查看总股票数、最高/最低/平均 RS 分数
5. **下载 CSV**：一键下载排名结果

## 常见问题

### Q: 数据获取失败怎么办？

A: 
- 检查网络连接
- yfinance 可能因请求频率限制而失败，程序会自动重试和跳过
- 查看日志文件了解详细错误
- 确保能访问 `https://finance.yahoo.com`

### Q: 如何添加更多股票？

A: 
- 方法1: 修改 `config.py` 中的 `DEFAULT_TICKERS`
- 方法2: 创建股票列表文件，设置 `TICKER_LIST_FILE` 环境变量
- 方法3: 使用命令行参数 `--tickers`
- 方法4: 在 Streamlit 界面中自定义输入

### Q: RS 分数和 IBD 官方分数一致吗？

A: 
- 本系统基于 IBD 的公开计算方法实现
- 由于 IBD 未公开精确算法，可能存在细微差异
- 但核心逻辑（相对市场基准、加权、百分位排名）是一致的
- 分数趋势和排名顺序应该是可靠的

### Q: 如何实现每周更新？

A: 修改 `scheduler.py`，使用 `schedule.every().week.at(time_str).do(...)`

### Q: 可以计算 A 股吗？

A: yfinance 支持部分 A 股（需要添加 `.SS` 或 `.SZ` 后缀），但本系统主要针对美股设计。如需支持 A 股，需要修改市场基准配置。

## 性能说明

- 默认股票列表（约 40 只）: 约 1-2 分钟
- S&P 500 全量（500 只）: 约 10-15 分钟（受网络影响）

建议：
- 首次使用先用小列表测试
- 批量获取时程序会自动控制请求频率
- 使用 Streamlit 界面可以实时查看进度

## 技术栈

- **Python 3.7+**
- **yfinance**: 股票数据获取（Yahoo Finance）
- **pandas, numpy**: 数据处理和计算
- **streamlit**: Web 界面框架
- **schedule**: 任务调度

## 许可证

MIT License

## 更新日志

### v2.0.0 (2024)
- ✅ 实现真正的 IBD 风格 RS Rating 计算
- ✅ 添加市场基准（SPY）比较
- ✅ 实现加权 RS 计算（近期权重更高）
- ✅ 添加 RS Line 计算
- ✅ 添加 Streamlit Web 界面
- ✅ 更新所有相关模块和文档

### v1.0.0 (2024)
- 初始版本
- 实现基础 RS 计算和排名功能
- 支持自动更新调度

## 参考

- [Investor's Business Daily (IBD)](https://www.investors.com/)
- IBD RS Rating 计算方法（基于公开资料和反向工程）
