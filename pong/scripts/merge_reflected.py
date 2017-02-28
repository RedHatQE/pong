"""
This script will merge the RHEL6 and RedHatEnterpriseLinux7 json files together
"""
import os
import argparse
import json
import sys
from toolz import itertoolz as it
from toolz import dicttoolz as dt

parser = argparse.ArgumentParser()
parser.add_argument("--rh6", help="path to RHEL6 mapping file")
parser.add_argument("--rh7", help="path to RHEL7 mapping file")
parser.add_argument("--testng", help="path to the JarHelper reflected json file for testng annotations")
parser.add_argument("--ann", help="path to the json file with all the annotation metadata")

opts = parser.parse_args()

paths = [opts.rh6, opts.rh7, opts.testng, opts.ann]
names = ["rh6", "rh7", "testng", "ann"]
zipped = zip(paths, names)
for t in zipped:
    if not os.path.exists(t[0]):
        print "Could not find the mapping file for --{}".format(t[1])
        sys.exit(1)

json_dicts = {}
for z in zipped:
    with open(z[0], "r") as jsonf:
        json_dicts[z[1]] = json.load(jsonf)


# Create a new dict.  The top level key will still be the function name, but the value will be another map whose
# top level key is a project
# {
#   "someMethod.foo": {
#     "RedHatEnterpriseLinux7":{
#       "requirements":[],
#       "testcase":"RHEL7-55646"
#     }
#     "RHEL6":{
#       "requirements":[
#         "RHEL6-27619"
#       ],
#       "testcase":"RHEL6-37011"
#     }
#   }
# }

rh6 = json_dicts["rh6"]
rh7 = json_dicts["rh7"]
ann = json_dicts["ann"]
testng = json_dicts["testng"]

newdict = {}
for d in rh6:
    meth = d.keys()[0]
    v = d[meth]
    rh6_tc = v['testcase']
    if meth not in newdict:
        newdict[meth] = {"RHEL6": v, 'testcases': rh6_tc}

for d in rh7:
    meth = d.keys()[0]
    v = d[meth]
    rh7_tc = v['testcase']
    if meth not in newdict:
        newdict[meth] = {"RedHatEnterpriseLinux7": v, 'testcases': rh7_tc}
    else:
        if "RedHatEnterpriseLinux7" not in newdict[meth]:
            newdict[meth]["RedHatEnterpriseLinux7"] = v
            tcs = [newdict[meth]['testcases'], rh7_tc]
            newdict[meth]['testcases'] = tcs

with open("/tmp/merged-projects.json", "w") as merged:
    json.dump(newdict, merged, sort_keys=True, indent=2, separators=(',', ':'))

grouped = it.groupby('methodName', testng)
for k, v in grouped.items():
    v = v[0]
    className = v['className']
    lookup = "{}.{}".format(className, k)
    if lookup in newdict:
        nd = dt.merge(newdict[lookup], v)
        newdict[lookup] = nd

with open("/tmp/testng-and-polarion.json", "w") as merged:
    json.dump(newdict, merged, sort_keys=True, indent=2, separators=(',', ':'))

with open("/tmp/testcases-by-meth.txt", "w") as tcs:
    lines = []
    for k, v in newdict.items():
        if isinstance(v['testcases'], list):
            ids = k + ": " + ", ".join(map(lambda x: '"{}"'.format(x), v['testcases'])) + "\n"
        else:
            ids = k + ": " + v['testcases'] + "\n"
        print ids
        tcs.write(ids)


ann_dict = {}
ann_grouped = it.groupby('qualifiedName', ann)
for k, v in ann_grouped.items():
    v = v[0]
    if k in newdict:
        nd = dt.merge(v, newdict[k])
        ann_dict[k] = nd

with open("/tmp/fully-merged.json", "w") as merged:
    json.dump(ann_dict, merged, sort_keys=True, indent=2, separators=(',', ':'))
