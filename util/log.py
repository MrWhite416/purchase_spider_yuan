# development time: 2025-08-20  14:42
# developer: 元英

""" 这是一个日志模块 """

import logging
from logging.handlers import RotatingFileHandler
from colorama import init, Style, Fore
from setting import LOG_FILE,LOG_FILE_MAX,LOG_FILE_BACKUP_COUNT


class CustomColoredFormatter(logging.Formatter):
    # 定义不同日志级别的颜色
    LOG_LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA
    }

    # 定义日期时间和日志信息、行号、函数名的颜色
    DATE_COLOR = Fore.BLUE
    # MESSAGE_COLOR = Fore.WHITE
    ROW_NO = Fore.WHITE+Style.BRIGHT
    FUNC_NAME = Fore.CYAN+Style.BRIGHT


    def format(self, record) -> str:
        # 获取当前日志记录对应的颜色
        log_color = self.LOG_LEVEL_COLORS.get(record.levelno, Fore.WHITE)
        # 格式化日期，使用预定义的日期颜色
        formatted_date = f"{self.DATE_COLOR}{self.formatTime(record)}{Style.RESET_ALL}"
        # 格式化日志级别，使用对应级别的颜色
        formatted_level = f"{log_color}{record.levelname}{Style.RESET_ALL}"
        # 格式化日志消息，使用对应日志级别的颜色
        formatted_message = f"{log_color}{record.getMessage()}{Style.RESET_ALL}"
        # 格式化线程名、文件名、行号和函数名
        formatted_filename = f"{self.ROW_NO}{record.filename}:{record.lineno}{Style.RESET_ALL}"
        formatted_funcname = f"{self.FUNC_NAME}{record.funcName}{Style.RESET_ALL}"
        formatted_threadname = f"{self.FUNC_NAME}{record.threadName}:{record.thread}{Style.RESET_ALL}"

        # 将格式化后的日期、日志级别、文件名、行号、函数名和日志消息组合成完整的日志输出
        return f"{formatted_date} | {formatted_level} | {formatted_threadname} | {formatted_filename} | {formatted_funcname} | {formatted_message}"


def setup_logger(level=logging.DEBUG,log_file:str=LOG_FILE,max_size=LOG_FILE_MAX, backup_count=LOG_FILE_BACKUP_COUNT):
    # 创建一个日志记录器
    logger = logging.getLogger(__name__)
    logger.setLevel(level)

    # 创建一个控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    # 为控制台处理器设置自定义的彩色格式化器
    console_handler.setFormatter(CustomColoredFormatter())
    logger.addHandler(console_handler)

    # 创建一个文件处理器，使用 RotatingFileHandler
    file_handler = RotatingFileHandler(log_file, mode='a', encoding='utf-8', maxBytes=max_size, backupCount=backup_count)
    file_handler.setLevel(level)

    # 为文件处理器设置一个普通的格式化器，去除颜色代码
    file_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(threadName)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


# 设置日志记录器，同时指定日志文件的路径
logger = setup_logger()


if __name__ == '__main__':

    # 输出不同级别的日志
    logger.debug("这是一条调试信息")
    logger.info("这是一条普通信息")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")
    logger.critical("这是一条严重错误信息")