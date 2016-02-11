.. introduction::

Welcome to polarion_testng
==========================

The polarion_testng project uses Red Hat's pylarion project to send results of testng-results.xml up to the Polarion
database.  This includes the following features:

- Autogeneration of a Requirement if one does not exist, based on the <test> name
- Autogeneration of a TestCase if it does not exist, based on the <test-method>
- Linking of a TestCase to the Requirement
- Generating a TestRun and inserting TestRecords based on the data in the <suite>
- A CLI to run it manually
- Provides the basis for an upstream jenkins job that ran a test, to a downstream job that does the reporting

Architecture and Design
=======================

polarion_testng is split into several modules:

- cli:
  Contains some command line utilities
- configuration:
  Contains classes that do the actual job of getting configuration information from several sources
- core:
  Defines classes that map <test-method> elements to Polarion TestRecords
- exporter:
  Defines the class that kicks off the retrieval of configuration information, the parsing of the testng-results.xml
  and creating or updating a TestRun
- logger:
  Creates a simple global logger that will create a timestamped file in /tmp
- parsing:
  Has classes that actually do the parsing of the testng-results.xml as well as autogeneration of Requirements and
  TestCases in Polarion
- requirement:
  Creates Polarion Requirements
- utils:
  Various helper functions



Configuration Handling
----------------------

One of the largest parts of the code deals with handling of all the various means of getting configuration information.
Information can come from:

#. A .pylarion file
#. The OS Environment
#. A YAML config file
#. A Jenkins generated test environment file
#. The CLI itself

The order listed above is the order of increasing precedence (ie, the CLI trumps all).  The end result is that when
pong is run, it can generate a configuration record (which is an immutable dict) that any needed configuration data
can be retrieved.


Autogeneration of Requirements
------------------------------

One of polarion_testng's main cases is to autogenerate a Polarion Requirement.  While it parses the results xml file,
it looks at the <class> element.  Given the name of this class, pong will check to see if a Requirement already exists
with this ID, and if not, it will create one.  Since <test-methods> are child elements of <class>, and <test-methods>
in the xml map to Polarion TestCases, we therefore know which Requirement to link to the TestCase.

Autogeneration of TestCases
---------------------------

During parsing of the results xml file, when a <test-method> element is encountered, the name attribute is used as a
query.  This query will attempt to find an existing Polarion TestCase, and if it does not exist, a TestCase with this
ID will be created.  From configuration data, pong also knows the arch and variant, and from metadata about the test
like the description (which is populated in the description attribute of the <test-method> element), pong can fill in
some additional data for the TestCase.  As noted above, since <test-method> elements are children of the <class> element
pong also knows what Requirement to link the retrieved TestCase to if it is not already linked

Creation of TestRuns
--------------------

A TestRun is created through a combination of the result xml file and various configuration information.  From
Polarion's perspective, it only needs a TestRun Template, and an ID.  Both the template ID and test run ID are obtained
through several configuration fields.  A TestRun will be generated for each <suite> element in the result xml file,
and the ID of the TestRun is::

    testrun_id = "{} {} {} {}".format(testrun_prefix, testrun_base, testrun_suffix, unique)

All but the unique param comes from one or more configuration properties.

Adding TestRecords
------------------

Once a TestRun has been obtained (either a new one generated, or retrieved from an existing ID), pong will add
TestRecord entries to the TestRun.  It does this from information obtained during parsing of the <test-method> element.
Note that since this is TestNG, your test might be a data-provider test.  This means that the xml may have more
than one <test-method name=X> with the same name, but different <args> children.  Since Polarion does not currently
support this from an automation perspective, what is done instead is that all the <test-method> with the same name
have 2 mapped classes (TestNGToPolarion and TestIterationResult).  The args of every similar <test-method> are collected
(as a list of TestIterationResult) and this list is saved to an object of TestNGToPolarion.  This is done so that in
the future, when Polarion does support parameterized tests, pong will be ready for it.

The ramification of this means that even if your suite ran 10 different versions of test Foo, you will only see one
TestRecord in the TestRun (until Polarion starts supporting parameterized tests programatically)


Usage
=====

There are 3 primary use cases for how to use pong:

#. From the command line manually
#. Called from a jenkins job
#. At the REPL for exploration/testing purposes
