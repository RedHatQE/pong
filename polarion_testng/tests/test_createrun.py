from polarion_testng.exporter import Exporter

suite = Exporter("../../polarion_testng-results.xml")
suite.create_test_run("Sean Toner Template Automation Testing", "Jenkins Run")