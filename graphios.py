#!/usr/bin/python -tt
# vim: set ts=4 sw=4 tw=79 et :
# Copyright (C) 2011  Shawn Sterling <shawn@systemtemplar.org>
#
# With contributions from:
#
# Juan Jose Presa <juanjop@gmail.com>
# Ranjib Dey <dey.ranjib@gmail.com>
# Ryan Davis <https://github.com/ryepup>
# Alexey Diyan <alexey.diyan@gmail.com>
# Steffen Zieger <me@saz.sh>
# Nathan Bird <ecthellion@gmail.com>
# Dave Josephsen <dave@skeptech.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
#
# graphios: this program will read nagios host and service perfdata, and
# send it to a carbon server.
#
# The latest version of this code will be found on my github page:
# https://github.com/shawn-sterling

from ConfigParser import SafeConfigParser
from optparse import OptionParser
import copy
import logging
import logging.handlers
import os
import os.path
import re
import sys
import time
import backends


############################################################
# #### You will likely need to change some of the below #####

# nagios spool directory
spool_directory = '/var/spool/nagios/graphios'
#
# # graphios log info
log_file = ''
log_max_size = 25165824         # 24 MB
# # log_level = logging.INFO
# log_level = logging.DEBUG      # DEBUG is quite verbose
#
# # How long to sleep between processing the spool directory
# sleep_time = 15
#
# # when we can't connect to carbon, the sleeptime is doubled until we hit max
# sleep_max = 480
#
# # keep a replayable archive log of processed metrics
# metric_archive = '/usr/local/nagios/var/graphios_metric_archive.log'
#
# # test mode makes it so we print what we would add to carbon, and not delete
# # any files from the spool directory. log_level must be DEBUG as well.
# test_mode = False
#
# # Character to use as replacement for invalid characters in metric names
# replacement_character = '_'
#
# # use service description as part of your carbon metric
# # $GRAPHIOSPREFIX.$HOSTNAME.$SERVICEDESC.$GRAPHIOSPOSTFIX.$PERFDATA
# use_service_desc = False
#
# config file stuff

#-------------------------------------------------

# by default we will check the current path for graphios.cfg, if config_file
# is set, we will use that instead.

config_file = ''
debug = True
enabled_backends = ''

# config dictionary
cfg = {}

# default config values (these will be over-ridden with the config

# #### You should stop changing things unless you know what you are doing #####
##############################################################################

# options parsing
parser = OptionParser("""usage: %prog [options]
sends nagios performance data to carbon.
""")

parser.add_option('-v', "--verbose", action="store_true", dest="verbose",
                  help="sets logging to DEBUG level")
parser.add_option("--spool-directory", dest="spool_directory",
                  default=spool_directory,
                  help="where to look for nagios performance data")
parser.add_option("--log-file", dest="log_file",
                  default=log_file,
                  help="file to log to")
parser.add_option("--backend", dest="backend", default="stdout",
                  help="sets which storage backend to use")
parser.add_option("--config", dest="config_file", default="",
                  help="set custom config file location")

log = logging.getLogger('log')

# # import the backend plug-ins
# bfiles = [fname[:-3] for fname in os.listdir(bdir) if fname.endswith(".py")]

# if bdir not in sys.path:
#     sys.path.insert(1, bdir)

# backends = [__import__(fname) for fname in bfiles]


class GraphiosMetric(object):
    def __init__(self):
        self.LABEL = ''                 # The name in the perfdata from nagios
        self.VALUE = ''                 # The measured value of that metric
        self.UOM = ''                   # The unit of measure for the metric
        self.DATATYPE = ''              # HOSTPERFDATA|SERVICEPERFDATA
        self.TIMET = ''                 # Epoc time the measurement was taken
        self.HOSTNAME = ''              # name of th host measured
        self.SERVICEDESC = ''           # nagios configured service description
        self.PERFDATA = ''              # the space-delimited raw perfdata
        self.SERVICECHECKCOMMAND = ''   # literal check command syntax
        self.HOSTCHECKCOMMAND = ''      # literal check command syntax
        self.HOSTSTATE = ''             # current state afa nagios is concerned
        self.HOSTSTATETYPE = ''         # HARD|SOFT
        self.SERVICESTATE = ''          # current state afa nagios is concerned
        self.SERVICESTATETYPE = ''      # HARD|SOFT
        self.GRAPHITEPREFIX = ''        # graphios prefix
        self.GRAPHITEPOSTFIX = ''       # graphios suffix
        self.VALID = False              # if this metric is valid

    def validate(self):
        if (
            self.TIMET is not '' and
            self.PERFDATA is not '' and
            self.HOSTNAME is not ''
        ):
            if "use_service_desc" in cfg:
                if self.SERVICEDESC is not '':
                    self.VALID = True
            else:
                self.VALID = True


def read_config(config_file):
    if config_file == '':
        config_file = "%s/graphios.cfg" % sys.path[0]
    config = SafeConfigParser()
    # The logger won't be initialized yet, so we use print_debug
    if os.path.isfile(config_file):
        config.read(config_file)
        config_dict = {}
        for section in config.sections():
            # there should only be 1 'graphios' section
            print_debug("section: %s" % section)
            config_dict['name'] = section
            for name, value in config.items(section):
                config_dict[name] = value
                print_debug("config[%s]=%s" % (name, value))
        # print config_dict
        return config_dict
    else:
        print_debug("Can't open config file: %s" % config_file)
        print """\nEither modify the script at the config_file = '' line and
specify where you want your config file to be, or create a config file
in the above directory (which should be the same dir the graphios.py is in)
or you can specify --config=myconfigfilelocation at the command line."""
        sys.exit(1)


def verify_config(config_dict):
    """
    will verify the needed variables are found
    """
    ensure_list = ['replacement_character', 'log_file', 'log_max_size',
                   'log_level', 'sleep_time', 'sleep_max', 'test_mode']
    missing_values = []
    for ensure in ensure_list:
        if ensure not in config_dict:
            missing_values.append(ensure)
    if len(missing_values) > 0:
        print "\nMust have value in config file for:\n"
        for value in missing_values:
            print "%s\n" % value
        sys.exit(1)


def print_debug(msg):
    """
    prints a debug message if global debug is True
    """
    if debug:
        print msg


def configure(opts=''):
    """
    sets up graphios config
    """
    global cfg
    global debug
    if opts != '':
        cfg["log_file"] = opts.log_file
        cfg["log_max_size"] = 25165824         # 24 MB
        if opts.verbose:
            cfg["debug"] = True
        cfg["spool_directory"] = opts.spool_directory
        cfg["backend"] = opts.backend

    if cfg["log_file"] == "''":
        cfg["log_file"] = "%s/graphios.log" % sys.path[0]

    log_handler = logging.handlers.RotatingFileHandler(
        cfg["log_file"], maxBytes=cfg["log_max_size"], backupCount=4,
        #encoding='bz2')
    )
    formatter = logging.Formatter(
        "%(asctime)s %(filename)s %(levelname)s %(message)s",
        "%B %d %H:%M:%S")
    log_handler.setFormatter(formatter)
    log.addHandler(log_handler)

    if "debug" in cfg and cfg["debug"] == "True":
        print("adding streamhandler")
        log.setLevel(logging.DEBUG)
        log.addHandler(logging.StreamHandler())
        debug = True
    else:
        log.setLevel(logging.INFO)


def process_log(file_name):
    """ process log lines into GraphiosMetric Objects.
    input is a tab delimited series of key/values each of which are delimited
    by '::' it looks like:
    DATATYPE::HOSTPERFDATA  TIMET::1399738074 etc..
    """

    processed_objects = []  # the final list of metric objects we'll return
    graphite_lines = 0  # count the number of valid lines we process

    try:
        host_data_file = open(file_name, "r")
        file_array = host_data_file.readlines()
        host_data_file.close()
    except OSError as ex:
        log.critical("Can't open file:%s error: %s" % (file_name, ex))
        sys.exit(2)

    # parse each line into a metric object
    for line in file_array:
        if not re.search("^DATATYPE::", line):
            continue
        #log.debug('parsing: %s' % line)
        graphite_lines += 1
        variables = line.split('\t')
        mobj = get_mobj(variables)
        if mobj:
            # break out the metric object into one object per perfdata metric
            log.debug('perfdata:%s' % mobj.PERFDATA)
            for metric in mobj.PERFDATA.split():
                try:
                    nobj = copy.copy(mobj)
                    (nobj.LABEL, d) = metric.split('=')
                    v = d.split(';')[0]
                    u = v
                    nobj.VALUE = re.sub("[a-zA-Z%]", "", v)
                    nobj.UOM = re.sub("[^a-zA-Z]+", "", u)
                    processed_objects.append(nobj)
                except:
                    log.critical("failed to parse metric: %s" % nobj.PERFDATA)
                    continue

    return processed_objects


def get_mobj(nag_array):
    """
        takes a split array of nagios variables and returns a mobj if it's
        valid. otherwise return False.
    """
    mobj = GraphiosMetric()
    for var in nag_array:
        (var_name, value) = var.split('::')
        value = re.sub("/", cfg["replacement_character"], value)
        if re.search("PERFDATA", var_name):
            mobj.PERFDATA = value
        elif re.search("^\$_", value):
            continue
        else:
            value = re.sub("\s", "", value)
            setattr(mobj, var_name, value)

    mobj.validate()
    if mobj.VALID is True:
        return mobj
    return False


def handle_file(file_name, graphite_lines):
    """
    archive processed metric lines and delete the input log files
    """
    if "test_mode" in cfg and cfg["test_mode"] == "True":
        log.debug("graphite_lines:%s" % graphite_lines)
    else:
        try:
            os.remove(file_name)
        except (OSError, IOError) as ex:
            log.critical("couldn't remove file %s error:%s" % (file_name, ex))
        else:
            log.debug("deleted %s" % file_name)


def process_spool_dir(directory):
    """
    processes the files in the spool directory
    """
    log.debug("Processing spool directory %s", directory)
    num_files = 0
    perfdata_files = os.listdir(directory)
    for perfdata_file in perfdata_files:
        mobjs = []

        if (
            perfdata_file == "host-perfdata" or
            perfdata_file == "service-perfdata"
        ):
            continue
        elif re.match('^_', perfdata_file):
            continue

        num_files += 1
        file_dir = os.path.join(directory, perfdata_file)

        if os.stat(file_dir)[6] == 0:
            # file was 0 bytes
            handle_file(file_dir, 0)
            continue

        mobjs = process_log(file_dir)
        mobjs_len = len(mobjs)
        num_lines_processed = send_backends(mobjs)
        if num_lines_processed > 1:
            # this number being over 1 isn't quite right. What if we
            # wrote to the stdout backend but not any other? Then we are
            # deleting a file, we shouldn't be. Need to see if any one backend
            # returns successfully (besides stdout) then we can delete the
            # file.
            handle_file(file_dir, len(mobjs))

    log.info("Processed %s files (%s metrics,%s backended) in %s" % (num_files,
             mobjs_len, num_lines_processed, directory))


def init_backends():
    """
    I'm going to be a little forward thinking with this and build a global dict
    of enabled back-ends whose values are instantiations of the back-end
    objects themselves. I know, global bad, but hypothetically we could modify
    this dict dynamically via a runtime-interface (graphiosctl?) to turn off/on
    backends without having to restart the graphios process.  I feel like
    that's enough of a win to justify the global. If you build it, they will
    come.
    """
    global enabled_backends
    enabled_backends = {}

    #PLUGIN WRITERS! register your new backends by adding their obj name here
    avail_backends = ("carbon",
                      "statsd",
                      "librato",
                      "stdout",
                      )

    #populate the controller dict from avail + config. this assumes you named
    #your plugin the same as your config option enabling the plugin (eg.
    #carbon and enable_carbon)

    for plugin in avail_backends:
        cfg_option = "enable_%s" % (plugin)
        if cfg_option in cfg and cfg[cfg_option] == "True":
            backend_obj = getattr(backends, plugin)
            enabled_backends[plugin] = backend_obj(cfg)

    log.info("Enabled backends: %s" % enabled_backends.keys())


def disable_backend(backend):
    """
    example function to disable a backend while we're running
    """
    log.info("Disabling : %s" % backend)
    try:
        del enabled_backends[backend]
    except:
        log.critical("Could not disable %s. Sorry." % backend)
    else:
        log.info("Enabled backends: %s" % enabled_backends.keys())


def enable_backend(backend):
    """
    example function to enable a backend while we're running
    """
    try:
        enabled_backends[backend] = getattr(backends, backend)
    except:
        log.critical("Could not enable %s. Sorry." % backend)
    else:
        log.info("Enabled backends: %s" % enabled_backends.keys())


def send_backends(metrics):
    """
    use the enabled_backends dict to call into the backend send functions
    """
    global enabled_backends

    if len(enabled_backends) < 1:
        log.critical("At least one Back-end must be enabled in graphios.cfg")
        sys.exit(1)

    ret = 0
    processed_lines = 0

    for backend in enabled_backends:
        processed_lines = enabled_backends[backend].send(metrics)
        #log.debug('got %s lines from b-e' % processed_lines)
        ret += processed_lines

    #log.debug("send_backends, returning: %s" % ret)
    return ret


def main():
    log.info("graphios startup.")
    try:
        while True:
            process_spool_dir(spool_directory)
            log.debug("graphios sleeping.")
            time.sleep(float(cfg["sleep_time"]))
    except KeyboardInterrupt:
        log.info("ctrl-c pressed. Exiting graphios.")


if __name__ == '__main__':
    # global cfg
    if len(sys.argv) > 1:
        (options, args) = parser.parse_args()
        if options.config:
            cfg = read_config(options.config)
            verify_config(cfg)
        else:
            configure(options)
    else:
        cfg = read_config(config_file)
        verify_config(cfg)
        configure()
    print cfg
    init_backends()
    main()
