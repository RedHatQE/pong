# pong

Pong is a pylarion based tool for teams using TestNG frameworks for their tests to upload results to a Polarion server.
It is TestNG specific since the junit report that TestNG generates misses some information that can come in handy.

## What pong does

- Creates one TestRun per \<suite\> element in the testng-results.xml
- Parses the xml file for each \<test-method\> creating a TestRecord based on it
- Uses the class and name attributes from \<teset-method\> as a partial TestCase
  - If this ID does not exist in Polarion for a TestCase, it will auto-generate a TestCase
- Uses the <class> element to get a partial ID for a Requirements
  - If this ID does not exist in Polarion for a Requirement, it will auto-generate a Requirement
- Links the TestCase to the Requirement if it is not already
- Generates a new TestRun ID based on configuration properties (prefix, base, and suffix)
  - Creates TestRecords in Polarion based on the \<test-method\>
  - Links the TestRecord with the TestCase
  - Adds the TestRecords to the TestRun

## How to use it

There are many configuration options for pong including via the commandline, a yaml based config file, OS environment 
variables, and through the .pylarion file (with precedence descending in that order...ie, the commandline wins).  You can 
mix and match different config options, for example using a yaml config file, but overriding one or more options on the
command line.

**Command line examples**

```
cd /path/to/pong
python -m pong.exporter 
--project-id=RHEL6 \
--result-path=http://path/to/your/jenkins/job  \
--testcases-query="title:RHSM-TC AND title:rhsm.*.tests*" \
--artifact-archive=test-output/testng-results.xml \
--distro="major:6,minor:8,variant:Server,arch:x86_64" \
--testrun-prefix=RHSM \
--testrun-suffix="Server x86_64 Run" \
--testrun-template="sean toner test template" \ 
--testcase-prefix="RHSM-TC: "  \ 
--requirement-prefix="RHSM-REQ: " \ 
--requirements-query="title:RHSM-REQ AND (author.id:ci\-user OR author.id:stoner)"


❯❯❯ python -m pong.exporter --help                                                                                                                                                     experimental ✱ ◼
usage: exporter.py [-h] [-d DISTRO] [-a ARTIFACT_ARCHIVE] [-r RESULT_PATH]
                   [-p PROJECT_ID] [-c EXPORTER_CONFIG] [-P PYLARION_PATH]
                   [-u PYLARION_USER] [--password PYLARION_PASSWORD]
                   [-t TESTRUN_TEMPLATE] [--testrun-prefix TESTRUN_PREFIX]
                   [--testrun-suffix TESTRUN_SUFFIX]
                   [--testrun-base TESTRUN_BASE]
                   [-b [TESTCASES_QUERY [TESTCASES_QUERY ...]]]
                   [--requirements-query REQUIREMENTS_QUERY]
                   [-e ENVIRONMENT_FILE] [-s TEST_CASE_SKIPS]
                   [--requirement-prefix REQUIREMENT_PREFIX]
                   [--testcase-prefix TESTCASE_PREFIX]
                   [--update-run UPDATE_RUN] [--write-to-project SET_PROJECT]
                   [--query-testcase QUERY_TESTCASE]
                   [--get-default-project-id GET_DEFAULT_PROJECT_ID]
                   [--generate-only GENERATE_ONLY]
                   [--get-latest-testrun GET_LATEST_TESTRUN]

optional arguments:
  -h, --help            show this help message and exit
  -d DISTRO, --distro DISTRO
                        Reads in the arch, variant, name, major and minor in
                        the following form: 'arch:x86_64,variant:Server,name:R
                        edHatEnterpriseLinux-6.8,major:6,minor:8' If used,
                        must supply arch and variant
  -a ARTIFACT_ARCHIVE, --artifact-archive ARTIFACT_ARCHIVE
                        Used when run from a jenkins job, the jenkins job
                        should use the Post-build Actions -> Archive the
                        artifacts -> Files to archive, and the value entered
                        there for the testng-result.xml should be entered here
  -r RESULT_PATH, --result-path RESULT_PATH
                        Path or URL of testng-results.xml file to parse. If
                        --environment-file is also specified, this field is
                        overridden
  -p PROJECT_ID, --project-id PROJECT_ID
                        The Polarion project id. Will override what is in
                        .pylarion file
  -c EXPORTER_CONFIG, --exporter-config EXPORTER_CONFIG
                        Path to configuration file. Initial default is
                        ~/exporter.yml. Willoverride EXPORTER_CONFIG env var
  -P PYLARION_PATH, --pylarion-path PYLARION_PATH
                        Path to the .pylarion file (defaults to ~/.pylarion
  -u PYLARION_USER, --user PYLARION_USER
                        The username in Polarion to run test as (overrides
                        .pylarion)
  --password PYLARION_PASSWORD
                        The password to use for Polarion (overrides .pylarion)
  -t TESTRUN_TEMPLATE, --testrun-template TESTRUN_TEMPLATE
                        The Polarion template name that the test run is based
                        off of
  --testrun-prefix TESTRUN_PREFIX
                        Part of the testrun id. The testrun id is generated
                        as: '{} {} {} {}'.format(prefix, base, suffix, unique
  --testrun-suffix TESTRUN_SUFFIX
                        See testrun_prefix
  --testrun-base TESTRUN_BASE
                        See testrun_prefix. Defaults to the <suite name=> from
                        the testng-results.xml
  -b [TESTCASES_QUERY [TESTCASES_QUERY ...]], --testcases-query [TESTCASES_QUERY [TESTCASES_QUERY ...]]
                        A list of space separated strings that will be used
                        for lucene based TestCase title searches For example,
                        if all your test cases have rhel-<6|7>-test in them,
                        then do: '-b rhel-6-test rhel-7-test'. Another way to
                        do this is like -b 'rhel-*-test'
  --requirements-query REQUIREMENTS_QUERY
                        A lucene query string to query for existing
                        Requirements in Polarion
  -e ENVIRONMENT_FILE, --environment-file ENVIRONMENT_FILE
                        Path to an upstream jenkins job generated file. This
                        file will overridethe results_path even on the CLI
  -s TEST_CASE_SKIPS, --test-case-skips TEST_CASE_SKIPS
                        When True, if a test-method was skipped, add a
                        TestRecord for it anyway By default this is False.
  --requirement-prefix REQUIREMENT_PREFIX
                        A string that will be prepended to the autogenerated
                        Requirement title
  --testcase-prefix TESTCASE_PREFIX
                        A string that will be prepended to the autogenerated
                        TestCase title
  --update-run UPDATE_RUN
                        If given, the arg will be used to find and update an
                        existing Polarion TestRun with the testng-results.xml
  --write-to-project SET_PROJECT
                        If project_id, user, or password are given, write to
                        the pylarion_path
  --query-testcase QUERY_TESTCASE
                        Find a testcase by title, and print out information
  --get-default-project-id GET_DEFAULT_PROJECT_ID
                        Gets the .pylarion project id
  --generate-only GENERATE_ONLY
                        Only create/update TestCases and Requirements based on
                        the testng-results.xml
  --get-latest-testrun GET_LATEST_TESTRUN
                        The supplied arg should be a base string minus the
                        unique identifier of a test run. For example, if the
                        testrun id is 'exporter testing 1'then the supplied
                        arg will be 'exporter testing'. A query will be
                        performedto retrieve the title of the most recent run
```

**YAML config file example** 

```
---

pylarion_path:          # path to .pylarion file to use (will replace contents of ~/.pylarion if given)
user:                   # user for the .pylarion file
password:               # password for user in the .pylarion file
result_path:            # Path to a testng-results.xml file to parse
project_id: RHEL6       # The Polarion project ID to run under
testrun:
  template:             # the polarion template id to use
  prefix: RHSM          # Used to help determine testrun ID: "{} {} {}".format(prefix, base, suffix) (usually team name)
  base:                 # see above.  This will often be determined by the <suite> name
  suffix:               # See above.  This can be some other identifier, like a compose id
distro:
  arch: x86_64          # arch to use as default
  variant: Server       # variant to use as a default
  major:                # the distro major number
  minor:                # the distro minor numer
  name:                 # a full distro name
testcases_query:
  - rhsm.*.tests*       # sequence of TestCase title queries which will be performed and cached
testcase_prefix:        # If given, this string will be prepended to the autogenerated TestCase title in Polarion
environment_file:       # path to a jenkins generated environment file (local path)
build_url:              # If given, will replace result_path.  Where jenkins will store testng-results.xml artifact
requirement_prefix:     # If given, this string will be prepended to the autogenerated Requirement title in Polarion
requirements_query:     # A lucene query to look up Requirements for caching
```

## Explanation of the queries

Note that 2 of the configuration parameters are required and there is no default.  The user must provide a lucene style
query for testcases_query and requirements_query

The purpose of these queries is to retrieve from Polarion any existing TestCases or Requirements respectively so that
they are cached (rather than making a separate query for each and every TestCase and Requirement).  How the user wishes
to create the query is up to them.  The rhsm-qe team uses a query based on the title: 


## Breakdown of modules

- core:  Contains the TestIterationResult and TestNGToPolarion mapping classes.  This primarily models the relationship
    between TestNG and Polarion
- configuration: Handles all the configuration details from the CLI, Yaml file, etc and ultimately generates a final 
    immutable dictionary (PRecord)
- decorators: Some useful decorators that are applicable to any function
- exporter: contains the __main__ that kicks everything off
- logger: Sets up a useful global logger object
- parsing: Parses the testng-results.xml file, generating TestNGToPolarion objects
- requirement: utility functions for querying and creating pylarion Requirement objects
- utils: utility functions mostly for querying and searching WorkItems and TestRuns
