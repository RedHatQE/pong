__author__ = 'stoner'

import logging
import sys


def make_stream_handler(fmt, stream=sys.stdout, loglevel=logging.INFO):
    strm_handler = logging.StreamHandler(stream=stream)

    strm_handler.setFormatter(fmt)
    strm_handler.setLevel(loglevel)
    return strm_handler


def make_formatter(format_str="", date_format="%H:%M:%S"):
    if not format_str:
        format_str = "%(created)s-%(name)s-%(levelname)s: \t%(message)s"

    return logging.Formatter(fmt=format_str, datefmt=date_format)


def make_logger(loggername, handlers=(), loglevel=logging.DEBUG):
    logr = logging.getLogger(loggername)
    logr.setLevel(loglevel)

    for hdlr in handlers:
        logr.addHandler(hdlr)

    return logr


def get_simple_logger(logname, loglvl=logging.DEBUG):
    """
    Simple wrapper around the other functions to create a basic logger.  This is
    useful as a module level debugger

    :param logname: (str) a name to give to the logger object
    :param loglvl: (int) a logging loglevel
    """
    # Do the stream handler and formatter
    stream_fmt = make_formatter()
    sh = make_stream_handler(stream_fmt)

    # get the actual logger
    logr = make_logger(logname, (sh,))
    logr.setLevel(loglvl)
    return logr

log = get_simple_logger(__name__)
