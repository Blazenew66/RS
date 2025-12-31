"""
主程序入口：整合所有模块，实现完整的 RS 排名系统
"""
import logging
import sys
from datetime import datetime
from typing import List, Optional

from rs_system.config import (
    DEFAULT_TICKERS,
    TICKER_LIST_FILE,
    OUTPUT_DIR,
    LOG_FILE,
    TOP_N_DISPLAY,
    MARKET_BENCHMARK
)
from rs_system.data_fetcher import DataFetcher
from rs_system.rs_calculator import RSCalculator
from rs_system.ranker import Ranker
from rs_system.reporter import Reporter
from rs_system.scheduler import Scheduler, is_trading_day


def setup_logging():
    """配置日志系统"""
    # 确保输出目录存在
    import os
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # 配置日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 同时输出到文件和控制台
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_ticker_list() -> List[str]:
    """
    加载股票列表
    
    Returns:
        股票代码列表
    """
    tickers = DEFAULT_TICKERS.copy()
    
    # 如果配置了文件路径，尝试从文件读取
    if TICKER_LIST_FILE:
        try:
            import os
            if os.path.exists(TICKER_LIST_FILE):
                with open(TICKER_LIST_FILE, 'r', encoding='utf-8') as f:
                    file_tickers = [
                        line.strip().upper()
                        for line in f
                        if line.strip() and not line.strip().startswith('#')
                    ]
                    if file_tickers:
                        tickers = file_tickers
                        logging.info(f"从文件加载 {len(tickers)} 只股票: {TICKER_LIST_FILE}")
        except Exception as e:
            logging.warning(f"读取股票列表文件失败: {e}，使用默认列表")
    
    return tickers


def run_rs_ranking(
    tickers: Optional[List[str]] = None,
    save_csv: bool = True,
    print_report: bool = True
):
    """
    执行完整的 RS 排名流程
    
    Args:
        tickers: 股票代码列表，如果为 None 则使用配置的默认列表
        save_csv: 是否保存 CSV 文件
        print_report: 是否打印控制台报告
    """
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("开始执行 RS 排名系统")
    logger.info("=" * 80)
    
    # 1. 加载股票列表
    if tickers is None:
        tickers = load_ticker_list()
    
    logger.info(f"待处理股票数量: {len(tickers)}")
    
    # 2. 获取数据
    logger.info("步骤 1/5: 获取股票数据...")
    fetcher = DataFetcher()
    ticker_data = fetcher.fetch_multiple_tickers(tickers)
    
    if not ticker_data:
        logger.error("未能获取任何股票数据，程序终止")
        return None
    
    # 2.5. 获取市场基准数据（SPY）
    logger.info("步骤 2/5: 获取市场基准数据（{}）...".format(MARKET_BENCHMARK))
    market_data = fetcher.fetch_single_ticker(MARKET_BENCHMARK)
    
    if market_data is None or market_data.empty:
        logger.error(f"未能获取市场基准数据（{MARKET_BENCHMARK}），程序终止")
        return None
    
    logger.info(f"成功获取市场基准数据，共 {len(market_data)} 条记录")
    
    # 3. 计算 RS（IBD 风格，相对于市场基准）
    logger.info("步骤 3/5: 计算 IBD 风格 RS 原始值（相对于市场基准）...")
    calculator = RSCalculator()
    rs_raw_dict = calculator.calculate_rs_for_all(ticker_data, market_data)
    
    if not rs_raw_dict:
        logger.error("未能计算任何 RS 值，程序终止")
        return None
    
    # 4. 排名
    logger.info("步骤 4/5: 生成排名（百分位排名 1-99）...")
    ranker = Ranker()
    rankings_df = ranker.rank_rs_scores(rs_raw_dict)
    
    # 5. 生成报告
    logger.info("步骤 5/5: 生成报告...")
    reporter = Reporter()
    
    if save_csv:
        csv_path = reporter.save_to_csv(rankings_df)
        logger.info(f"CSV 文件已保存: {csv_path}")
    
    if print_report:
        reporter.print_console_report(rankings_df, top_n=TOP_N_DISPLAY)
    
    # 生成统计摘要
    stats = reporter.generate_summary_stats(rankings_df)
    logger.info(f"统计摘要: {stats}")
    
    logger.info("=" * 80)
    logger.info("RS 排名系统执行完成")
    logger.info("=" * 80)
    
    return rankings_df


def main():
    """主函数"""
    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='美股 RS 相对强度排名系统')
    parser.add_argument(
        '--mode',
        choices=['once', 'schedule'],
        default='once',
        help='运行模式: once=执行一次, schedule=定时执行'
    )
    parser.add_argument(
        '--time',
        type=str,
        default=None,
        help='定时执行时间 (格式: HH:MM，仅在 schedule 模式下有效)'
    )
    parser.add_argument(
        '--tickers',
        type=str,
        nargs='+',
        default=None,
        help='自定义股票代码列表（空格分隔）'
    )
    parser.add_argument(
        '--no-csv',
        action='store_true',
        help='不保存 CSV 文件'
    )
    parser.add_argument(
        '--no-report',
        action='store_true',
        help='不打印控制台报告'
    )
    
    args = parser.parse_args()
    
    # 准备参数
    tickers = args.tickers
    save_csv = not args.no_csv
    print_report = not args.no_report
    
    # 定义任务函数
    def task():
        run_rs_ranking(tickers=tickers, save_csv=save_csv, print_report=print_report)
    
    # 根据模式执行
    if args.mode == 'once':
        # 执行一次
        logger.info("模式: 执行一次")
        task()
    elif args.mode == 'schedule':
        # 定时执行
        logger.info("模式: 定时执行")
        scheduler = Scheduler(task)
        
        if args.time:
            scheduler.run_daily(args.time)
        else:
            from rs_system.config import SCHEDULE_TIME
            scheduler.run_daily(SCHEDULE_TIME)
        
        # 如果是交易日，立即执行一次
        if is_trading_day():
            logger.info("今天是交易日，立即执行一次...")
            scheduler.run_immediately()
        
        # 启动调度器（阻塞）
        scheduler.start()


if __name__ == "__main__":
    main()

