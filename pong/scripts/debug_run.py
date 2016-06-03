"""
Takes a pong.parameters file or URL and uses it to pass in parameters.

PROJECT_ID= RHEL6
RESULT_PATH= <Jenkins URL>
ARTIFACT_ARCHIVE= test-output/testng-results.xml
BASE_QUERIES= rhsm.*.tests*
DISTRO= name:Red Hat Enterprise Linux,major:6,minor:8,variant:Server,arch:x86_64
TESTRUN_PREFIX= RHSM
TESTRUN_SUFFIX= Server x86_64
TESTRUN_TEMPLATE= RHSM RHEL-6 8
"""

import os
from functools import partial
from pong.parsing import download_url
from argparse import ArgumentParser
from ConfigParser import ConfigParser
from pong.exporter import Exporter
from pong.configuration import kickstart

parser = ArgumentParser()
parser.add_argument("-u", "--url")
parser.add_argument("-r", "--result-path")
args = parser.parse_args()

if args.url.startswith("http:"):
    pong_params = download_url(args.url)
else:
    pong_params = args.url

if 0:
    with open("section", "w") as sectioned:
        with open(pong_params, "r") as pp:
            sectioned.write("[default]\n")
            for line in pp.readlines():
                sectioned.write(line)


    cfg = ConfigParser()
    cfg.read(["section"])

    cfgget = partial(cfg.get, "default")

    keys = ["PROJECT_ID", "RESULT_PATH", "ARTIFACT_ARCHIVE", "TESTCASES_QUERY", "REQUIREMENTS_QUERY",
        "DISTRO", "REQUIREMENT_PREFIX", "TESTCASE_PREFIX",
        "TESTRUN_PREFIX", "TESTRUN_SUFFIX", "TESTRUN_TEMPLATE",
        "TESTRUN_JENKINS_JOBS", "TESTRUN_NOTES"]
    keys_p = map(lambda k: "P_" + k, keys)
    keys.remove("TESTRUN_JENKINS_JOBS")
    keys.append("TESTRUN_JENKINSJOBS")

    def converter(name):
        if name == "BASE_QUERIES":
            name = "testcases_query"
        return "--" + name.replace("_", "-").lower()

    cmd_args = map(converter, keys)


with open(pong_params, "r") as params:
    lines = params.readlines()


def composer(kv):
    key, val = kv
    val = val.replace("\n", "")
    key1 = "--" + key[2:].lower().replace("_", "-")
    if "testrun-jenkins-jobs" in key1:
        key1 = "--testrun-jenkinsjobs"
    return key1, val

cmdline_args = map(composer, map(lambda l: l.split("="), lines[1:]))
# cmdline_args = zip(cmd_args, map(cfgget, keys_p))

arglist = []
for opts in cmdline_args:
    arglist.extend(opts)

arglist.extend(["--test-case-skips", "True"])

for i, arg in enumerate(arglist):
    if arg == "--result-path" and args.result_path is not None:
        arglist[i+1] = args.result_path
        break


config_map = kickstart(args=arglist)
Exporter.export(config_map)
