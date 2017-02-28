"""
This is a script to create a JSON map of class.methodName to the Polarion TestCase and Requirements
"""

from pong.utils import *
from pong.logger import log
import re
import argparse
import json
import toolz
import sys
import xml.etree.ElementTree as et

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--mapping-file", help="Path to mapping json file")
opts = parser.parse_args()

if not os.path.exists(opts.mapping_file):
    print "Could not find the mapping file to load"
    sys.exit(1)


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

# It seems that we get duplicates in the reflected, so let's remove them
# Extra Credit:  do this functionally.  Though maybe we should keep the duplicates?
if 0:
    refl = {}
    for clazz, items in reflected.items():
        nameset = []
        maps = []
        qualset = set()
        for m in items:
            methname = m['methodName']
            qual = "{}.{}".format(clazz, methname)
            if qual not in qualset:
                nameset.append(methname)
                qualset.add(qual)
                maps.append(m)
            else:
                log.warning("Found duplicate {} in {}.".format(qual, nameset))
        refl[clazz] = maps
    reflected = refl


mapped = []
for class_meth, tc in matched:
    mapping = {}
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
    ptc = toolz.first(found)
    fullname = "{}.{}".format(klass, meth)
    log.info("Found matching test case for {}".format(fullname))

    reqs = [req.work_item_id for req in tc.linked_work_items]
    mapping[fullname] = {"testcase": tc.work_item_id, "requirements": reqs}
    mapped.append(mapping)


for clazz, maps in reflected.items():
    for m in maps:
        methname = m['methodName']
        classname = m['className']
        if methname not in mapping and m['enabled']:
            log.warning("{}.{} is enabled, but there is no Polarion TestCase for it".format(classname, methname))

s = sorted(mapped, key=lambda x: x.keys()[0])
with open("map-file.json", "w") as mapper:
    json.dump(s, mapper, sort_keys=True, indent=2, separators=(',', ':'))

with open("reflected.json", "w") as refl:
    json.dump(reflected, refl, sort_keys=True, indent=2, separators=(',', ':'))


#####################################################################
# These are the python equivalents of some of the java classes.
# These are used to convert the TestCase object in pylarion into a JSON
# representation.  We have to do this, because unfortunately, the TestCase
# object can not be serialized via json.dumps(tc), nor would we want to
# because there is too much information
######################################################################


import abc


class EnumType(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, val):
        self.val = self.check(val)

    def to_lower(self):
        return self.val.lower()

    def check(self, val):
        valid = [i for i in dir(self.__class__) if not callable(getattr(self.__class__, i)) and not i.startswith("_")]
        if val not in valid:
            raise Exception("val must be in {}".format(",".join(valid)))
        return val

    @classmethod
    def from_lower(cls, val):
        return cls(val.upper)


class TestType(EnumType):
    FUNCTIONAL = "FUNCTIONAL"
    NONFUNCTIONAL = "NONFUNCTIONAL"
    STRUCTURAL = "STRUCTURAL"

    def __init__(self, val):
        super(TestType, self).__init__(val)


class SubType(EnumType):
    EMPTY = "EMPTY"
    COMPLIANCE = "COMPLIANCE"
    DOCUMENTATION = "DOCUMENTATION"
    I18NL10N = "I18NL10N"
    INSTALLABILITY = "INSTALLABILITY"
    INTEROPERABILITY = "INTEROPERABILITY"
    PERFORMANCE = "PERFORMANCE"
    RELIABILITY = "RELIABILITY"
    SCALABILITY = "SCALABILITY"
    SECURITY = "SECURITY"
    USABILITY = "USABILITY"
    RECOVERYFAILOVER = "RECOVERYFAILOVER"
    def __init__(self, val):
        super(SubType, self).__init__(val)


class Automation(EnumType):
    AUTOMATED = "AUTOMATED"
    NOTAUTOMATED = "NOTAUTOMATED"
    MANUALONLY = "MANUALONLY"

    def __init__(self, val):
        super(Automation, self).__init__(val)


class Level(EnumType):
    COMPONENT = "COMPONENT"
    INTEGRATION = "INTEGRATION"
    SYSTEM = "SYSTEM"
    ACCEPTANCE = "ACCEPTANCE"

    def __init__(self, val):
        super(Level, self).__init__(val)


class PosNeg(EnumType):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"

    def __init__(self, val):
        super(PosNeg, self).__init__(val)


class Importance(EnumType):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    def __init__(self, val):
        super(Importance, self).__init__(val)


class Role(EnumType):
    RELATES_TO = "RELATES_TO"
    HAS_PARENT = "HAS_PARENT"
    DUPLICATES = "DUPLICATES"
    VERIFIES = "VERIFIES"
    IS_RELATED_TO = "IS_RELATED_TO"
    IS_PARENT_OF = "IS_PARENT_OF"
    IS_DUPLICATED_BY = "IS_DUPLICATED_BY"
    TRIGGERS = "TRIGGERS"

    def __init__(self, val):
        super(Role, self).__init__(val)


class LinkedWorkItem(object):
    def __init__(self, lwi):
        self.work_item_id = str(lwi.work_item_id)
        self.suspect = False
        self.role = str(lwi.role)
        self.project = str(lwi.default_project)
        self.revision = lwi.revision if lwi.revision else ""


class TestType(object):
    def __init__(self, tc):
        self.testtype = str(tc.testtype)
        subtype1 = SubType.EMPTY if str(tc.subtype1) == "-" else str(tc.subtype1).upper()
        subtype2 = SubType.EMPTY if str(tc.subtype2) in ["-", "None"] else str(tc.subtype2).upper()
        self.subtype1 = subtype1.lower()
        self.subtype2 = subtype2.lower()


class TC2Json(object):
    def __init__(self, tc):
        self.testcase_id = str(tc.work_item_id)
        self.project = "RHEL6" if "RHEL6" in self.testcase_id else "RedHatEnterpriseLinux7"
        self.title = str(tc.title)
        self.description = str(tc.description)
        self.setup = str(tc.setup)
        self.teardown = str(tc.teardown)
        self.linked_work_items = [str(wi.work_item_id) for wi in tc.linked_work_items]
        self.importance = str(tc.caseimportance)
        self.posneg = str(tc.caseposneg)
        self.level = str(tc.caselevel)
        self.automation = str(tc.caseautomation)
        self.test_type = TestType(tc)
        self.test_steps = self.get_ts(tc)
        self.assignee = str(tc.assignee)
        self.initial_estimate = str(tc.initial_estimate) if tc.initial_estimate else ""
        self.tags = str(tc.tags) if tc.tags else ""
        self.component = str(tc.casecomponent)
        self.subcomponent = str(tc.subcomponent) if tc.subcomponent else ""
        self.upstream = str(tc.upstream) if tc.upstream else ""
        
    def get_ts(self, tc):
        steps = tc.test_steps.steps
        if steps:
            vals = steps[0].values
            if vals:
                return unicode(vals[0].content).split(",")
        else:
            return []

js = map(lambda x: TC2Json(x[1]), matched)

with open("/tmp/tc2json.json", "w") as tc2:
    json.dump(js, tc2, default=lambda x: x.__dict__, indent=2, sort_keys=True, separators=(",", ":"))


class XMLTestCase(object):
    """
    Generates a valid XML for a TestCase
    """
    def __init__(self, jtc):
        root = et.Element("testcases", attrib=self.make_tcs_attrib(jtc))
        tc = et.SubElement(root, "testcase", attrib=self.make_tc_attrib(jtc))
        rps = self.make_rps(root)

    def make_tcs_attrib(self, jtc):
        return {"project_id": jtc.project}

    def make_tc_attrib(self, jtc):
        attrib = {"id": jtc.testcase_id}
        if jtc.assignee:
            attrib["assignee-id"] = jtc.assignee
        if jtc.initial_estimate:
            attrib["initial_estimate"] = jtc.initial_estimate
        return attrib

    def make_rps(self, parent, resp_name=None, resp_val=None):
        rps = et.SubElement(parent, "response-properties")
        attr = {"name": "rhsm_qe" if resp_name is None else resp_name,
                "val": "testcase" if resp_val is None else resp_val}
        rp = et.SubElement(rps, "response-property", attrib=attr)
        return rps

