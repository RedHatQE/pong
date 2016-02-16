from pong.core import TestNGToPolarion
from pong.utils import *
from pyrsistent import m, v, s, pvector, PRecord, field
from pylarion.work_item import Requirement
from toolz import first


def is_requirement_exists(title):
    q = title_query(title)
    reqs = query_requirement(q)

    def fltr(r):
        print "Checking", unicode(r.title)
        return title == unicode(r.title)

    return first(filter(fltr, reqs))


def is_in_requirements(title, requirements):
    titles = list(filter(lambda r: title == str(r.title), requirements))

    if len(titles) > 2:
        raise Exception("Should not have multiple matches on Requirements")
    elif len(titles) == 0:
        return False
    else:
        return first(titles)


def create_requirement(project_id, title, description="", reqtype="functional",
                       severity="should_have"):
    if is_requirement_exists(title):
        return True
    else:
        return Requirement.create(project_id, title, description, severity=severity,
                                  reqtype=reqtype)
