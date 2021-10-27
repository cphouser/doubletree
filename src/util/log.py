#!/usr/bin/env python3

import logging

class LogFormatter(logging.Formatter):
    """Logging Formatter to add colors and count warning / errors"""
    #https://stackoverflow.com/a/56944256
    grey = "\033[94m"
    blue = "\033[96m"
    red = "\033[22;31m"
    bold_red = "\033[1;31m"
    reset = "\033[0m"
    yellow = "\033[22;33m"
    format = '[%(levelname)s]\t%(module)s:%(lineno)d:%(funcName)s: %(message)s'

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: blue + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
