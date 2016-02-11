import logging
import sys
import time

DEFAULT_LOG_FILE = "/tmp/pong"


def make_timestamp():
    """
    Returns the localtime year-month-day-hr-min-sec as a string
    """
    timevals = time.localtime()[:-3]
    ts = "-".join(str(x) for x in timevals)
    return ts


def make_timestamped_filename(prefix, postfix=".log"):
    """
    Returns a string containing prefix-timestamp-postfix
    """
    fname = prefix + "-" + make_timestamp() + postfix
    return fname


def make_stream_handler(fmt, stream=sys.stdout, loglevel=logging.INFO):
    strm_handler = logging.StreamHandler(stream=stream)

    strm_handler.setFormatter(fmt)
    strm_handler.setLevel(loglevel)
    return strm_handler


def make_file_handler(fmt, filename, loglevel=logging.DEBUG):
    """

    :param fmt:
    :param filename:
    :param loglevel:
    :return:
    """
    file_handler = logging.FileHandler(filename)
    file_handler.setFormatter(fmt)
    file_handler.setLevel(loglevel)
    return file_handler


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


def get_simple_logger(logname, filename=DEFAULT_LOG_FILE, loglvl=logging.DEBUG):
    """
    Simple wrapper around the other functions to create a basic logger.  This is
    useful as a module level debugger

    :param logname: (str) a name to give to the logger object
    :param filename: (str) path to log file
    :param loglvl: (int) a logging loglevel
    """
    # Do the stream handler and formatter
    stream_fmt = make_formatter()
    sh = make_stream_handler(stream_fmt)
    sh.setLevel(logging.INFO)

    # Make the filename, file handler and formatter
    fname = make_timestamped_filename(filename, ".log")
    file_fmt = make_formatter()
    fh = make_file_handler(file_fmt, fname)
    fh.setLevel(logging.DEBUG)

    # get the actual logger
    logr = make_logger(logname, (sh, fh))
    # logr.setLevel(loglvl)
    return logr

log = get_simple_logger(__name__)
