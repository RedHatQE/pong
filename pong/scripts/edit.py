from pylarion.work_item import TestCase, Requirement
from pong.utils import query_test_case, query_requirement
import re


def add_colon_tc(tc):
    parts = tc.title.split()
    if ":" not in tc.title:
        newtitle = parts[0] + " : " + parts[1]
        wi = TestCase(uri=tc.uri)
        wi.title = newtitle
        try:
            wi.update()
            print "Changed title to {}".format(newtitle)
        except:
            print "Failed to update {}".format(wi.title)


def clean_req_title(req):
    """
    Makes sure that all the titles for requirements have RHSM-REQ : title (space:space)

    :param req: A Pylarion Requirement object
    :return:
    """
    patt = re.compile(r"RHSM-REQ(\s*:?\s*)(.+)")
    m = patt.search(req.title)
    if not m:
        raise Exception("Did not match on requirement title")
    colon, title = m.groups()
    if not colon.startswith(" ") or not colon.endswith(" "):
        new_title = "RHSM-REQ : " + title
        preq = Requirement(uri=req.uri)
        preq.title = new_title
        try:
            preq.update()
            print "Changed {} to title {}".format(preq.work_item_id, preq.title)
        except:
            print "Failed to update {}".format(req.work_item_id)


def mark_for_deletion(tc):
    if "RHSM-TC" in tc.title:
        wi = TestCase(uri=tc.uri)
        wi.title = "Delete me"
        try:
            wi.update()
            print "Changed {} title from {} to {}".format(wi.work_item_id, tc.title, wi.title)
        except:
            print "Failed to change {}".format(wi.work_item_id)


def fix_tc_title(tc):
    """
    Need to add RHSM-TC : prefix to the existing testcases

    :param tc:
    :return:
    """
    if tc.title.startswith("RHSM-TC : "):
        print "TestCase already starts with RHSM-TC : "
        return

    newtitle = "RHSM-TC : " + tc.title
    wi = TestCase(uri=tc.uri)
    wi.title = newtitle
    try:
        wi.update()
        print "Changed {} title to {}".format(wi.work_item_id, newtitle)
    except:
        print "Failed to update {}".format(wi.title)


def remove_linked_requirements_from_tests(test_cases):
    """
    Removes all linked Items from TestCase objects in test_Cases

    :param test_cases:
    :return:
    """
    for tc in test_cases:
        tc = TestCase(uri=tc.uri)
        tc.linked_work_items = []
        tc.update()

tcs = query_test_case("title:rhsm.*.tests*")
bad = list(filter(lambda tc: not tc.title.startswith("RHSM-TC"), tcs))

if 0:
    for tc in tcs:
        fix_tc_title(tc)

if 0:
    reqs = query_requirement("title:RHSM-REQ AND author.id:ci\-user")
    for req in reqs:
        clean_req_title(req)

