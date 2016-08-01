from pong.utils import *
from toolz import first
from pong.logger import log


def is_requirement_exists(title):
    q = title_query(title)
    reqs = query_requirement(q)

    def fltr(r):
        print "Checking", unicode(r.title)
        return title in unicode(r.title)

    try:
        res = first(filter(fltr, reqs))
    except StopIteration:
        res = False
    return res


def is_in_requirements(title, requirements):
    titles = list(filter(lambda r: title in str(r.title), requirements))

    if len(titles) > 2:
        raise Exception("Should not have multiple matches on Requirements")
    elif len(titles) == 0:
        return False
    else:
        return first(titles)


def create_requirement(project_id, title, description="", reqtype="functional",
                       severity="should_have"):

    if True:
        log.warning("No longer creating a requirement automatically")
        return None
    else:
        from pylarion.work_item import Requirement
        req = is_requirement_exists(title)
        if req:
            log.info("Found existing Requirement {}".format(req.title))
            return req
        else:
            log.info("Creating a new Requirement: {}".format(title))
            return Requirement.create(project_id, title, description, severity=severity,
                                      reqtype=reqtype)
