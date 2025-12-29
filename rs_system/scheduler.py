"""
自动调度模块：实现每日自动更新功能
"""
import schedule
import time
from datetime import datetime
import logging
from typing import Callable
from rs_system.config import SCHEDULE_TIME, SCHEDULE_TIMEZONE

logger = logging.getLogger(__name__)


class Scheduler:
    """任务调度器"""
    
    def __init__(self, task_function: Callable):
        """
        初始化调度器
        
        Args:
            task_function: 要执行的任务函数（无参数）
        """
        self.task_function = task_function
        self.is_running = False
    
    def run_daily(self, time_str: str = SCHEDULE_TIME):
        """
        设置每日定时任务
        
        Args:
            time_str: 执行时间，格式 "HH:MM"（24小时制）
        """
        schedule.clear()  # 清除之前的任务
        schedule.every().day.at(time_str).do(self._execute_task)
        logger.info(f"已设置每日任务，执行时间: {time_str}")
    
    def run_immediately(self):
        """立即执行一次任务"""
        logger.info("立即执行任务...")
        self._execute_task()
    
    def _execute_task(self):
        """执行任务（包装函数，用于异常处理）"""
        try:
            logger.info(f"开始执行任务 - {datetime.now()}")
            self.task_function()
            logger.info(f"任务执行完成 - {datetime.now()}")
        except Exception as e:
            logger.error(f"任务执行失败: {str(e)}", exc_info=True)
    
    def start(self, run_immediately: bool = False):
        """
        启动调度器（阻塞运行）
        
        Args:
            run_immediately: 是否立即执行一次
        """
        if run_immediately:
            self.run_immediately()
        
        self.is_running = True
        logger.info("调度器已启动，等待执行时间...")
        
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            logger.info("调度器已停止")
            self.is_running = False
    
    def stop(self):
        """停止调度器"""
        self.is_running = False
        schedule.clear()
        logger.info("调度器已停止")


def is_trading_day(date: datetime = None) -> bool:
    """
    判断是否为交易日（简化版，实际应该考虑节假日）
    
    Args:
        date: 日期，默认为今天
        
    Returns:
        是否为交易日
    """
    if date is None:
        date = datetime.now()
    
    # 简单判断：排除周末
    weekday = date.weekday()  # 0=Monday, 6=Sunday
    return weekday < 5  # Monday to Friday

