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

- exporter:  T