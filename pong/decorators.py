import datetime
import ssl
import platform
import types
from functools import wraps
from pong.logger import log

version = [int(i) for i in platform.python_version_tuple()]
if version >= [2, 7, 7]:
    ssl._create_default_https_context = ssl._create_unverified_context


def fixme(msg):
    """
    Apply to a function that needs to be fixed

    :param msg:
    :return:
    """
    def outer(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            log.info("===================FIXME========================")
            log.info("{} {}".format(fn.__name__, msg))
            log.info("================================================")
            return fn(*args, **kwargs)
        return inner
    return outer


def profile(fn):
    """
    A simple timer around a function call

    :param fn:
    :return:
    """
    @wraps(fn)
    def inner(*args, **kwargs):
        start_time = datetime.datetime.now()
        result = fn(*args, **kwargs)
        end_time = datetime.datetime.now()
        log.debug("\tstart time: {}".format(start_time))
        log.debug("\tend time: {}".format(end_time))
        log.debug("\ttotal time: {}".format(end_time - start_time))
        return result
    return inner


def retry(fn):
    """
    Decorator to handle ssl timeouts

    :return:
    """
    @wraps(fn)
    def outer(*args, **kwargs):
        retries = 3
        result = None
        while retries > 0:
            try:
                result = fn(*args, **kwargs)
                retries = 0
            except ssl.SSLError as se:
                result = se
                retries -= 1
            except Exception as ex:
                result = ex
                retries -= 1
        if isinstance(result, Exception):
            raise result
        else:
            return result
    return outer


###################################################################
# FIXME:  These belong somewhere else
###################################################################

def cycle(seq):
    """
    Not a decorator, but this will repeatedly cycle through the elements of seq
    :param seq:
    :return:
    """
    while True:
        # python3
        # yield from seq
        for x in seq:
            yield x


def repeat(val):
    """
    What's this good for?  If you want to populate a list with the same item

    Usage:
        import toolz
        ten_zeroes = toolz.take(10, repeat(0))
    :param val:
    :return:
    """
    while True:
        yield val