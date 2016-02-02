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
import toolz

from polarion_testng.logger import log
from polarion_testng.utils import *
from polarion_testng.decorators import retry, profile
from polarion_testng.parsing import parser, Transformer
from polarion_testng.jenkins import get_test_environment, TestEnvironment

# Jenkins created environment variables
if 0:
    WORKSPACE = os.environ["WORKSPACE"]
    TEST_RUN_TEMPLATE = os.environ["TEST_RUN_TEMPLATE"]
    TESTNG_RESULTS_PATH = os.path.join(WORKSPACE, "test-output/polarion_testng-results.xml")

OLD_EXPORTER = 0
TESTING = 0


def fltr(obj, f):
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
    def create_test_run(self, template_id, test_run_base, runner="stoner"):
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
                except:
                    retries -= 1
            else:
                raise Exception("Could not create a new TestRun")
            test_run.status = "inprogress"
            log.info("Creating test run for {}".format(s))

            for tc in testngs:
                tc.create_test_record(test_run, run_by=runner)

            test_run.status = "finished"
            #self._update_tr(test_run)

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
    def get_test_run(test_run_id, create=True):
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

    def cfg(self):
        """
        Kicks everything off

        :return:
        """
        import polarion_testng.configuration as pcfg

        configurators = []
        env_cfg = pcfg.OSEnvironmentConfigurator()
        cli_cfg = pcfg.CLIConfigurator()
        yml_cfg = pcfg.YAMLConfigurator()
        if cli_cfg.args.environment:
            jnk_cfg = pcfg.JenkinsConfigurator()



# FIXME: this has gotten huge.  Let's turn this into a separate function or class
# Also, we should have a config file, where the CLI will override the config file
if __name__ == "__main__":
    import hy
    import polarion_testng.cli as cli

    parse_arg = cli.gen_argparse()
    args = parse_arg.parse_args()

    # Save off our original .pylarion in case the user passes in a project-id that is different
    # If the user selects --set-project-id, this change is permanent, but if --project-id (or -p)
    # is used, this is just a temporary change
    reset_project_id = False
    get_pylarion_path = lambda: args.pylarion_path or os.path.expanduser("~/.pylarion")
    using_pylarion_path = get_pylarion_path()
    original_project_id = get_default_project(pylarion_path=using_pylarion_path)

    project_id = args.project_id
    results_path = args.result_path
    template_id = args.template_id  # eg "sean toner test template"
    testrun_id = args.testrun_id    # eg "pylarion exporter testing"
    gen_only = args.generate_only
    update_id = args.update_run
    test_env = args.environment_file
    arch = args.arch
    variant = args.variant

    for a in dir(args):
        obj = getattr(args, a)
        if a.startswith("_"):
            continue
        if callable(obj):
            continue
        log.info("{} = {}".format(a, obj))

    # Check to see if the -e option was passed in to look for the test environment file.  If so,
    # we will use it to get the project id, and path to the result file
    te = None
    if results_path is None and test_env is None:
        log.error("Must pass in either a -r or -e to get the testng-results.xml file")
        sys.exit(0)
    if test_env is not None:
        log.info("Overriding other arguments passed in from CLI")
        te = get_test_environment(test_env, )
        results_path = te.results_path
        log.info("\tresults_path is now {}".format(results_path))
        project_id = te.project_id
        log.info("\tproject_id is now {}".format(project_id))
        arch = te.distro_arch
        log.info("\tarch is now {}".format(arch))
        variant = te.distro_variant
        log.info("\tvariant is now {}".format(variant))

    # CLI options that will quit if not None
    query_testcase = args.query_testcase
    get_default_project_id = args.get_default_project_id
    get_latest_testrun = args.get_latest_testrun

    # FIXME:  Turn these into functions and decorate them
    if query_testcase:
        tests = query_test_case(query_testcase)
        for test in tests:
            #test = PylTestCase(uri=t.uri)
            msg = test.work_item_id + " " + test.title
            log.info(msg)
    if get_default_project_id:
        log.info(get_default_project())
    if args.set_project_id:
        reset_project_id = True
        cli.set_project_id()
    if get_latest_testrun:
        tr = get_latest_test_run(testrun_id)

        valid = toolz.partial(fltr, tr)
        fields = filter(valid, dir(tr))

        for attr in fields:
            print_tr(tr, attr)
    if any([query_testcase, get_default_project_id, get_latest_testrun]):
        sys.exit(0)

    # Get the project_id.  If the passed in value is different, we need to edit the .pylarion file
    if project_id is None and test_env is None:
        raise Exception("Must pass in either -p or -e to get project_id")
    default_project_id = get_default_project()
    if project_id != default_project_id:
        cli.set_project_id(using_pylarion_path, project_id)

    trans = 0

    default_queries = [] if args.base_queries is None else args.base_queries
    transformer = Transformer(project_id, results_path, template_id, base_queries=default_queries, test_env=te)
    if OLD_EXPORTER:
        # Will auto-generate polarion TestCases
        suite = Exporter(results_path)
    else:
        suite = Exporter(transformer)

    # Once the suite object has been initialized, generate a test run with associated test records
    if not gen_only:
        if update_id:
            log.info("Updating test run {}".format(update_id))
            tr = Exporter.get_test_run(update_id)
            suite.update_test_run(tr)
        else:
            log.info("Creating new TestRun...")
            suite.create_test_run(template_id, testrun_id)
    log.info("TestRun information completed to Polarion")

    if reset_project_id:
        try:
            import shutil
            backup = using_pylarion_path + ".bak"
            shutil.move(backup, using_pylarion_path)
        except Exception as ex:
            cli.set_project_id(using_pylarion_path, original_project_id)
