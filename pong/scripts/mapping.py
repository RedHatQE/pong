"""
This is a script to create a JSON map of class.methodName to the Polarion TestCase and Requirements
"""

from pong.utils import *
from pong.logger import log
import re
import argparse
import json
import toolz

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--mapping-file", help="Path to mapping json file")
opts = parser.parse_args()


class ProjectDetails(object):
    def __init__(self, requirement, testcase):
        self.requirement = requirement
        self.testcase = testcase


class Mapping(object):
    def __init__(self, method):
        self.method = method

tcs = query_test_case("title:RHSM-TC AND type:testcase", fields=["title", "work_item_id", "linked_work_items"])
patt = re.compile(r"RHSM-TC : rhsm.(cli|gui)\.tests\.([a-zA-Z0-9_.\- ]+)")


def matcher(tc):
    m = patt.search(tc.title)
    if m:
        return m.groups(), tc
    return False

matched = filter(lambda x: x, [matcher(tc_) for tc_ in tcs])
reflected = None
with open(opts.mapping_file, "r") as mapping:
    reflected = toolz.groupby('className', json.load(mapping))

mapping = {}
for class_meth, tc in matched:
    class_prefix = "rhsm.{}.tests.".format(class_meth[0])
    klass, meth = class_meth[1].split(".")
    klass = class_prefix + klass
    try:
        class_group = reflected[klass]
    except KeyError as ke:
        log.warning(ke.message)
        continue
    found = list(filter(lambda m: m['methodName'] == meth, class_group))
    if not found:
        log.info("No Polarion test case was found for {}.{}".format(klass,meth))
        continue
    for ptc in found:
        fullname = "{}.{}".format(klass, meth)
        log.info("Found matching test case for {}".format(fullname))

        reqs = [req.work_item_id for req in tc.linked_work_items]
        mapping[fullname] = {"testcase": tc.work_item_id, "requirements": reqs}

with open("map-file.json", "w") as mapper:
    json.dump(mapping, mapper)