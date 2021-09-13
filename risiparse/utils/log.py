#!/usr/bin/python3

"""This module takes care of all logging related needs"""

# Thanks to
# https://uran198.github.io/en/python/2016/07/12/colorful-python-logging.html

import logging
import colorama
import copy

# specify colors for different logging levels
LOG_COLORS = {
    logging.ERROR: colorama.Fore.RED,
    logging.CRITICAL: colorama.Fore.RED,
    logging.WARNING: colorama.Fore.YELLOW
}


class ColorFormatter(logging.Formatter):
    def format(self, record, *args, **kwargs):
        # if the corresponding logger has children, they may receive modified
        # record, so we want to keep it intact
        new_record = copy.copy(record)
        if new_record.levelno in LOG_COLORS:
            # we want levelname to be in different color, so let's modify it
            new_record.msg = "{color_begin}{msg}{color_end}".format(
                msg=new_record.msg,
                color_begin=LOG_COLORS[new_record.levelno],
                color_end=colorama.Style.RESET_ALL,
            )
            new_record.levelname = "{color_begin}{level}{color_end}".format(
                level=new_record.levelname,
                color_begin=LOG_COLORS[new_record.levelno],
                color_end=colorama.Style.RESET_ALL,
            )
        # now we can let standart formatting take care of the rest
        return super().format(new_record, *args, **kwargs)
