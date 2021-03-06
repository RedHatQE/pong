import shutil

import re
import os
import ConfigParser
from functools import partial
from itertools import repeat


from toolz import itertoolz as itz
from toolz import functoolz as ftz

from pong.decorators import retry, profile

PYLARION_CONFIG = [os.path.join(os.environ['HOME'], ".pylarion")]
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
STATUS_MAP = {"PASS": PASS, "FAIL": FAIL, "SKIP": SKIP}
DEFAULT_WORKSPACE = "/home/jenkins/workspace"
DEFAULT_JENKINS_PROJECT = "stoner_gui_test_polarion"
DEFAULT_RESULT_PATH = "test_output/pong-results.xml"

TC_KEYS = {"caseimportance": "high",
           "caselevel": "component",
           "caseposneg": "positive",
           "testtype": "functional",
           "subtype1": "reliability",
           "caseautomation": "automated"}


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


@profile
@retry
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
    from pylarion.work_item import TestCase as PylTestCase
    return PylTestCase.query(query, fields=fields, **kwargs)


def cached_tc_query(query, test_cases, multiple=False):
    def title_match(tc):
        #klass, method_name = get_class_methodname(str(tc.title))
        res = query in tc.title
        return res

    matches = list(filter(title_match, test_cases))
    retval = []
    if not multiple and len(matches) > 1:
        raise Exception("Can not have more than one match, modify your query")
    elif len(matches) == 0:
        if not multiple:
            retval = False
    else:
        if multiple:
            retval = matches
        else:
            retval = itz.first(matches)
    return retval


@profile
@retry
def query_requirement(query, fields=None, **kwargs):
    """
    Returns a list of pylarion Requirement objects

    :param query:
    :param fields:
    :param kwargs:
    :return:
    """
    if fields is None:
        fields = ["work_item_id", "title"]
    from pylarion.work_item import Requirement
    return Requirement.query(query, fields=fields, **kwargs)


def title_query(q, wild=True, no_quote=False):
    """
    Helps generate a title query.

    Creates a simpler lucene query, and handles the case where the user might want to have spaces
    eg::

        query = title_query("RHSM : RCT Tool")
        print query  # title:"RHSM : RCT Tool"*
    :param q:
    :param wild:
    :param no_quote: if true, don't surround
    :return:
    """
    title_fmt = 'title:"{}{}"'
    if no_quote:
        title_fmt = 'title:{}{}'
    extra = ""
    if wild:
        extra = "*"
    query = title_fmt.format(q, extra)
    return query


def get_default_project(pylarion_path=PYLARION_CONFIG):
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
    from pylarion.test_run import TestRun
    s = TestRun.search('"{}"'.format(test_run_name),
                       fields=["test_run_id", "created", "status"],
                       sort="created")
    current = None
    if s:
        latest = itz.last(s)
        current = TestRun(uri=latest.uri)
    return current


def get_test_run(project_id, test_run_id):
    """
    Given a Polarion project_id and a test run id (not title) return a fully formed
    pylarion TestRun object.

    Note that unlike the TestRun.search() class method, this will populate all the fields

    :param project_id: str of the project id
    :param test_run_id: str of the test run id
    :return:
    """
    from pylarion.test_run import TestRun as PylTestRun
    tr = PylTestRun(project_id=project_id, test_run_id=test_run_id)
    return tr


def make_test_run_id_from_latest(test_run):
    """
    Returns a new test run id string that can be used to generate a
    TestRun (because Polarion is too stupid to create a unique id for
    the user)

    :param test_run: TestRun object
    :return: str
    """
    patt = re.compile(r"^(.+)\s+(\d+)$")
    m = patt.search(test_run.test_run_id)
    base_id = test_run.test_run_id
    if m:
        base_id = m.groups()[0]
        id = int(m.groups()[1]) + 1
    else:
        id = 1

    base_id = remove_run(base_id)
    return "{} Run {}".format(base_id, id)


def remove_run(s):
    s = s.strip()
    if s.endswith("Run"):
        s = s[:-3]
        return remove_run(s)
    else:
        return s


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
    return any(test_case_id == rec.test_case_id for rec in test_run._records)


def zero_steps(polarion_tc):
    """
    Given a pylarion TestCase object, remove all the TestSteps

    :param polarion_tc:
    :return:
    """
    pass


def polarion_safe_string(string):
    """
    Polarion doesn't like . in a string
    :param string:
    :return:
    """
    # As we find other characters to replace, add a new
    # function and compose them
    def no_dot(s):
        return s.replace(".", "-")

    def no_newline(s):
        return s.strip()

    def no_colon(s):
        return s.replace(":", " ")

    safe = ftz.compose(no_colon, no_dot, no_newline)
    return safe(string)


def testify_requirement_name(test_name, prefix=""):
    """
    Generates a name for a Requirement by taking the <test name=XXX> name attribute, and prefixing with prefix

    :param test_name:
    :param prefix:
    :return:
    """
    return prefix + test_name


def public_field(obj, f):
    """
    Predicate function that sees if field f in an object is neither callable nor private

    Useful in filtering functions to print fields in an object

    :param obj: The object to check
    :param f: string which is the name of a field in the object
    :return: bool
    """
    result = False
    try:
        no_under = not f.startswith("_")
        attrib = getattr(obj, f)
        return no_under and (attrib and not callable(attrib))
    except AttributeError:
        pass
    except TypeError:
        pass
    return result


def make_iterable(obj):
    """
    Takes an arbitrary object and returns the fields which are public and not callable

    :param obj:
    :return:
    """
    valid = partial(public_field, obj)
    items = filter(valid, dir(obj))
    for i in items:
        yield i, getattr(obj, i)


def replace(names_to_check, non_valid=None, rmap=None):
    """
    Removes characters defined in non_valid from strings defined in names_to_check

    Does not mutate strings in names_to_check, but returns new strings with invalid
    characters replaced by a single space

    :param names_to_check: a list of names to sanitize
    :param non_valid: a list or set of characters or strings which should be replaced
    :param rmap: a mapping from non_valid char to replacement char.  Default is to
                 replace any non_valid character with a single space
    :return:
    """
    if non_valid is None:
        non_valid = [c for c in """\/.:*"<>|~!@#$?%^&'*()+`,="""] + ['Tab']
    if rmap is None:
        rmap = {c: " " for c in non_valid}

    def clean(n, nv):
        return reduce(lambda n, c: n if c not in n else n.replace(c, rmap[c]), nv, n)
    return map(clean, names_to_check, repeat(non_valid, len(names_to_check)))


def create_backup(orig, backup=".bak"):
    backup_path = orig + backup
    shutil.copy(orig, backup_path)
