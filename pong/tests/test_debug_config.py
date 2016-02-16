import unittest
from pong.configuration import extractor, cli_print


class Config(unittest.TestCase):
    def test_cli_print(self):
        example = """1455653630.7-pong.logger-INFO: 	result_path=http://rhsm-jenkins.rhev-ci-vms.eng.rdu2.redhat.com/job/jsefler-subscription-manager-rhel-6.8-x86_64-Tier3Tests/23/artifact/test-output/testng-results.xml
1455653630.7-pong.logger-INFO: 	query_testcase=False
1455653630.7-pong.logger-INFO: 	get_default_project_id=False
1455653630.7-pong.logger-INFO: 	pylarion_path=/home/jenkins/.pylarion
1455653630.7-pong.logger-INFO: 	exporter_config=/home/jenkins/exporter.yml
1455653630.7-pong.logger-INFO: 	update_run=False
1455653630.7-pong.logger-INFO: 	testrun_prefix=RHSM
1455653630.7-pong.logger-INFO: 	testrun_template=RHSM RHEL6-8
1455653630.7-pong.logger-INFO: 	get_latest_testrun=False
1455653630.7-pong.logger-INFO: 	set_project=False
1455653630.7-pong.logger-INFO: 	base_queries=['rhsm.*.tests*']
1455653630.7-pong.logger-INFO: 	project_id=RHEL6
1455653630.7-pong.logger-INFO: 	generate_only=False
1455653630.7-pong.logger-INFO: 	testrun_suffix=Server x86_64 Run
1455653630.7-pong.logger-INFO: 	artifact_archive=test-output/testng-results.xml
1455653630.7-pong.logger-INFO: 	distro=Distro(major='6', arch='x86_64', variant='Server', name='Red Hat Enterprise Linux', minor='8')"""

        args = extractor(example)
        cli_args = cli_print(args)
        print cli_args