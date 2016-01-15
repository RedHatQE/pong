"""
Source controlled version for the post build step

1.  Clone the testng repo to jenkins slave
2.  Get the Arch and Variant that we tested on (CLIENT_1)
3.  Create a Suite
4.  call suite.create_test_run("/path/to/testng-results.xml")
"""

import os
from subprocess import Popen, PIPE, STDOUT

WORKSPACE = os.environ["WORKSPACE"]
client_1 = os.environ["CLIENT_1"]
smoke_dir = os.path.join(WORKSPACE, "smoke")

if os.path.exists(smoke_dir):
    os.unlink(smoke_dir)

proc = Popen("git clone ", stdout=STDOUT, stderr=STDOUT)
outp, _ = proc.communicate()
if proc.returncode != 0:
    raise Exception("Unable to clone smoke exporter")

print(outp)

