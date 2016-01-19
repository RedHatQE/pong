import xml.etree.ElementTree as ET

from polarion_testng.core import TestIterationResult, TestNGToPolarion
from polarion_testng.decorators import fixme
from polarion_testng.logger import log
from polarion_testng.utils import *


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
    This is the main function which parses the polarion_testng-results.xml file and creates a dictionary of
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
                add_step(test_cases, test_case_title, attrs, string_steps, **kwds)
            else:
                add_step(test_cases, test_case_title, attrs, None, **kwds)
    return test_cases


def parser(result_path, get_output=False):
    """
    This is the main function which parses the polarion_testng-results.xml file and creates a dictionary of
    test case title -> list of {attributes: (result of testmethod),
                                args: (the arguments for this step)}

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
