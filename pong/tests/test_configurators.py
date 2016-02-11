import pong.configuration as cfg
import pyrsistent as pyr

import unittest


class TestCLIConfigurator(unittest.TestCase):
    def test_args(self):
        arglist = ["-r https://rhsm-jenkins.rhev-ci-vms.eng.rdu2.redhat.com/view/Scratch/job/stoner-gui-test-smoke/93/artifact/test-output/testng-results.xml",
                   "--testrun-prefix RHSM",
                   "--testrun-suffix blah"]
        argstr = " ".join(arglist)
        self.cfg = cfg.CLIConfigurator(args=argstr)

        start_map = pyr.m()
        end_map = self.cfg(start_map)
