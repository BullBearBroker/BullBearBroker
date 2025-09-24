from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, format="{time} {level} {message}", serialize=True)


def get_logger():
    return logger
