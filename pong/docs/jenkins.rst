.. jenkins::

Automating via Jenkins
======================

The primary purpose of pong is to have a way to report the results of a TestNG run during automation.  Doing this is
not much different than calling pong from the command line, but it does require that:

- There is a "downstream" job that calls pong with the necessary configuration dat
- An "upstream" job calls this downstream job, and creates an environment file for pong to read

Jenkins management
------------------

Make sure that Jenkins has the `authorize plugin installed`_.  Then go to Manage Jenkins -> Configure Global Security.
You should see a Access Control for Builds.  Click Add and configure like this

.. image:: /images/access-control.png
   :scale: 100%



The Downstream Job
------------------

The downstream is a jenkins job that actually calls pong.  It is a relatively simple job and you can make a plain
job that executes a shell script like this::

    env

    echo $JOB_NAME
    echo ${TEST_ENVIRONMENT}

    if [ -e ${TEST_ENVIRONMENT} ];
    then
      echo "env from last job exists"
    else
      echo "Could not find environment file"
    fi

    cat ${TEST_ENVIRONMENT}

    # Let's work in a virtual environment so we don't mess up our slave node
    if [ ! -e $HOME/venv ]; then
      virtualenv $HOME/venv
    fi
    source $HOME/venv/bin/activate
    pip install -r $WORKSPACE/requirements.txt

    # I'm using bleeding edge hy which has a few nicer features, but is backwards incompatible
    if [ -e /tmp/hy ]; then
      rm -rf /tmp/hy
    fi

    pushd /tmp
    git clone https://github.com/hylang/hy.git
    pushd hy
    python setup.py install
    popd
    popd
    echo `pwd`

    # now we can work from our polarion_testng
    python -m polarion_testng.exporter -e ${TEST_ENVIRONMENT} --testrun-prefix YOUR_TEAM -b TEST_CASE_QUERY1,TEST_CASE_QUERY2 --testrun-template NAME_OF_YOUR_TEMPLATE

    # And delete the TEST_ENVIRONMENT file
    if [ -e ${TEST_ENVIRONMENT} ]; then
      rm -f ${TEST_ENVIRONMENT}
    fi

One thing to keep in mind is that pong needs to know how to generate a unique testrun ID (because Polarion stupidly
does not do this for you).  The approach pong takes is basically this::

    testrun_id = "{} {} {} {}".format(testrun_prefix, testrun_base, testrun_suffix, unique)

The unique param is actually generated internally by pong, so it is not something you need to figure out (nor can you).

Things to change:

- Where it says YOUR_TEAM, this is really just one part of generating a unique test run ID.  We use "RHSM-" for the
  Red Hat Subscription Management team, but you can use whatever.
- Where it says TEST_CASE_QUERY1 and 2, you can put in a list of TestCase title based queries here.  The actual query
  will be something like "title:{}".format(TEST_CASE_QUERY1).  Since this is a sequence, you can supply as many as you
  need, and results from the queries will be joined together.
- Where it says NAME_OF_YOUR_TEMPLATE, this is the ID of a polarion TestRun template

There are a lot more configuration options that you could also use.

One last thing to do is make sure the downstream job has the right authorization.  Near the top of your job you should
have a selection box that says "Configure Build Authorization".  Select it and chose "Run as user who Triggered Build"

.. image:: /images/build-authorization.png
   :scale: 100%

The Upstream Job
----------------

The upstream job is a jenkins job that actually runs your TestNG test.  There are a few things that you will need to
configure on your jenkins master to make it work.

The first of these is creating a `dynamic build parameter`_ called TEST_ENVIRONMENT.  A dynamic build parameter requires
a plugin for jenkins, and basically you write a small groovy script to dynamically generate a value for a parameter.
We need this ability to uniquely generate a file path for a test environment file.  This file will be a python-style
config script that the upstream job creates.  But first, let's actually fill in what's needed

.. image:: /images/dynamic-param.png
   :scale: 100%

The second par that needs to be done is to actually generate a test environment file now that we know the path.  This
test environment file should look like a python config file like this::

    [test_environment]
    PLATFORM=RedHatEnterpriseLinux7-Server-x86_64
    RHELX=6
    RHELY=8
    DISTRO_VARIANT=Server
    DISTRO_ARCH=x86_64
    BUILD_URL=http://my.jenkins.master/job/stoner-gui-test-smoke/101/
    COMPOSE_ID=RHEL-6.8-20160209.n.1

All of these fields are technically optional.  All of these fields can be passed in from the CLI or a YAML config file,
but much of this information you will probably want jenkins itself to generate.  For example, your test probably knows
what version of RHEL it ran on (RHELX is the major version and RHELY is the minor version), as well as the variant
and arch.  Your jenkins job will also know how to fill in the BUILD_URL (since $BUILD_URL is a built in jenkins env var)

So a simple way would be to write a little bash script in an execute shell build script::

    if [ -e "${TEST_ENVIRONMENT}" ]; then
      echo "Deleting file ${TEST_ENVIRONMENT}"
      rm -f ${TEST_ENVIRONMENT}
    fi

    echo "[test_environment]" > ${TEST_ENVIRONMENT}
    echo "RHELX=${RHELX}" >> ${TEST_ENVIRONMENT}
    echo "RHELY=${RHELY}" >> ${TEST_ENVIRONMENT}
    echo "DISTRO_VARIANT=${DISTRO_VARIANT}" >> ${TEST_ENVIRONMENT}
    echo "DISTRO_ARCH=${DISTRO_ARCH}" >> ${TEST_ENVIRONMENT}
    echo "BUILD_URL=${BUILD_URL}" >> ${TEST_ENVIRONMENT}
    echo "COMPOSE_ID=${COMPOSE_ID}" >> ${TEST_ENVIRONMENT}

Once the above are done, a uniquely generated file path, with the contents of the above will be written.  The last
part is to have one more step that kicks off a downstream job.  Click to add a new Build Step and select
Trigger/call builds on other projects.  Then fill it out like this by clicking Add Parameters, and selecting the
"Build on the same node" and again to select "Current Build Parameters"

.. image:: /images/trigger-downstream.png
   :scale: 100%


.. _dynamic build parameter: https://wiki.jenkins-ci.org/display/JENKINS/Dynamic+Parameter+Plug-in
.. _authorize plugin installed: https://wiki.jenkins-ci.org/display/JENKINS/Authorize+Project+plugin