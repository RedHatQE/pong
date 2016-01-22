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

# Jenkins created environment variables
if 0:
    WORKSPACE = os.environ["WORKSPACE"]
    TEST_RUN_TEMPLATE = os.environ["TEST_RUN_TEMPLATE"]
    TESTNG_RESULTS_PATH = os.path.join(WORKSPACE, "test-output/polarion_testng-results.xml")

OLD_EXPORTER = 0


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


class Suite(object):
    """
    A collection of TestCase objects.
    """
    def __init__(self, transformer, project=None):
        self.tests = []
        self.transformer = transformer

        #if OLD_EXPORTER:
        #    self.tests = parser(results_root)
        testng_suites = self.transformer.parse_suite()
        self.tests = testng_suites
        for k, v in testng_suites.items():
            tests = v
            self._project = transformer.project_id

            not_skipped = filter(lambda x: x.status != SKIP, tests)
            # TODO: It would be nice to have show which Tests got skipped due to dependency on another
            # test that failed, or because of a BZ blocker
            for test_case in not_skipped:
                desc = test_case.description
                title = test_case.title

                t = lambda x: unicode.encode(x, encoding="utf-8", errors="ignore") if isinstance(x, unicode) else x
                desc, title = [t(x) for x in [desc, title]]

                log.info("Creating TestCase for {}: {}".format(title, desc))
                pyl_tc = test_case.create_polarion_tc()
                self._update_tc(pyl_tc)

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
        tr = get_latest_test_run(test_run_base)
        new_id = make_test_run_id_from_latest(tr)
        log.info("Creating new Test Run ID: {}".format(new_id))
        test_run = TestRun.create(self.project, new_id, template_id)
        test_run.status = "inprogress"

        for s, testngs in self.tests.items():
            log.info("Creating test run for {}".format(s))
            for tc in testngs:
                tc.create_test_record(test_run, run_by=runner)

        test_run.status = "finished"
        self._update_tr(test_run)

    def update_test_run(self, test_run, runner="stoner"):
        """
        Given a TestRun object, update it given the TestCases contained in self

        :param test_run: pylarion TestRun object
        :param runner: the user who ran the tests
        :return: None
        """
        for _, testngs in self.tests:
            # Check to see if the test case is already part of the test run
            for tc in testngs:
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
        all_fields = filter(lambda x: not x.startswith("_"),
                            TestRun._cls_suds_map.keys())
        all_fields = list(all_fields) + [test_run_id]
        tr = TestRun.search('"{}"'.format(test_run_id), fields=all_fields,
                            sort="created")
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

    results_path = args.result_path
    template_id = args.template_id  # eg "sean toner test template"
    testrun_id = args.testrun_id    # eg "pylarion exporter testing"
    gen_only = args.generate_only
    update_id = args.update_run

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
    project_id = args.project_id
    default_project_id = get_default_project()
    if project_id != default_project_id:
        cli.set_project_id(using_pylarion_path, project_id)

    trans = 0

    transformer = Transformer(project_id, results_path, template_id)
    if OLD_EXPORTER:
        # Will auto-generate polarion TestCases
        suite = Suite(results_path)
    else:
        suite = Suite(transformer)

    # Once the suite object has been initialized, generate a test run with associated test records
    if not gen_only:
        if update_id:
            tr = Suite.get_test_run(update_id)
            log.info("Updating existing test run...")
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
