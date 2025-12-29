# 快速启动指南

## 第一步：安装依赖

```bash
pip install -r requirements.txt
```

## 第二步：运行测试（推荐首次使用）

```bash
python test_rs_system.py
```

这将使用5只股票进行快速测试，验证系统是否正常工作。

## 第三步：正式运行

### 方式1：执行一次（默认模式）

```bash
python -m rs_system.main
```

### 方式2：自定义股票列表

```bash
python -m rs_system.main --tickers AAPL MSFT GOOGL AMZN TSLA
```

### 方式3：定时自动更新

```bash
# 每天16:00自动执行
python -m rs_system.main --mode schedule

# 自定义时间（例如每天17:00）
python -m rs_system.main --mode schedule --time 17:00
```

## 输出文件

运行后，会在 `output/` 目录下生成：

- `rs_rankings.csv` - 排名结果（包含所有股票）
- `rs_system.log` - 详细日志

## 查看结果

打开 `output/rs_rankings.csv` 查看完整排名，或查看控制台输出的 Top 20。

## 常见问题

**Q: 提示缺少模块？**
A: 确保已安装所有依赖：`pip install -r requirements.txt`

**Q: 数据获取失败？**
A: 检查网络连接，yfinance 需要访问互联网。某些股票可能暂时无法获取数据，程序会自动跳过。

**Q: 如何修改股票列表？**
A: 编辑 `rs_system/config.py` 中的 `DEFAULT_TICKERS`，或使用 `--tickers` 参数。

## 下一步

- 查看 `README.md` 了解详细功能
- 修改 `rs_system/config.py` 自定义配置
- 查看 `output/rs_system.log` 了解运行详情

