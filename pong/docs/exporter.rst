.. automodule:: polarion_testng.exporter
   :members:

The exporter module
===================

IS badly named and will be refactored.  It is the place where the actual parsing of the
testng-results.xml takes place and collected into a Suite class.  It is also where the
CLI action happens.  You can execute it manually like::

  python -m polarion_testng.exporter -p "RHEL6" -t "RHSM test template" -r "/path/to/testng-results.xml"

