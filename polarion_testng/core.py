from polarion_testng.utils import *
from pylarion.work_item import TestSteps as PylTestSteps
from pylarion.work_item import TestStep as PylTestStep

from polarion_testng.logger import log
import datetime
from polarion_testng.decorators import profile


class TestIterationResult(object):
    def __init__(self, attrs, params=None, output="", exception=None):
        self.status = attrs["status"]
        self.duration = str(int(attrs["duration-ms"]) / 1000.0)
        self.exception = exception
        self.attributes = {} if attrs is None else attrs
        self.output = output
        self.started = attrs["started-at"] if "started-at" in attrs else datetime.datetime.now()

        self.params = [] if params is None else params
        self.args = {"Arg{}".format(i): v for i, v in enumerate(self.params)}


# An array of TestNGToPolarion objects will be the container that represents Polarion "test iterations"
# The index in the array will be the test iteration number, and this object will know the parameterized
# fields (self.params).  The TestIterationResult object (self.step_result) will contain the values of the
# parameters for that iteration run
class TestNGToPolarion(object):
    """
    A representation of the TestNG @Test and it's mapping to relevant Polarion fields
    """
    ALLOWED_FIELDS = ["name", "status", "signature", "is-config", "duration-ms", "started-at",
                      "finished-at", "description", "data-provider", "depends-on-methods"]

    def __init__(self, attrs, title, test_case=None, result=None, params=None, project=None, requirement=None):
        self.title = title
        self.attributes = attrs
        self.description = "" if "description" not in attrs else attrs["description"]
        self.polarion_tc = test_case
        self.data_provider = "data-provider" in attrs
        self.params = [] if params is None else params
        self.args = self.args = {"Arg{}".format(i):v for i,v in enumerate(self.params)}
        self.step_results = [result] if result is not None else []
        self._status = None
        self.project = get_default_project() if project is None else project
        self._author = None
        self.requirement = requirement

    @property
    def status(self):
        """
        Determines the status from the step_results

        :return:
        """
        if self._status is None:
            self._status = self.attributes["status"]

        return self._status

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
        steps.keys = ["args", "expectedResult"]

    def create_test_record(self, test_run, run_by="stoner"):
        """
        Adds a TestRecord to a TestRun and associates it with the TestCase

        :param test_run: a pylarion TestRun object
        :param run_by: (str) identifies who executed the test
        """
        tc_id = self.polarion_tc.work_item_id
        result = self.status
        executed_by = run_by

        def comment_string(i, s):
            base = "{} {}\t".format(i, s.status)
            # This seems to be dramatically slowing down Polarion, so take it out for now
            if s.exception:
                exc_info = s.exception["message"] + "<br>" + \
                           s.exception["stack_trace"] + "<br>"
                base += "<br>" + exc_info
            return base

        comment = "<br>".join(comment_string(i, step) for i,step in enumerate(self.step_results))

        # Get the first step for our start time, and the last for our finish
        formatter = "%Y-%m-%dT%H:%M:%SZ"
        strptime = datetime.datetime.strptime

        if self.step_results:
            last_step = itz.last(self.step_results)
            dt_start = strptime(self.step_results[0].started, formatter)
            dt_finish = strptime(last_step.started, formatter)
            time_delta = dt_finish - dt_start
            duration = time_delta.seconds + float(last_step.duration)
        else:
            if len(self.step_results) >= 1:
                raise Exception("Should be at least one step_results")
            duration = float(self.step_results[0].duration)
            dt_start = strptime(self.step_results[0].started, formatter)

        result = convert_status(result)
        if result == "waiting":
            log.info("Skipping TestRecord for {} due to status of SKIP".format(tc_id))
            return

        comment = unicode(comment, encoding='utf-8')
        kwds = {"test_comment": comment, "test_case_id": tc_id, "test_result": result,
                "executed": dt_start, "duration": duration, "executed_by": executed_by}

        log.info("Creating TestRecord for {}".format(self.title))
        self.add_test_record(test_run, **kwds)

    @profile
    def add_test_record(self, test_run, **kwargs):
        test_run.add_test_record_by_fields(**kwargs)

    @profile
    def add_test_record_obj(self, test_run, test_record):
        test_run.add_test_record_by_object(test_record)

    @staticmethod
    def validate_test(tc):
        for key, val in TC_KEYS.items():
            tid = tc.work_item_id
            log.debug("Checking if {} is set for test case {}".format(key, tid))
            current = getattr(tc, key)
            if not current:  # set to default
                setattr(tc, key, val)

    @profile
    def create_polarion_tc(self):
        """
        Given the polarion_testng.TestCase, convert it to the equivalent pylarion.work_item.TestCase
        """
        # Check to see if we already have an existing test case
        if self.polarion_tc:
            tc = self.polarion_tc
            self.validate_test(tc)

            # See if the Polarion Test Case has steps. The TestCase will contain a TestSteps array of size 1
            # The step will have 2 columns (or key-value pairs)
            # | step | expectedResult
            # +======+===============
            # | args | PASS
            test_steps = tc.get_test_steps()
            steps = test_steps.steps

            # If this TestCase has more than 1 TestStep, it's the older workaround where a TestStep was a row
            # of data in the 2d array.  Moving to the SR2 2015 release with parameterized testing instead
            if len(steps) > 1:
                tc.set_test_steps()  # Empty the TestSteps
            if len(steps) == 0:
                step = self.make_polarion_test_step()
                tc.set_test_steps([step])
        else:
            tc = PylTestCase.create(self.project, self.title, self.description, **TC_KEYS)

            # Create PylTestSteps if needed and add it
            if self.step_results:
                step = self.make_polarion_test_step()
                tc.set_test_steps([step])
            else:
                raise Exception("No step result in TestNGToPolarion")
        return tc

    def make_polarion_test_step(self):
        """
        Creates pylarion TestSteps
        """
        ts = PylTestStep()
        args = ",".join(["Arg{}".format(i) for i in range(len(self.params))])
        step_args = unicode(args, encoding='utf-8')
        ts.values = [step_args, "PASS"]
        return ts
