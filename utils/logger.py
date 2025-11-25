import logging
import os
import datetime
from typing import Optional
from utils.config_manager import config_manager

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 获取日志目录（使用绝对路径）
LOG_DIR = os.path.join(PROJECT_ROOT, config_manager.get('LOG_DIR', 'logs'))

# 创建日志目录
os.makedirs(LOG_DIR, exist_ok=True)

# 日志格式
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'

# 全局日志文件路径（确保所有logger使用同一个文件）
GLOBAL_LOG_FILE = os.path.join(LOG_DIR, f"openmanus_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.log")

# 创建并配置根logger
def setup_logger(name: str = 'openmanus', level: Optional[int] = None) -> logging.Logger:
    """
    设置并返回一个logger实例
    
    Args:
        name: logger的名称
        level: 日志级别，如果为None则从配置中获取
    
    Returns:
        配置好的logger实例
    """
    # 获取日志级别
    if level is None:
        level_name = config_manager.get('LOG_LEVEL', 'INFO')
        level = getattr(logging, level_name)
    
    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加handler
    if not logger.handlers:
        # 创建控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(LOG_FORMAT)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # 创建文件handler（使用全局日志文件）
        file_handler = logging.FileHandler(GLOBAL_LOG_FILE, encoding='utf-8')
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger

# 创建默认logger
define_log_level = lambda: setup_logger()
logger = setup_logger()

# 测试日志功能
logger.info("=== OpenManus-LC 日志系统初始化成功 ===")
logger.info(f"日志文件路径: {GLOBAL_LOG_FILE}")
logger.info(f"日志级别: {config_manager.get('LOG_LEVEL', 'INFO')}")

# 日志装饰器，用于简化函数日志记录
def log_function_call(func):
    """
    装饰器，记录函数调用、参数和返回值
    """
    func_logger = setup_logger(func.__module__)
    
    def wrapper(*args, **kwargs):
        func_logger.debug(f"调用函数 {func.__name__}，参数: args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            func_logger.debug(f"函数 {func.__name__} 返回: {result}")
            return result
        except Exception as e:
            func_logger.exception(f"函数 {func.__name__} 执行出错: {e}")
            raise
    
    return wrapper

# 错误处理装饰器，用于函数异常重试
def error_handler(max_retries=3, retry_delay=1, exceptions=(Exception,)):
    """
    装饰器，自动重试失败的函数
    
    Args:
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
        exceptions: 捕获的异常类型
    """
    import time
    
    def decorator(func):
        func_logger = setup_logger(func.__module__)
        
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        func_logger.info(f"重试函数 {func.__name__}，第 {attempt} 次尝试")
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    func_logger.warning(f"函数 {func.__name__} 尝试 {attempt+1} 失败: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))  # 指数退避
            
            func_logger.error(f"函数 {func.__name__} 在 {max_retries} 次尝试后失败")
            raise last_exception
        
        return wrapper
    
    return decorator