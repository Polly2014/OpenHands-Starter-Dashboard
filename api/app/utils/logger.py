# app/utils/logger.py
import logging
import os
from dotenv import load_dotenv

load_dotenv()

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    # 避免重复配置
    if logger.handlers:
        return logger
        
    log_level = logging.DEBUG if os.getenv("ENVIRONMENT") == "development" else logging.INFO
    
    logger.setLevel(log_level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger