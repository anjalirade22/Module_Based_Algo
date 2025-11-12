import logging
import os
from datetime import datetime

def setup_logging(log_dir='logs', log_file_prefix='TradingSystem_log'):
    """Sets up logging configuration.

    Args:
        log_dir (str): Directory where log files will be stored.
        log_file_prefix (str): Prefix for the log file name.
    """
    # Ensure the log directory exists
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, f"{log_file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger("TradingSystem")
