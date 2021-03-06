from pong.utils import *

from pong.logger import log
import datetime
from pong.decorators import profile


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

    def __init__(self, attrs, cm_name, test_case=None, result=None, params=None, project=None, requirement=None,
                 testng_test=None, prefix=""):
        """

        :param attrs: A dict of the <test-method> attributes
        :param cm_name: The class.method name of the <test-method> (becomes the TestRecord title)
        :param test_case: A pylarion TestCase object
        :param result:
        :param params: A list of the arguments used from a data provider test
        :param project: a string of the project id
        :param requirement: a pylarion Requirement object
        :param testng_test: the <test name=""> that represents what logical test this object belongs to
        :return:
        """
        self.class_method = cm_name
        self.prefix = prefix
        self.title = prefix + cm_name
        self.attributes = attrs
        self.polarion_tc = test_case
        self.data_provider = "data-provider" in attrs
        self.params = [] if params is None else params
        self.args = self.args = {"Arg{}".format(i):v for i,v in enumerate(self.params)}
        self.step_results = [result] if result is not None else []
        self._status = None
        self.project = get_default_project() if project is None else project
        self._author = None
        self.requirement = requirement  # PylRequirement(project_id=self.project, work_item_id=requirement)
        self.testng_test = testng_test

        if "description" not in attrs:
            self.description = u""
        else:
            try:
                self.description = attrs["description"].decode(encoding="utf8")
            except UnicodeError:
                raw = attrs["description"].encode("utf-8")
                self.description = unicode(raw, encoding="utf-8", errors="replace")

    @property
    def status(self):
        """
        Determines the status from the step_results

        :return:
        """
        if self._status is None:
            result = self.attributes["status"]
            log.debug("Checking step_results of {}: {}".format(self.title, self.step_results))
            no_nones = filter(lambda x: x is not None, self.step_results)
            self.step_results = no_nones
            if any(filter(lambda ti: ti.status != "PASS" and ti.status != "SKIP", self.step_results)):
                result = FAIL
            self._status = result
        return self._status

    @status.setter
    def status(self, val):
        log.error("Can not set self.status.  Value of {} being ignored".format(val))

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
        from pylarion.work_item import TestCase as PylTestCase
        if query is None:
            query = "title:{}".format(self.title)
        return PylTestCase.query(query)

    @staticmethod
    def create_base_test_steps():
        """
        Creates a pylarion.test_steps.TestSteps object with associated keys

        :return:
        """
        from pylarion.work_item import TestSteps as PylTestSteps
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
            if s.exception:
                exc_info = s.exception.get("message", "") + "<br>" + \
                           s.exception.get("stack_trace", "") + "<br>"
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
            duration = float(self.attributes["duration-ms"])
            dt_start = strptime(self.attributes["started-at"], formatter)

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

    def link_requirements(self, tc_obj):
        """

        :param tc_obj:
        :return:
        """
        linked_items = tc_obj.linked_work_items
        if not self.requirement:
            log.warning("No requirement exists for this test case")
        else:
            duplicates = filter(lambda x: x == self.requirement, [li.work_item_id for li in linked_items])
            num_duplicates = len(duplicates)
            if num_duplicates == 0:
                log.info("Linking requirement {} to TestCase {}".format(self.requirement, tc_obj.work_item_id))
                tc_obj.add_linked_item(self.requirement, "verifies")
            elif num_duplicates > 1:
                msg = "Found duplicate linked Requirements {} for TestCase {}.  Cleaning...."
                log.warning(msg.format(itz.first(duplicates), tc_obj.work_item_id))
                for _ in range(len(duplicates) - 1):
                    tc_obj.remove_linked_item(self.requirement, "verifies")
            else:
                msg = "Requirement {} already linked to TestCase {}"
                log.info(msg.format(itz.first(duplicates), tc_obj.work_item_id))

    @profile
    def create_polarion_tc(self):
        """
        Given the pong.TestCase, convert it to the equivalent pylarion.work_item.TestCase
        """
        t = lambda x: unicode.encode(x, encoding="utf-8", errors="ignore") if isinstance(x, unicode) else x
        desc, title = [t(x) for x in [self.description, self.title]]
        # Check to see if we already have an existing test case
        tc = None
        if self.polarion_tc:
            log.info("Getting TestCase for {}: {}".format(title, desc))
            tc = self.polarion_tc
            self.validate_test(tc)

            if not self.polarion_tc.title.startswith(self.prefix):
                self.polarion_tc.title = self.prefix + self.polarion_tc.title

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
            log.info("Generating new TestCase for {} : {}".format(title, desc))
            WORKAROUND_949 = False
            try:
                self.description.decode(encoding="utf-8")
            except UnicodeError:
                raw = self.description.encode("utf-8")
                self.description = unicode(raw, encoding="utf-8", errors="replace")
                try:
                    self.description.decode(encoding="utf-8")
                except UnicodeError:
                    WORKAROUND_949 = True

            if WORKAROUND_949:
                self.description = unicode("", encoding="utf-8")

            from pylarion.work_item import TestCase as PylTestCase
            tc = PylTestCase.create(self.project, self.title, self.description, **TC_KEYS)

            # Create PylTestSteps if needed and add it
            if self.step_results:
                step = self.make_polarion_test_step()
                tc.set_test_steps([step])

            if not tc:
                raise Exception("Could not create TestCase for {}".format(self.title))
            else:
                self.polarion_tc = tc

        self.link_requirements(tc)
        self.polarion_tc.update()
        return tc

    def make_polarion_test_step(self):
        """
        Creates pylarion TestSteps
        """
        from pylarion.work_item import TestStep as PylTestStep
        ts = PylTestStep()
        args = ",".join(["Arg{}".format(i) for i in range(len(self.params))])
        step_args = unicode(args, encoding='utf-8')
        ts.values = [step_args, "PASS"]
        return ts
