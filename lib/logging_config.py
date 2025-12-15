"""
Centralized logging configuration for thermal-report.
"""
import logging
import logging.handlers
from pathlib import Path


def setup_logging(level='ERROR', log_file='thermal_report_errors.log', log_dir=None):
    """
    Configure logging for the application.
    
    Args:
        level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file (str): Name of log file
        log_dir (str): Directory to store log file. If None, uses current directory.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Ensure log directory exists
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        log_path = Path(log_dir) / log_file
    else:
        log_path = Path(log_file)
    
    # Convert string level to logging constant
    log_level = getattr(logging, level.upper(), logging.ERROR)
    
    # Create logger
    logger = logging.getLogger('thermal_report')
    logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler
    try:
        file_handler = logging.FileHandler(str(log_path))
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not open log file {log_path}: {e}")
    
    # Console handler (stderr)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger
