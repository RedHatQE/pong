import re
import os
import ConfigParser

from toolz import itertoolz as itz
from pylarion.work_item import TestCase as PylTestCase
from pylarion.test_run import TestRun

PYLARION_CONFIG = [os.path.join(os.environ['HOME'], ".pylarion")]
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
STATUS_MAP = {"PASS": PASS, "FAIL": FAIL, "SKIP": SKIP}
DEFAULT_WORKSPACE = "/home/jenkins/workspace"
DEFAULT_JENKINS_PROJECT = "stoner_gui_test_polarion"
DEFAULT_RESULT_PATH = "test_output/polarion_testng-results.xml"

TC_KEYS = {"caseimportance": "high", "caselevel": "component", "caseposneg": "positive",
           "testtype": "functional", "subtype1": "reliability", "caseautomation": "automated"}


def get_class_methodname(s):
    """
    splits a classname.methodname into constituent class and methodname

    :param s: str (eg "rhsm.cli.tests.GeneralTests.SomeTestMethod")
    :return: (classname, methodname)
    """
    parts = s.split(".")
    klass = ".".join(parts[:-1])
    methodname = parts[-1]
    return klass, methodname


def query_test_case(query, fields=None, **kwargs):
    """
    Returns a list of pylarion TestCase objects

    :param query:
    :param fields: an optional list of fields to populate in the returned TestCase objects
                   (by default only work_item_id and title will be populated)
    :return:
    """
    if fields is None:
        fields = ["work_item_id", "title"]
    return PylTestCase.query(query, fields=fields, **kwargs)


def get_default_project():
    """
    Reads in the ~/.pylarion config file to get default project
    :return: the default project
    """
    config = ConfigParser.ConfigParser()
    config.read(PYLARION_CONFIG)
    return config.get("webservice", "default_project")


def sanitize(text_obj):
    """
    The Polarion Text object might contain html formatting, so clean it

    :param text_obj:
    :return:
    """
    patt = re.compile(r"(<.*>)?(\w+)(<.*>)?")
    if text_obj.content is None:
        text_obj.content = ""
    m = patt.search(text_obj.content)
    value = text_obj.content
    if m:
        value = m.groups()[1]

    final = value
    if isinstance(value, unicode):
        final = value.encode('utf-8', 'ignore')
    return final


def get_latest_test_run(test_run_name):
    """
    Gets the most recent TestRun based on the test_run_name

    NOTE: the test_run_name should be the name of a test run without the integer.
    For example, if your TestRun id is normally "Jenkins Run 1", then test_run_name
    should be "Jenkins Run".

    :param test_run_name: test run id string
    :return: TestRun
    """
    s = TestRun.search('"{}"'.format(test_run_name),
                       fields=["test_run_id", "created", "status"],
                       sort="created")
    return itz.last(s) if s else None


def get_test_run(project_id, test_run_id):
    """
    Given a Polarion project_id and a test run id (not title) return a fully formed
    pylarion TestRun object.

    Note that unlike the TestRun.search() class method, this will populate all the fields

    :param project_id: str of the project id
    :param test_run_id: str of the test run id
    :return:
    """
    tr = TestRun(project_id=project_id, test_run_id=test_run_id)
    return tr


def make_test_run_id_from_latest(test_run):
    """
    Returns a new test run id string that can be used to generate a
    TestRun (because Polarion is too stupid to create a unique id for
    the user)

    :param test_run: TestRun object
    :return: str
    """
    patt = re.compile(r"([a-zA-Z ]+)(\d+)$")
    m = patt.search(test_run.test_run_id)
    base_id = test_run.test_run_id
    if m:
        base_id = m.groups()[0]
        id = int(m.groups()[1]) + 1
    else:
        id = 1
    return "{}{}".format(base_id, id)


def convert_status(testng_result):
    convert = {"PASS": "passed", "FAIL": "failed", "SKIP": "waiting"}
    return convert[testng_result]


def check_test_case_in_test_run(test_run, test_case_id):
    """
    Creates a copy of a test_run obj and checks to see if a test case id
    already exists in this run

    :param test_run:
    :param test_case_id:
    :return:
    """
    check_tr = TestRun(uri=test_run.uri)
    return any(test_case_id == rec.test_case_id for rec in check_tr._records)


def zero_steps(polarion_tc):
    """
    Given a pylarion TestCase object, remove all the TestSteps

    :param polarion_tc:
    :return:
    """
    pass