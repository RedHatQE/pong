import xml.etree.ElementTree as ET
from urllib2 import urlopen
from urlparse import urlparse

from pong.core import TestIterationResult, TestNGToPolarion
from pong.decorators import fixme
from pong.logger import log
from pong.utils import *

import pong.requirement as preq
from pong.decorators import profile


def get_data_provider_elements(elem):
    """
    Gets all the <param> elements from a <test-method> invocation

    Note that we have to convert the values in the xml file to unicode because some tests are
    translation tests in foreign languages and thus require unicode to properly decode/encode.

    :param elem: an Element node from <test-method>
    :return: a list of argument values which have been stringified
    """
    def uni(val):
        txt = "null" if val.text is None else val.text
        if isinstance(txt, unicode):
            return txt
        else:
            return unicode(txt, encoding='utf-8')

    return [uni(value).strip() for param in elem.iter("param") for value in param]


def stringify_arg(value):
    """
    Gets rid of the CDATA xml part of the string.

    :param value: a possibly unicode element
    :return: unicode value without the CDATA information
    """
    patt = re.compile(r"<!\[CDATA\[(.+)\]\]")
    if value is None:
        value = "null"
    m = patt.search(value)
    if not m:
        arg = value.strip()
    else:
        arg = m.groups()[0].strip()
    text = arg.encode('utf-8', 'ignore')
    return text


def get_exception(test_meth_elem):
    """
    Gets any exception information from a test_method element

    :param test_meth_elem:
    :return:
    """
    exception = {}
    for exc in test_meth_elem.iter("exception"):
        exception["classname"] = exc.attrib["class"]
        for child in exc:
            txt = stringify_arg(child.text)
            if child.tag == "message":
                exception["message"] = txt
            if child.tag == "full-stacktrace":
                exception["stack_trace"] = txt
    return exception


@fixme("will be replaced when SR2 2015 API is exposed in pylarion")
def add_step(steps, title, attrs, new_row, exception=None, output=None,
             started=None, duration=None, status=PASS, test_case=None):
    """
    FIXME: ughhhh this is ugly, and will also change with the SR2 2015 API.  Rework this to make it:
    1) immutable
    2) flexible enough to accommodate iterations and parameters

    Helper function that creates a dictionary that can be used by the
    TestCase object in initialization (the results argument)

    :param steps: A dictionary which will contain testcase titles as the top level element.
    :param title: title of the test case
    :param attrs: dict of the xml attributes for a <test-method>
    :param new_row: arguments of the test case step
    :param exception: any exception that may have occurred
    :param output: output of the result of the test step
    :param started:
    :param duration:
    :param status:
    :param test_case:
    :return:
    """
    if title not in steps:
        steps[title] = {}
        steps[title]["test_case"] = test_case
        steps[title]["steps"] = [{"args": new_row, "attributes": attrs,
                                  "exception": exception, "output": output,
                                  "started": started, "duration": duration,
                                  "status": status}]
    elif steps[title]:
        step = {"args": new_row, "attributes": attrs,
                "exception": exception, "output": output,
                "started": started, "duration": duration,
                "status": status}
        steps[title]["steps"].append(step)


@fixme("parsing needs to change how it gets TestSteps (data providers are not TestStep based anymore)")
def parse_results(result_path, get_output=False):
    """
    This is the main function which parses the pong-results.xml file and creates a dictionary of
    test case title -> list of {attributes (result of testmethod) and args (the arguments for this step)}

    :param result_path:
    :return:
    """
    tree = ET.parse(result_path)
    root = tree.getroot()
    test_cases = {}

    for klass in root.iter("class"):
        class_name = klass.attrib["name"]
        query = "title:{}*".format(class_name)
        log.info("Querying Polarion for: {}".format(query))
        matches = query_test_case(query)
        ptc = None

        last_test_method = None
        for test_method in klass:
            attribs = test_method.attrib

            # if this is an is-config method, skip it
            if "is-config" in attribs and attribs["is-config"] == "true":
                continue

            method_name = attribs["name"]
            if last_test_method is None:
                last_test_method = method_name
            elif method_name != last_test_method:
                ptc = None
                last_test_method = method_name

            if ptc is None:
                for match in matches:
                    _, methodname = get_class_methodname(match.title)
                    if str(methodname) == str(method_name):
                        log.info("Found existing TestCase: {}".format(match.title))
                        ptc = PylTestCase(uri=match.uri)
                        break

            log.info("Parsing {}.{} {}".format(class_name, method_name, attribs['started-at']))
            test_case_title = class_name + "." + method_name

            # Get miscellaneous information
            kwds = {"exception": get_exception(test_method),
                    "status": attribs["status"],
                    "started": attribs["started-at"],
                    "test_case": ptc,
                    "duration": int(attribs["duration-ms"]) / 1000.0} # TestNG in ms

            # If we have data-provider elements, we need to grab all the params
            if 'data-provider' in attribs:
                args = get_data_provider_elements(test_method)

                # Create a TestStep object.  The step field
                steps = ["Arg{}: {}".format(i, stringify_arg(arg))
                         for i, arg in enumerate(args)]
                string_steps = ", ".join(steps)
                add_step(test_cases, test_case_title, attribs, string_steps, **kwds)
            else:
                add_step(test_cases, test_case_title, attribs, None, **kwds)
    return test_cases


def parser(result_path, get_output=False):
    """
    Creates a TestNGToPolarion object for each <test-method> in the xml file

    :param result_path:
    :return:
    """
    log.info("Starting parse of xml result file...")
    tree = ET.parse(result_path)
    root = tree.getroot()
    titles = set()
    tests = []

    for klass in root.iter("class"):
        class_name = klass.attrib["name"]
        query = "title:{}*".format(class_name)
        log.info("Querying Polarion for: {}".format(query))
        matches = query_test_case(query)
        ptc = None
        testng = None

        last_test_method = None
        iteration = 1
        for test_method in klass:
            attribs = test_method.attrib
            attrs = attribs

            # if this is an is-config method, skip it
            if "is-config" in attribs and attribs["is-config"] == "true":
                continue

            method_name = attribs["name"]
            if last_test_method is None:
                last_test_method = method_name
            elif method_name != last_test_method:
                ptc = None
                last_test_method = method_name

            if ptc is None:
                for match in matches:
                    _, methodname = get_class_methodname(match.title)
                    if str(methodname) == str(method_name):
                        log.info("Found existing TestCase in Polarion: {}".format(match.title))
                        ptc = PylTestCase(uri=match.uri)
                        iteration = 1
                        break
                else:
                    log.info("No matching TestCase in Polarion was found")

            template = "\tIteration {}: parsing {}.{} {}"
            log.info(template.format(iteration, class_name, method_name, attribs['started-at']))
            iteration += 1
            test_case_title = class_name + "." + method_name

            # If we have data-provider elements, we need to grab all the params
            args = None
            if 'data-provider' in attribs:
                args = get_data_provider_elements(test_method)

            result = TestIterationResult(attrs, params=args, exception=get_exception(test_method))
            if test_case_title not in titles:
                testng = TestNGToPolarion(attrs, title=test_case_title, test_case=ptc,
                                          result=result, params=args)
                titles.add(test_case_title)
                tests.append(testng)
            else:
                testng.step_results.append(result)
    log.info("End parsing of xml results file")
    return tests


def download_url(urlpath, output_dir=".", binary=False):
    try:
        thing = urlopen(urlpath)
    except Exception as e:
        print(str(e))
        return

    parsed = urlparse(urlpath)
    filename = os.path.basename(parsed.path)
    writemod = "wb" if binary else "w"

    fobj = thing.read()
    if output_dir != ".":
        if not os.path.exists(output_dir):
            log.error("{0} does not exist".format(output_dir))
            log.error("Writing file to {0}".format(os.getcwd()))
        else:
            filename = "/".join([output_dir, filename])
    with open(filename, writemod) as downloaded:
        try:
            downloaded.write(fobj)
        except TypeError:
            with open(filename, "wb") as downloaded:
                downloaded.write(fobj)
    if not os.path.exists(filename):
        raise Exception("Could not write to {}".format(filename))
    return filename


class Transformer(object):
    """
    Parses the testng-results.xml file along with some metadata to generate Polarion data

    A basic model of the testng-results.xml::

      <suite>
        <test name="GUI: Registration ...>
          <class name=rhsm.gui.tests.register_tests ...>
            <test-method name=simple_register status=FAIL data-provider=userowners ...>
            <test-method name=unregister status=PASS ...>
            <test-method>...</test-method>
          </class>
          <class>...</class>
        </test>
        <test>...<test>
      </suite>

    An object of this class is used to do the following:
    1) For each <suite>, get the <test> elements, and generate a Requirement if needed based on name

       - For each <class> in <test>, and for each <test-method> in <class>...

         - Generate a TestCase if needed, and link to the Requirement of the <test>
    """
    # def __init__(self, project_id=None, result_path=None, template_id, requirement_prefix=TEST_REQUIREMENT_PREFIX,
    #             testrun_prefix="", existing_reqs=None, quick_query=True, base_queries=None,
    #             testrun_suffix="testing"):
    def __init__(self, config, requirement_prefix=TEST_REQUIREMENT_PREFIX, existing_reqs=None, quick_query=True, ):
        """

        :param project_id:
        :param result_path:
        :param template_id:
        :param requirement_prefix:
        :param testrun_prefix:
        :param existing_reqs:
        :param quick_query:
        :param base_queries:
        :param testrun_suffix:
        :return:
        """
        self.testrun_prefix = config.testrun_prefix
        self.testrun_suffix = config.testrun_suffix
        self.template_id = config.testrun_template
        self.result_path = config.result_path
        self.project_id = config.project_id
        self.requirement_prefix = requirement_prefix
        self._existing_requirements = existing_reqs
        self.quick_query = quick_query
        self.base_queries = [] if config.base_queries is None else config.base_queries
        self.config = config

        existing_test_cases = []
        for base in self.base_queries:
            bq = 'title:{}'.format(base)
            log.info("Performing Polarion query of {}".format(bq))
            tcs = query_test_case(bq)
            existing_test_cases.extend(tcs)
        self.existing_test_cases = existing_test_cases

    def generate_base_testrun_id(self, suite_name):
        """
        Generates a name that can be used to look up testruns

        This function also sanitizes these characters:
        \/.:*"<>|~!@#$?%^&'*()+`,='Tab'

        :param suite_name:
        :return:
        """
        check = [self.testrun_prefix, suite_name, self.testrun_suffix]
        new = replace(check)
        self.testrun_prefix, suite_name, self.testrun_suffix = new
        return "{} {} {}".format(self.testrun_prefix, suite_name, self.testrun_suffix)

    @property
    def existing_requirements(self):
        if self._existing_requirements is None:
            self._existing_requirements = query_requirement("RHSM")
        return self._existing_requirements

    @existing_requirements.setter
    def existing_requirements(self, val):
        log.error("Can not set existing_requirements after initialization")

    @staticmethod
    @profile
    def parse_by_element(result_path, element):
        if result_path.startswith("http"):
            result_path = download_url(result_path)

        tree = ET.parse(result_path)
        root = tree.getroot()
        return root.iter(element)

    def parse_suite(self, req_prefix=TEST_REQUIREMENT_PREFIX):
        """
        Gets all the <test> elements, and generates a Requirement if needed, then grabs all the <class> elements
        generating (or updating) a TestCase if needed.

        :param suite:
        :param req_prefix:
        :return:
        """
        log.info("Beginning parsing of {}...".format(self.result_path))
        suites = self.parse_by_element(self.result_path, "suite")

        testng_suites = {}
        for suite in suites:
            suite_name = suite.attrib["name"]
            tests = self.parse_tests(suite)
            testng_suites[suite_name] = tests

        return testng_suites

    def parse_tests(self, suite):
        """
        This function dives into the <suite> element, looking for it's <test> children.

        Once it finds a <test> element, it grabs the name attribute and uses the name in order to
        generate a title for a Requirement.  It then kicks off parsing of the <test-methods> passing
        in a list of the tests (which will contain all the generated TestNGToPolarion objects) and
        the titles of all the test methods.

        :param req_prefix:
        :param suite:
        :return:
        """
        log.info("Getting tests from suite {}...".format(suite.attrib["name"]))
        titles = set()
        requirements_set = set()
        tests = []

        # The <test> element contains the logical grouping of what the tests are testing.  So this is a
        # natural place to autogenerate a Requirement.  Since <test-methods> are children of a <test>,
        # and the <test> element maps to a TestNGToPolarion, we will pass the Requirement to the
        # TestNGToPolarion object so we can link the TestCase to the Requirement
        req = None
        for test in suite.iter("test"):
            attributes = test.attrib
            requirement_name = testify_requirement_name(attributes["name"], prefix=self.requirement_prefix)
            if requirement_name not in requirements_set:
                # First, check to see if we've got a requirement with this name, and if not, create one
                # query = title_query(requirement_name)
                if self.quick_query:
                    req = preq.is_in_requirements(requirement_name, self.existing_requirements)
                else:
                    req = preq.is_requirement_exists(requirement_name)
                if not req:
                    req = preq.create_requirement(self.project_id, requirement_name)
                requirements_set.add(requirement_name)

            # FIXME: This shouldn't happen, but what happens if it does?
            if req is None:
                log.error("No requirements were found or created")
            _, t = self.parse_test_methods(test, titles=titles, tests=tests, requirement=req)

        log.info("End parsing of xml results file")
        return tests

    def parse_test_methods(self, test, titles=None, tests=None, requirement=None):
        """
        Does the parsing of the <test-method> element

        :param test:
        :param titles:
        :param tests:
        :param requirement:
        :return:
        """
        if titles is None:
            titles = set()

        if tests is None:
            tests = []

        req_work_id = requirement.work_item_id
        for klass in test.iter("class"):
            t_class = TNGTestClass(test, klass.attrib)
            testng = None
            testng_test_name = test.attrib["name"]
            last_test_method = None
            iteration = 1
            cached_lookup = self.existing_test_cases

            for test_method in klass:
                if "is-config" in test_method.attrib and test_method.attrib["is-config"] == "true":
                    continue
                tm = TNGTestMethod(test_method, t_class, cached_query=cached_lookup)

                if last_test_method is None:
                    last_test_method = tm.method_name
                elif tm.method_name != last_test_method:
                    last_test_method = tm.method_name

                test_case_title = tm.full_name
                if test_case_title not in titles:
                    iteration = 1
                template = "\tIteration {}: parsing {} {}"
                log.info(template.format(iteration, test_case_title, tm.attribs['started-at']))
                iteration += 1

                if test_case_title not in titles:
                    testng = tm.make_testngtopolarion(req_work_id, testng_test_name)
                    titles.add(test_case_title)
                    tests.append(testng)
                else:
                    # We only get multiple test_case_title if it was a data-provider test so append results
                    testng.step_results.append(tm.result)

        return titles, tests


class TNGTestClass(object):
    def __init__(self, test_elem, attribs):
        self.name = attribs["name"]
        self.query_title = "title:{}*".format(self.name)

    def find_me(self, existing_tests=None, multiple=True):
        log.info("Querying Polarion for: {}".format(self.query_title))
        if existing_tests is None:
            matches = query_test_case(self.query_title)
        else:
            matches = cached_tc_query(self.name, existing_tests, multiple=multiple)
        return matches


class TNGTestMethod(object):
    """
    Python class to represent a <test-method>
    """
    def __init__(self, tm_elem, test_class, cached_query=None):
        """

        :param tm_elem: The Element of the <test-method>
        :param test_class: The Element of the <class>
        :param cached_query: a list of the already queried pylarion TestCase
        :return:
        """
        self._p_testcase = None
        self.parent_class = test_class
        self.class_name = test_class.name
        self.method_name = tm_elem.attrib["name"]
        self.full_name = "{}.{}".format(self.class_name, self.method_name)
        self.cached = cached_query
        self.attribs = tm_elem.attrib
        self.result = self._make_testiterationresult(tm_elem)

    @property
    def p_testcase(self):
        if self._p_testcase is None:
            self._p_testcase = self.find_matching_polarion_tc()
        return self._p_testcase

    @p_testcase.setter
    def p_testcase(self, val):
        if not isinstance(val, PylTestCase):
            raise Exception("p_testcase must be a pylarion.work_item.TestCase object")
        self._p_testcase = val

    def find_matching_polarion_tc(self):
        """
        Uses the cached lookup to find a matching class.methodname

        :return: pylarion.work_item.TestCase
        """
        matches = self.parent_class.find_me(existing_tests=self.cached, multiple=True)

        ptc = None
        if self._p_testcase is None:
            for match in matches:
                _, methodname = get_class_methodname(match.title)
                if str(methodname) == str(self.method_name):
                    log.info("Found existing TestCase in Polarion: {}".format(match.title))
                    ptc = PylTestCase(uri=match.uri)
        else:
            ptc = self._p_testcase
        return ptc

    def _make_testiterationresult(self, test_elem):
        result = None
        if 'data-provider' in self.attribs:
            args = get_data_provider_elements(test_elem)
            result = TestIterationResult(test_elem.attrib, params=args, exception=get_exception(test_elem))
        return result

    def make_testngtopolarion(self, requirement_id, testng_test_name):
        """
        Creates a TestNGToPolarion object based on this object

        :param requirement_id: a str of the work_item_id of the associated Requirement
        :param testng_test_name: the name of the test from the testng results.xml
        :return:
        """
        params = [] if self.result is None else self.result.params
        testng = TestNGToPolarion(self.attribs, title=self.full_name, test_case=self.p_testcase,
                                  result=self.result, params=params, requirement=requirement_id,
                                  testng_test=testng_test_name)

        return testng