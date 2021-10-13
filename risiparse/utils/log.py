#!/usr/bin/python3

"""This module takes care of all logging related needs"""

# Thanks to
# https://uran198.github.io/en/python/2016/07/12/colorful-python-logging.html

import logging
import pathlib
import datetime
import copy
import colorama

# specify colors for different logging levels
LOG_COLORS = {
    logging.ERROR: colorama.Fore.RED,
    logging.CRITICAL: colorama.Fore.RED,
    logging.WARNING: colorama.Fore.YELLOW
}

TODAY = datetime.date.today()


class ColorFormatter(logging.Formatter):
    """Color the logs"""
    def format(self, record, *args, **kwargs):
        # if the corresponding logger has children, they may receive modified
        # record, so we want to keep it intact
        new_record = copy.copy(record)
        if new_record.levelno in LOG_COLORS:
            # we want levelname to be in different color, so let's modify it
            msg = new_record.msg
            level = new_record.levelname
            color_begin = LOG_COLORS[new_record.levelno]
            color_end = colorama.Style.RESET_ALL
            new_record.msg = f"{color_begin}{msg}{color_end}"
            new_record.levelname = f"{color_begin}{level}{color_end}"
        # now we can let standart formatting take care of the rest
        return super().format(new_record, *args, **kwargs)


def set_file_logging(
        output_dir: pathlib.Path,
        logger: 'logging.Logger',
        fmt: str
) -> None:
    """Set up the logging to a file."""
    log_file = output_dir / f"risiparse-{TODAY}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(file_handler)
