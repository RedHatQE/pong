"""
Parses a testng-results.xml file and

1. Creates a Test Case based on class.method_name
   - It will check to see if an existing Test Case with a matching title already exists and return it
   - Otherwise, it will create a new Test Case
2. It will create a Test Step to be included in the TestCase
   - Step will be stringified arguments
   - Expected Result will be passed
3. If there is an existing Test Case, check to see if it has steps
   - If it does not, create a new Test Case?
   - If does, but number of steps do not match?
4. If creating a new test case insert the Test Steps into it
5. For each Test Case update it
6. For each Test Case, create a matching Test Record

"""
import sys

from pong.logger import log
from pong.utils import *
from pong.decorators import retry, profile
from pong.parsing import Transformer
from pong.configuration import kickstart, CLIConfigurator

OLD_EXPORTER = 0
TESTING = 0


def print_tr(obj, fld):
    print fld, "=", getattr(obj, fld)


class Exporter(object):
    """
    A collection of TestCase objects.
    """
    def __init__(self, transformer):
        self.tests = None
        self.transformer = transformer
        self._project = transformer.project_id
        self.collect()

    def collect(self):
        testng_suites = self.transformer.parse_suite()
        self.tests = testng_suites

        for k, tests in testng_suites.items():
            not_skipped = filter(lambda x: x.status != SKIP, tests)
            # TODO: It would be nice to have show which Tests got skipped due to dependency on another
            # test that failed, or because of a BZ blocker
            if TESTING:
                import random
                random.shuffle(not_skipped)
                not_skipped = itz.take(5, not_skipped)

            total = len(not_skipped) - 1
            updated = []
            for i, test_case in enumerate(not_skipped, start=0):
                log.info("Getting TestCase: {} out of {}".format(i, total))
                pyl_tc = test_case.create_polarion_tc()
                self._update_tc(pyl_tc)
                test_case.polarion_tc = pyl_tc
                updated.append(test_case)

            self.tests[k] = updated

        for k, tests in self.tests.items():
            for tc in tests:
                if tc.polarion_tc is None:
                    log.info("WTF.  {} has tc.polarion_tc is None".format(tc.title))

        print self.tests

    @property
    def project(self):
        if self._project is None:
            self._project = get_default_project()
        return self._project

    @project.setter
    def project(self, val):
        self._project = val

    @retry
    def _update_tr(self, test_run):
        test_run.update()

    @retry
    def _update_tc(self, test_case):
        test_case.update()

    @profile
    def create_test_run(self, template_id, test_run_base=None, runner="stoner"):
        """
        Creates a new Polarion TestRun

        :param template_id: id of the template to use for TestRun
        :param test_run_base: a str to look up most recent TestRuns (eg "Jenkins Run" if
                              the full name of TestRuns is "Jenkins Run 200"
        :param runner: str of the user id (eg stoner, not "Sean Toner")
        :return: None
        """
        for s, testngs in self.tests.items():
            if test_run_base is None:
                test_run_base = self.transformer.generate_base_testrun_id(s)

            # Find our latest run.  If it doesn't exist, we'll generate one
            tr = get_latest_test_run(test_run_base)
            if tr:
                new_id = make_test_run_id_from_latest(tr)
            else:
                new_id = test_run_base + " 1"
            log.info("Creating new Test Run ID: {}".format(new_id))
            retries = 3
            while retries > 0:
                try:
                    test_run = TestRun.create(self.project, new_id, template_id)
                    break
                except Exception as ex:
                    log.warning("Got exception {}".format(ex))
                    retries -= 1
                    log.warning("Retrying {} more times".format(retries))
            else:
                raise Exception("Could not create a new TestRun")
            test_run.status = "inprogress"

            test_run._set_custom_field("arch", self.transformer.config.distro.arch)
            test_run._set_custom_field("variant", self.transformer.config.distro.variant)
            for tc in testngs:
                tc.create_test_record(test_run, run_by=runner)

            log.info("Created test run for {}".format(new_id))
            test_run.status = "finished"

    def update_test_run(self, test_run, runner="stoner"):
        """
        Given a TestRun object, update it given the TestCases contained in self

        :param test_run: pylarion TestRun object
        :param runner: the user who ran the tests
        :return: None
        """
        for _, testngs in self.tests.items():
            # Check to see if the test case is already part of the test run
            for tc in testngs:
                if tc.polarion_tc is None:
                    raise Exception("How did this happen?  {} has no TestCase".format(tc.title))
                if check_test_case_in_test_run(test_run, tc.polarion_tc.work_item_id):
                    continue
                tc.create_test_record(test_run, run_by=runner)

    @staticmethod
    def get_test_run(test_run_id):
        """
        Looks for matching TestRun given a test_run_id string

        :param test_run_id:
        :return:
        """
        tr = TestRun.search('"{}"'.format(test_run_id), fields=[u"test_run_id"],
                            sort="created")
        tr = itz.first(tr)
        if tr:
            tr = TestRun(uri=tr.uri)
        return tr

    def create_test_run_template(self, template_id, case_type="automatedProcess", query=None):
        """
        Creates a TestRun template that can be used as a basis for other TestRuns

        :param template_id: a unique str to give as ID for this template
        :param case_type:
        :param query:
        :return:
        """
        test_template = TestRun.create_template(self.project, template_id, query=query,
                                                select_test_cases_by=case_type)
        return test_template

    def generate_testrun_id(self):
        """
        The test run id will be a concatenation of several strings

        prefix + suite_name + suffix + unique_id

        :return:
        """
        pass

    @staticmethod
    def export(result=None):
        """
        This is the method that actually does the processing of the configuration map and does what needs to be done

        :param result:
        :return:
        """
        if result is None:
            result = kickstart()

        cli_cfg = result["cli_cfg"]
        args = cli_cfg.args
        config = result["config"]

        # Save off our original .pylarion in case the user passes in a project-id that is different
        # If the user selects --set-project-id, changes from -p are permanent
        reset_project_id = False
        using_pylarion_path = config.pylarion_path
        original_project_id = cli_cfg.original_project_id

        # FIXME:  Turn these into functions and decorate them
        if args.query_testcase:
            tests = query_test_case(args.query_testcase)
            for test in tests:
                msg = test.work_item_id + " " + test.title
                log.info(msg)
        if args.get_default_project_id:
            log.info(get_default_project())
        if args.set_project:
            reset_project_id = True
            CLIConfigurator.set_project_id(config.pylarion_path, config.set_project)
        if args.get_latest_testrun:
            tr = get_latest_test_run(args.get_latest_testrun)
            for k, v in make_iterable(tr):
                print "{}={}".format(k, v)

        if any([args.query_testcase, args.get_default_project_id, args.get_latest_testrun]):
            sys.exit(0)

        # Get the project_id.  If the passed in value is different, we need to edit the .pylarion file
        default_project_id = cli_cfg.original_project_id
        if config.project_id != default_project_id:
            CLIConfigurator.set_project_id(using_pylarion_path, config.project_id)

        default_queries = [] if args.base_queries is None else args.base_queries
        transformer = Transformer(config)
        suite = Exporter(transformer)

        # Once the suite object has been initialized, generate a test run with associated test records
        if not config.generate_only:
            if config.update_run:
                update_id = config.update_run
                log.info("Updating test run {}".format(update_id))
                tr = Exporter.get_test_run(update_id)
                suite.update_test_run(tr)
            else:
                log.info("Creating new TestRun...")
                suite.create_test_run(config.testrun_template)
        log.info("TestRun information completed to Polarion")

        if reset_project_id:
            try:
                import shutil
                backup = using_pylarion_path + ".bak"
                shutil.move(backup, using_pylarion_path)
            except Exception as ex:
                CLIConfigurator.set_project_id(using_pylarion_path, original_project_id)


if __name__ == "__main__":
    config_map = kickstart()
    Exporter.export(config_map)

