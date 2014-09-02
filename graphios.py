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

import os
import os.path
import imp
import sys
import copy
import re
import logging
import logging.handlers
import time
from optparse import OptionParser


############################################################
# #### You will likely need to change some of the below #####

# nagios spool directory
spool_directory = '/var/spool/nagios/graphios'

# Where to look for pluggable back-ends
bdir = '/usr/local/nagios/libexec/graphios_backends'

# graphios log info
log_file = '/var/log/nagios/graphios.log'
log_max_size = 25165824         # 24 MB
# log_level = logging.INFO
log_level = logging.DEBUG      # DEBUG is quite verbose

# How long to sleep between processing the spool directory
sleep_time = 15

# when we can't connect to carbon, the sleeptime is doubled until we hit max
sleep_max = 480

# set this to 1 to delete the service and host data files
# when we're done parsing them
delete_after = 0

# test mode makes it so we print what we would add to carbon, and not delete
# any files from the spool directory. log_level must be DEBUG as well.
test_mode = False

# Character to use as replacement for invalid characters in metric names
replacement_character = '_'

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

log = logging.getLogger('log')

# import the backend plug-ins
bfiles = [fname[:-3] for fname in os.listdir(bdir) if fname.endswith(".py")]

if bdir not in sys.path:
    sys.path.insert(1, bdir)

backends = [__import__(fname) for fname in bfiles]


class GraphiosMetric(object):
    def __init__(self):
        self.LABEL = ''  # The metric name in the perfdata from nagios
        self.VALUE = ''  # The measured value of that metric
        self.UOM = ''  # The unit of measure for the metric
        self.DATATYPE = ''  # HOSTPERFDATA|SERVICEPERFDATA
        self.TIMET = ''  # Epoc time the measurement was taken
        self.HOSTNAME = ''  # name of th host measured
        self.SERVICEDESC = ''  # nagios configured service description
        self.PERFDATA = ''  # the space-delimited raw perfdata
        self.SERVICECHECKCOMMAND = ''  # literal check command syntax
        self.HOSTCHECKCOMMAND = ''  # literal check command syntax
        self.HOSTSTATE = ''  # current state afa nagios is concerned
        self.HOSTSTATETYPE = ''  # HARD|SOFT
        self.SERVICESTATE = ''  # current state afa nagios is concerned
        self.SERVICESTATETYPE = ''  # HARD|SOFT
        self.GRAPHITEPREFIX = ''  # graphios prefix
        self.GRAPHITEPOSTFIX = ''  # graphios suffix


def configure(opts):
    global spool_directory

    log_handler = logging.handlers.RotatingFileHandler(
        opts.log_file, maxBytes=log_max_size, backupCount=4)
    formatter = logging.Formatter(
        "%(asctime)s %(filename)s %(levelname)s %(message)s",
        "%B %d %H:%M:%S")
    log_handler.setFormatter(formatter)
    log.addHandler(log_handler)

    if opts.verbose:
        log.setLevel(logging.DEBUG)
        log.addHandler(logging.StreamHandler())
    else:
        log.setLevel(log_level)

    spool_directory = opts.spool_directory


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
    except Exception, ex:
        log.critical("Can't open file:%s error: %s" % (file_name, ex))
        sys.exit(2)

    # parse each line into a metric object
    for line in file_array:
        if not re.search("^DATATYPE::", line):
            continue
        log.debug('parsing: %s' % line)
        graphite_lines += 1
        mobj = GraphiosMetric()
        variables = line.split('\t')
        for var in variables:
            (var_name, value) = var.split('::')
            value = re.sub("/", replacement_character, value)
            if re.search("PERFDATA", var_name):
                mobj.PERFDATA = value
            elif re.search("^\$_", value):
                continue
            else:
                value = re.sub("\s", "", value)
                setattr(mobj, var_name, value)

        # break out the metric object into one object per perfdata metric
        log.debug('perfdata:%s' % mobj.PERFDATA)
        for metric in mobj.PERFDATA.split():
            nobj = copy.copy(mobj)
            (nobj.LABEL, d) = metric.split('=')
            v = d.split(';')[0]
            u = v
            nobj.VALUE = re.sub("[a-zA-Z%]", "", v)
            nobj.UOM = re.sub("[^a-zA-Z]+", "", u)
            processed_objects.append(nobj)

    return processed_objects


def handle_file(file_name, graphite_lines):
    """
    rename already processed files or
    delete files if necessary
    """
    if graphite_lines == 0 or delete_after == 1:
        log.debug("removing file, %s" % file_name)
        try:
            os.remove(file_name)
        except Exception, ex:
            log.critical("couldn't remove file %s error:%s" % (file_name, ex))
    else:
        (dname, fname) = os.path.split(file_name)
        nname = os.path.join(dname, "_%s" % fname)
        log.debug("moving file, %s to %s" % (file_name, nname))
        try:
            os.rename(file_name, nname)
        except Exception, ex:
            log.critical("couldn't rename file %s error:%s" % (file_name, ex))


def process_spool_dir(directory):
    """
    processes the files in the spool directory
    """
    log.debug("Processing spool directory %s", directory)
    num_files = 0
    metric_objects = []
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
        mobjs = process_log(file_dir)
        metric_objects.extend(mobjs)
        handle_file(file_dir, len(mobjs))

    log.info("Processed %s files in %s", num_files, directory)
    return metric_objects


def main():
    while True:
        metrics = []
        log.info("graphios startup.")
        metrics = process_spool_dir(spool_directory)

        if len(metrics) > 0:
            for backend in backends:
                bret = backend.send(metrics)
                if (bret != True):
                    log.warn("Plugin returned an error: %s",
                             backend)

        log.debug("graphios sleeping.")
        time.sleep(sleep_time)

if __name__ == '__main__':
    (options, args) = parser.parse_args()
    configure(options)
    main()
