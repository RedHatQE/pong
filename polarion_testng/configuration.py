"""
Configuration is a non-trivial task.  We need to be able to merge configuration variables from
the CLI, from the environment, from a test environment file and from a config file (with precedence
in that order).  In order to make sense of this, we will have a Configuration pipeline.

exporter.cfg(.pylarion) -> ConfigMap -> YAMLConfigurator -> EnvConfigurator -> CLIConfigurator ->
TestEnvironmentConfigurator -> ConfigMap

This is the essence of a transform pipeline.  However, rather than mutate the ConfigMap as it passes
through each Configurator, it will return a new modified ConfigMap.  Note that each Configurator may
only touch some fields in the map.  By having the ConfigMap be immutable, we can look and see what
each Configurator in the pipeline transformed stage by stage.

Fundamentally the pipeline is a composition of functions.  Each of the Configurator classes defined
in this module have objects that act as functions.  The function takes as a single argument a
ConfigMap type, and returns a transformed version of that map.  ConfigMap is a PMap type from 
pyrsistent and is thus immutable.  If we mutated the map as it traversed the pipeline, debugging
any errors will be more difficult.
"""

from argparse import ArgumentParser
from polarion_testng.utils import *
from polarion_testng.logger import log
import shutil
import os
import yaml
from toolz.functoolz import compose, partial
from pyrsistent import PRecord, field
import pyrsistent as pyr
from abc import ABCMeta, abstractmethod

try:
    import configparser
except ImportError as e:
    import ConfigParser as configparser


def fieldm():
    return field(mandatory=True)


def start_configuration():
    """
    Creates the initial PMap that will be passed down the pipeline

    :return:
    """
    return pyr.m()


class FieldFactory(object):
    def __init__(self, parser=None):
        self.short_names = set()
        self.parser = parser if parser else ArgumentParser()

    def field_factory(self, long_name, short_name=None, **kwargs):
        """
        This function does two things:  it forwards args to parser.add_arguments, and other args to field()

        Since there are no name-collisions in the keyword args for add_argument or field, we will direct them
        accordingly

        :param long_name: The "--long-arg" name
        :param short_name:
        :param cli_help:
        :param parser:
        :param kwargs:
        :return:
        """

        long_name = long_name
        short_name = short_name
        if short_name is not None and short_name in self.short_names:
            log.warning("{0} already used.  Not setting {0} for {1}".format(short_name, long_name))
        else:
            self.short_names.add(short_name)

        if "short_name" in kwargs:
            kwargs.pop("short_name")


        parser_kwargs = {}
        for x in ["required", "nargs", "choices", "default", "help"]:
            if x in kwargs:
                parser_kwargs[x] = kwargs.pop(x)
        field_kwargs = kwargs

        if short_name is not None:
            self.parser.add_argument(short_name, long_name, **parser_kwargs)
        else:
            self.parser.add_argument(long_name, **parser_kwargs)
        return field(**field_kwargs)


class Configurator(object):
    """
    Base class that all the other derived Configurator types must implement.  Every
    Configurator type is callable and thus implements __call__.  We do this to ensure
    that the object can be composed with other Configurator via toolz.functoolz.compose"""
    
    __metaclass__ = ABCMeta

    def __init__(self):
        self._original_map = None
        self.record = None

    @property
    def original_map(self):
        return self._original_map

    @original_map.setter
    def original_map(self, omap):
        if self._original_map is None:
            self._original_map = omap
        else:
            log.error(u'Can not set original-map')

    @abstractmethod
    def __call__(self, config_map):
        """Takes in a PMap and returns a transformed map"""
        pass


class Distro(PRecord):
    arch = field()
    variant = field()
    name = field()
    major = field()
    minor = field()


class CLIConfigRecord(PRecord):
    """
    This is the master record which will be passed in at the beginning of the pipeline.
    All Configurator types will take an object of this as input, and return a transformed
    (but not mutated) object to pass to the next one
    """
    factory = FieldFactory()
    add_field = factory.field_factory
    distro = add_field("-d", "--distro", type=Distro,
                       help="Reads in the arch, variant, name, major and minor in the form of a json dict"
                            "eg {'arch': 'x86_64', 'variant': 'Server', 'name': RedHatEnterpriseLinux-6.8',"
                            "'major': 6, 'minor': 8}.  If used, must supply arch and variant")
    artifact_archive = add_field("-a", "--artifact-archive", default="test-output/testng-results.xml",
                                 help="Used when run from a jenkins job, the jenkins job should use the Post-build"
                                      "Actions -> Archive the artifacts -> Files to archive, and the value"
                                      "entered there for the testng-result.xml should be entered here")
    result_path = add_field("-r", "--result-path",
                            help="Path or URL of testng-results.xml file to parse.  If --environment-file "
                                 "is also specified, this field is overridden")
    project_id = add_field("-p", "--project-id", mandatory=True,
                           help="The Polarion project id.  Will override what is in .pylarion file")
    pylarion_path = add_field("-P", "--pylarion-path", mandatory=True, default=os.path.expanduser("~/.pylarion"),
                              help="Path to the .pylarion file (defaults to ~/.pylarion")
    pylarion_user = add_field("-u", "--user", help="The username in Polarion to run test as (overrides .pylarion)")
    pylarion_password = add_field("--password", help="The password to use for Polarion (overrides .pylarion)")
    testrun_template = add_field("-t", "--testrun-template", mandatory=True,
                                 help="The template name in Polarion that the test run is based off of")
    testrun_prefix = add_field("--testrun-prefix", mandatory=True,
                               help="The testrun id is generated as: "
                                    "'{} {} {} {}'.format(prefix, suffix, suite, unique")
    testrun_suffix = add_field("--testrun-suffix", help="See testrun_prefix")
    suite_name = add_field("--suite-name",
                           help="See testrun_prefix.  Defaults to the <suite name=> from the testng-results.xml")
    base_queries = add_field("-b", "--base-queries", mandatory=True, nargs='*',
                             help="A sequence of strings that will be used for TestCase title searches "
                                  "eg 'title:<base_query>')")
    environment_file = add_field("-e", "--environment-file",
                                 help="Path to an upstream jenkins job generated file.  This file will override"
                                      "the results_path even on the CLI")

    # These are "functions"
    update_run = add_field("--update-run", help="If given, the arg will be used to find and update an existing "
                                                "Polarion TestRun with the testng-results.xml")
    set_project = add_field("--set-project",
                            help="If project_id, user, or password are given, write to the pylarion_path")
    query_testcase = add_field("--query-testcase", help="Find a testcase by title, and print out information")
    get_default_project_id = add_field("--get-default-project-id", help="Gets the .pylarion project id")
    generate_only = add_field("--generate-only",
                              help="Only create/update TestCases and Requirements based on the testng-results.xml")
    get_latest_testrun = add_field("--get-latest-testrun",
                                   help="The supplied arg should be a base string minus the unique identifier"
                                        " of a test run.  For example, if the testrun id is 'exporter testing 1'"
                                        "then the supplied arg will be 'exporter testing'.  A query will be performed"
                                        "to retrieve the title of the most recent run")

    @classmethod
    def parse_args(cls):
        return cls.factory.parser.parse_args()


class OSEnvironmentRecord(PRecord):
    """
    Fields that can be obtained from the OS environment
    """
    distro = field(type=Distro)
    build_url = field()
    result_path = field()
    project_id = field()


class JenkinsRecord(PRecord):
    """
    Represents the information recorded by an upstream job that will be needed for 
    the downstream job to run correctly.  Required for an automation run in jenkins but optional
    """
    distro = field(mandatory=True, type=Distro)
    upstream_workspace = fieldm()
    upstream_slave = fieldm()
    upstream_job_name = fieldm()
    upstream_build_number = fieldm()
    results_path = fieldm()
    project_id = field()


class ConfigRecord(PRecord):
    """
    This is the master record which will be passed in at the beginning of the pipeline.
    All Configurator types will take an object of this as input, and return a transformed
    (but not mutated) object to pass to the next one
    """
    distro = field(mandatory=True, type=Distro)
    artifact_archive = field()
    result_path = field()
    project_id = fieldm()
    pylarion_path = fieldm()
    pylarion_user = field()
    pylarion_password = field()
    testrun_template = fieldm()
    testrun_prefix = fieldm()
    testrun_suffix = fieldm()
    suite_name = fieldm()
    base_queries = fieldm()
    environment_file = field()

    # These are "functions"
    update_run = field()
    set_project = field()
    get_default_project_id = field()
    generate_only = field()
    get_latest_testrun = field()


class JenkinsConfigurator(Configurator):
    def __init__(self):
        super(JenkinsConfigurator, self).__init__()

    def __call__(self, omap):
        self.original_map = omap


class YAMLRecord(PRecord):
    """Keys in the YAML config file that we care about"""
    pylarion_path = field()
    user = field()
    password = field()
    result_path = field()
    project_id = field()
    testrun_template = field()
    testrun_prefix = field()
    testrun_suffix = field()
    suite_name = field()
    update_run = field()
    req_prefix = field()
    distro = field(mandatory=True, type=Distro)
    base_queries = field()
    environment_file = field()
    jenkins_url = field()


class OSEnvironmentConfigurator(Configurator):
    distro_keys = ['DISTRO_ARCH', 'DISTRO_VARIANT', 'DISTRO_MAJOR', 'DISTRO_MINOR']
    valid_keys = ['UPSTREAM_JOB_NAME', 'UPSTREAM_BUILD_NUMBER', 'RESULT_PATH', 'PROJECT_ID']

    def __call__(self, config_map):
        self.original_map = config_map
        return self._make_record()

    def _make_record(self):
        env_keys, d_keys = self.get_valid_keys()
        env_keys["distro"] = Distro(**d_keys)
        rec = OSEnvironmentRecord(**env_keys)
        self.os_env_record = rec
        return self.os_env_record

    def get_valid_keys(self):
        """Returns a dictionary which maps Environment variable names to keys in the ConfigRecord"""
        env_keys = os.environ.keys()
        validk = {k.lower(): os.environ[k] for k in filter(lambda x: x in self.valid_keys, env_keys)}
        validd = {k.replace("DISTRO_", "").lower(): os.environ[k]
                  for k in filter(lambda y: y in self.distro_keys, env_keys)}
        return validk, validd


class TestEnvironmentConfigurator(Configurator):

    def __init__(self, file_path):
        super(TestEnvironmentConfigurator, self).__init__()
        self.file_path = file_path




class CLIConfigurator(Configurator):
    def __init__(self, parser=ArgumentParser()):
        super(CLIConfigurator, self).__init__()
        self.parser = parser
        self.args = CLIConfigRecord.parse_args()
        self.dict_args = vars(self.args)
        self.reset_project_id = False
        self.pylarion_path = self.get_pylarion_path()
        self.original_project_id = get_default_project(pylarion_path=self.pylarion_path)
        self._project_id = None

    def _make_distro_record(self):
        """
        Parses the self.args.distro argument.
        :return:
        """
        import json
        if self.args.distro:
            distro = dict(kv.split(":") for kv in self.args.distro.split(","))
            required = ["arch", "variant"]
            valid = Distro._precord_fields.keys()
            for i in required:
                if i not in distro:
                    raise Exception("Must supply arch and variant if using --distro")
            invalid_keys = [k for k in distro.keys() if k not in valid]
            if invalid_keys:
                raise Exception("{} are invalid keys".format(invalid_keys))

            return Distro(**distro)

    def __call__(self, omap):
        self.original_map = omap
        distro_record = self._make_distro_record()
        if self.args.distro:
            self.dict_args["distro"] = distro_record

        # Before we modify the map, let's see if an environment file was passed in
        if self.args.environment_file:

        return self.original_map.update(self.dict_args)

    # This doesn't belong to this class
    def get_pylarion_path(self, cfg_map=None):
        if cfg_map is None:
            pyl_path = self.args.pylarion_path or os.path.expanduser('~/.pylarion')
        else:
            pyl_path = cfg_map.pylarion_path
        return pyl_path

    # This doesn't belong to this class either
    def save_pylarion(self, cfg_map=None):
        if cfg_map is None:
            if self.args.set_project:
                self.reset_project_id = True


class YAMLConfigurator(Configurator):
    def __init__(self, cfg_path=None):
        if cfg_path is None:
            self.cfg_path = os.path.expanduser("~/config_map.hy")
        super(YAMLConfigurator, self).__init__()

        if not os.path.exists(self.cfg_path):
            self.record = YAMLRecord()
        else:
            with open(self.cfg_path, "r") as cfg:
                cfg_dict = yaml.load(cfg)

            # Filter out the key-vals where the value is a falsey value
            final = {k: v for k, v in cfg_dict.items() if bool(v)}

            # If distro in final, create a Distro record
            if "distro" in final:
                distro_dict = {"distro": final["distro"]}
                final["distro"] = Distro(**distro_dict)
            self.record = YAMLRecord(**final)

    def __call__(self, omap):
        """
        Merges the original map with our yaml config map
        :param omap:
        :return:
        """
        self.original_map = omap
        return omap.update(self.record)


def final_configure(pipelined_map):
    return ConfigRecord(**pipelined_map)


##############################################################################
# helper functions
##############################################################################

def only_pretty_polarion(obj, field):
    result = False
    try:
        no_under = field.startswith(u'_')
        attrib = getattr(obj, field)
    
        result = (no_under and (attrib and (not callable(attrib))))
    except AttributeError as ae:
        result = False
    except TypeError as te:
        result = False
    return result


def print_kv(obj, field):
    print field, u'=', getattr(obj, field)

    
def query_testcase(query):
    for test in query_test_case(query):
        msg = ((test.work_item_id + u' ') + test.title)
        log.info(msg)

    
def get_default_projectid():
    log.info(get_default_project())

    
def get_latest_testrun(testrun_id):
    tr = get_latest_test_run(testrun_id)
    valid = partial(only_pretty_polarion, tr)
    fields = filter(valid, dir(tr))
    for attr in fields:
        print_kv(tr, attr)


def create_cfg_parser(path=None):
    cpath = (os.path.expanduser(u'~/.pylarion') if (path is None) else path)
    cparser = configparser.ConfigParser()
    if (not os.path.exists(cpath)):
        raise Exception(u'{} does not exist'.format(cpath))
    else:
        with open(cpath) as fp:
            cfg = cparser.readfp(fp)
            return cfg


def create_backup(orig, backup=None):
    """
    Creates a backup copy of original.  If backup is given it must be the full name, otherwise
    if backup is not given, the original file name will be appended with .bak

    :param orig:
    :param backup:
    :return:
    """
    backup_path = backup if backup else (orig + '.bak')
    return shutil.copy(orig, backup_path)


if __name__ == "__main__":
    start_map = start_configuration()

    cli_cfg = CLIConfigurator()
    end_map = cli_cfg(start_map)
    print cli_cfg
