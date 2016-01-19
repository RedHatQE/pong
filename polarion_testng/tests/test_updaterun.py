from polarion_testng.exporter import Suite
from polarion_testng.exporter import get_test_run
import ssl
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--project", help="Project ID",
                    default="RedHatEnterpriseLinux7")
parser.add_argument("--test-run-id", help="Unique ID of a Test Run")
parser.add_argument("--polarion_testng-path", help="Path to polarion_testng-results.xml file",
                    default="../../polarion_testng-results.xml")

args = parser.parse_args()

tr = get_test_run(project_id=args.project, test_run_id=args.test_run_id)
if tr.query is not None:
    # tr.query = "(title:rhsm.cli.* OR title:rhsm.gui.*)"
    tr.query = None
if tr.select_test_cases_by != "automatedProcess":
    #tr.select_test_cases_by = "staticQueryResult"
    tr.select_test_cases_by = "automatedProcess"
if not tr.project_id:
    tr.project_id = "RedHatEnterpriseLinux7"
if not tr.template:
    tr.template = "sean toner test template"

done = 3
while done > 0:
    try:
        tr.update()
        done = 0
    except ssl.SSLError as se:
        # give 3 tries total
        done -= 1

suite = Suite(args.testng_path)
suite.update_test_run(tr)
