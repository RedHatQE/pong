"""
This module is only here for posterity and will be removed once the new code is fully fleshed out

# FIXME: The SR2 2015 Polarion GA has the notion of Test Case iterations and Test Case parameters, where
# each iteration of a test case is used with differing values of the parameters.  The whole TestStepRecord
# class here was a workaround by translating a data driven row from TestNG into a TestStep (in Polarion)
# But moving forward, that will no longer be the case (once the iterations and parameterization fields are
# accessible from pylarion).  Instead, all automation tests will be a single TestStep, but a data provider
# test will have one or more Polarion parameters (which appears to be associated with the Polarion TestStep)
# In the manual web interface, the user can then select the TestCase and there will be a Test Parameters section
# with a Add Iteration button.  A field with all the parameter names will show up, and the values for the
# parameters can be entered.
#
# That describes the manual portion, but the SOAP interface does not yet support this.  However, looking at the
# interface, it seems apparent that the Parameters belong to a (Polarion) TestStep, and the iterations value
# seems to belong to the TestPlanning class (which is new)
"""


from pylarion.work_item import TestCase as PylTestCase
from pylarion.work_item import TestSteps as PylTestSteps
from pylarion.work_item import TestStep as PylTestStep
from pylarion.test_record import TestRecord

import copy
import hashlib
from polarion_testng.logger import log
import datetime

from polarion_testng.decorators import profile
from polarion_testng.utils import *


class ParseException(Exception):
    pass


class TestStepRecord(object):
    """
    Representation of an executed run of a TestCase of a particular step
    """
    KEYS = ["args", "expectedResult", "uuid"]

    def __init__(self, step, expected=PASS, status=PASS, enabled=True,
                 exception=None, output=None, started=None, duration=1.00):
        """
        :param step:
        :param expected: Normally should always be PASS (negative tests could be FAIL here but even they
                         they should normally be PASS)
        :param status: The result of the TestCase as a whole
        :param enabled: Whether the TestCase is enabled in Polarion or not
        :param exception: If the execution of this test case with these arguments threw an exception then
                          the stack trace is included here as a str
        :param output: (str) output from the execution of this step
        :param started: (datetime) a timestamp of when the step was executed
        :param duration: (float) a time in seconds of how long execution of the step took
        """
        self.step = step
        self.expected = expected
        self.status = status
        self.enabled = enabled
        self.exception = exception
        self.output = output
        self.duration = duration
        self.started = started

        m = hashlib.sha1()
        m.update(self.step)
        self.uuid = m.hexdigest()  # Use this to compare steps

    def make_polarion_test_step(self):
        """
        Creates pylarion TestSteps
        """
        ts = PylTestStep()
        step_args = unicode(self.step, encoding='utf-8')
        ts.values = [step_args, "PASS", self.uuid]
        return ts

    def compare(self, polarion_step):
        pass


class TestCase(object):
    """
    Representation of the execution of a test in TestNG

    This class really represents several things:
    1. Parsed results from the polarion_testng-results.xml (the <test-method> element)
    2. A means to create a Polarion Test Case given this object information
    3. A means to create a TestRecord in Polarion given this object's information
    """
    ALLOWED_FIELDS = ["name", "status", "signature", "is-config", "duration-ms", "started-at",
                      "finished-at", "description", "data-provider", "depends-on-methods"]

    # FIXME:  This probably shouldn't be a class level attribute
    tc_keys = {"caseimportance": "high", "caselevel": "component", "caseposneg": "positive",
               "testtype": "functional", "subtype1": "reliability", "caseautomation": "automated"}

    def __init__(self, title, results, project=None):
        """
        Initialization for a TestCase

        :param title: title description (this is *not* the id and is not unique)
        :param results: a dictionary of additional information
        :param project: project ID (will default to .pylarion project)
        :return:
        """
        self.title = title
        self.data_provider = True if len(results) > 1 else False
        self.results = results
        self._status = PASS
        self.steps = self._get_steps()
        self._project = project
        self._description = None
        self._author = None
        self.test_class, self.method_name = get_class_methodname(self.title)
        self.polarion_tc = self.results["test_case"]

    def _check_attrs(self, attribs):
        for k, v in attribs.items():
            if k not in TestCase.ALLOWED_FIELDS:
                raise ParseException("{} is not allowed in TestCase".format(k))

    def _get_steps(self):
        steps = []
        for row in self.results["steps"]:
            self._check_attrs(row["attributes"])
            ts_state = copy.copy(row)
            if row["args"] is None:
                break
            for key in ["attributes", "args"]:
                del ts_state[key]

            steps.append(TestStepRecord(row["args"], **ts_state))
        self._steps = steps
        return self._steps

    @property
    def status(self):
        """
        Looks through all the run steps and if any are not "PASS", it fails the run
        """
        if self.steps:
            for step in self.steps:
                # If any test-method invocation fails, the TestCase fails
                if step.status != PASS:
                    self._status = FAIL
                    break
        else:
            self._status = self.results["steps"][0]["attributes"]["status"]
        return self._status

    @status.setter
    def status(self, val):
        log.info("Can not set status manually to {}".format(val))

    @property
    def project(self):
        """
        Retrieves the project for this TestCase (eg RedHatEnterpriseLinux7)

        If no project was passed to init, the ~/.pylarion file will be used to
        determine the project id

        :return: (str) the project id
        """
        if self._project is None:
            self._project = get_default_project()
        return self._project

    @project.setter
    def project(self, val):
        self._project = val

    @property
    def description(self):
        """
        Retrieves a description from the parsed polarion_testng-results.xml for the test

        In TestNG, a possible field for the @Test annotation is 'description'.  The
        parser will read in this attribute from the xml so that it can be used to
        populate the Polarion TestCase description field.  If this field was not
        set in the annotation in the source code, it will be populated as 'TBD'

        :return: (str or unicode)
        """
        attrs = self.results["steps"][0]["attributes"]
        if self._description is None:
            if "description" in attrs:
                self._description = attrs["description"]
            else:
                self._description = "TBD"
        return self._description

    @description.setter
    def description(self, val):
        self._description = val

    @property
    def author(self):
        if self._author is None:
            config = ConfigParser.ConfigParser()
            config.read(PYLARION_CONFIG)
            self._author = config.get("webservice", "user")
        return self._author

    @author.setter
    def author(self, val):
        self._author = val

    def query_test_case(self, query=None):
        """
        """
        if query is None:
            query = "title:{}".format(self.title)
        return PylTestCase.query(query)

    @staticmethod
    def create_base_test_steps():
        """
        Creates a pylarion.test_steps.TestSteps object with associated keys

        :return:
        """
        steps = PylTestSteps()
        steps.keys = TestStepRecord.KEYS

    def create_test_record(self, test_run, run_by="stoner"):
        """
        Creates a TestRecord and associates it with the TestCase

        :param test_run: a pylarion TestRun object
        :param run_by: (str) identifies who executed the test
        """
        tc_id = self.polarion_tc.work_item_id
        result = self.status
        executed_by = run_by

        def comment_string(s):
            base = s.status + " " + s.uuid + "\t" + s.step
            # This seems to be dramatically slowing down Polarion, so take it out for now
            if s.exception:
                exc_info = s.exception["message"] + "<br>" + \
                           s.exception["stack_trace"] + "<br>"
                base += "<br>" + exc_info
            return base

        comment = "<br>".join(comment_string(step) for step in self.steps)
        # Add any exception information for non-data-providers
        if result == "failed" and not self.steps:
            exc = self.results["steps"][0]["exception"]
            exc_info = exc["message"] + "<br>" + \
                       exc["stack_trace"] + "<br>"
            comment += "<br>" + exc_info

        # Get the first step for our start time, and the last for our finish
        formatter = "%Y-%m-%dT%H:%M:%SZ"
        strptime = datetime.datetime.strptime

        if self.steps:
            last_step = itz.last(self.steps)
            dt_start = strptime(self.steps[0].started, formatter)
            dt_finish = strptime(last_step.started, formatter)
            time_delta = dt_finish - dt_start
            duration = time_delta.seconds + last_step.duration
        else:
            if len(self.results["steps"]) != 1:
                raise Exception("Should be one result in TestCase")
            duration = self.results["steps"][0]["duration"]
            dt_start = strptime(self.results["steps"][0]["started"], formatter)

        result = convert_status(result)
        if result == "waiting":
            log.info("Skipping TestRecord for {} due to status of SKIP".format(tc_id))
            return

        comment = unicode(comment, encoding='utf-8')
        kwds = {"test_comment": comment, "test_case_id": tc_id, "test_result": result,
                "executed": dt_start, "duration": duration, "executed_by": executed_by}

        log.info("Creating TestRecord for {}".format(self.title))
        self.add_test_record(test_run, **kwds)

    def create_polarion_test_record(self, **kwargs):
        """
        Creates a pylarion TestRecord object given the possible kwargs
        """
        record = TestRecord(project_id=self.project, test_case_id=self.polarion_tc.work_item_id)
        for k, v in kwargs.items():
            try:
                setattr(record, k, v)
            except AttributeError as ae:
                log.error("Can not assign {}={} to {}".format(k, v, record))
        return record

    @profile
    def add_test_record(self, test_run, **kwargs):
        test_run.add_test_record_by_fields(**kwargs)

    @profile
    def add_test_record_obj(self, test_run, test_record):
        test_run.add_test_record_by_object(test_record)

    @staticmethod
    def validate_test(tc):
        for key, val in TestCase.tc_keys.items():
            tid = tc.work_item_id
            log.debug("Checking if {} is set for test case {}".format(key, tid))
            current = getattr(tc, key)
            if not current:  # set to default
                setattr(tc, key, val)

    def create_polarion_tc(self):
        """
        Given the polarion_testng.TestCase, convert it to the equivalent pylarion.work_item.TestCase
        """
        # Check to see if we already have an existing test case
        if self.polarion_tc:
            tc = self.polarion_tc
            self.validate_test(tc)

            # See if the Polarion Test Case has steps. The TestCase will contain a TestSteps array.
            # It will have 3 columns (or key-value pairs)
            # | uuid       | step | expectedResult
            # +============+======+===============
            # | 73c6146... | args | PASS
            #
            # Check the existing test steps and compare to this TestCase.  If the TestStep does not
            # exist in the current Polarion Test Case, add it. In the matching Test Record, list
            # only the steps that were executed.
            test_steps = tc.get_test_steps()
            steps = test_steps.steps
            if test_steps:
                # Get the key-val pairs and look for the uuid
                step_maps = []

                for step in test_steps.steps:
                    step_maps.append({k: sanitize(v) for k, v in zip(TestStepRecord.KEYS, step.values)})

                # Compare the uuids from the TestStep.uuid to those retrieved from the Polarion Steps
                # If we find a TestStep uuid not in the Polarion Steps, add the TestStep to the
                # Polarion steps
                uuids = [step["uuid"] for step in step_maps]
                matched = filter(lambda x: x if x.uuid not in uuids else None, self.steps)
                if any(matched):
                    # if there's matches, we need to add that step]
                    for ts in matched:
                        new_ts = ts.make_polarion_test_step()
                        steps.append(new_ts)
                    tc.set_test_steps(steps)

        else:
            tc = PylTestCase.create(self.project, self.title, self.description, **TestCase.tc_keys)

            # Create PylTestSteps if needed and add it
            if self.steps:
                steps = []
                for ts in self.steps:
                    pyl_ts = ts.make_polarion_test_step()
                    steps.append(pyl_ts)
                tc.set_test_steps(steps)

        return tc


def make_test_cases(test_cases):
    """
    Takes a list of dicts and converts to a list TestCase objects

    The parse_results() function will return a list of dicts that can
    be consumed by this function

    :param test_cases: dict of title:results
    :return:
    """
    tests = []

    for title, keymap in test_cases.items():
        tests.append(TestCase(title, keymap))
    return tests