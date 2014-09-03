# Supports flushing graphios metrics to Librato
# vim: set ts=4 sw=4 tw=79 et :

import sys
import logging
import re
import base64
import urllib2
import json
import os


# ###########################################################
# #### You will likely need to change some of the below #####

# your librato credentials here:
email = 'your email'
token = 'your token'

# floor_time_secs: Floor samples to this time (match graphios sleep_time)
floor_time_secs = 15

# The values we'll use to construct the metric name:
namevals = ['GRAPHITEPREFIX', 'SERVICEDESC', 'GRAPHITEPOSTFIX', 'LABEL']

# The values we'll use to construct the librato source dimension:
sourcevals = ['HOSTNAME']

# #### You should stop changing things unless you know what you are doing ####
# ###########################################################################


class LibratoStore(object):
    def __init__(self):
        """
        Implements an interface that allows metrics to be persisted to Librato.

        Raises a :class:`ValueError` on bad arguments or `Exception` on missing
        configuration

        """

        self.logger = logging.getLogger("log.libratomodule")
        self.logger.info("Librato Backend Initialized")

        self.api = "https://metrics-api.librato.com"
        self.sink_name = "graphios-librato"
        self.sink_version = "0.0.1"
        self.flush_timeout_secs = 5
        self.gauges = {}

        # Limit our payload sizes
        self.max_metrics_payload = 500

        self.sfx_map = {
            'sum': 'sum',
            'sum_sq': 'sum_squares',
            'count': 'count',
            'stdev': None,
            'lower': 'min',
            'upper': 'max',
            'mean': None
        }

        self.email = email
        self.token = token
        self.floor_time_secs = floor_time_secs

    def add_measure(self, m):
        ts = int(m.TIMET)
        if self.floor_time_secs is not None:
            ts = (ts / self.floor_time_secs) * self.floor_time_secs

        source = ''
        for s in sourcevals:
            source += getattr(m, s)
            source += '.'
        source = re.sub(r"\.$", '', source)  # fix sources that end in dot
        source = re.sub(r"\.\.", '.', source)  # fix sources with double dots

        name = ''
        for n in namevals:
            name += getattr(m, n)
            name += '.'
        name = re.sub(r"\.$", '', name)  # fix names that end in dot
        name = re.sub(r"\.\.", '.', name)  # fix names with double dots

        k = "%s\t%s" % (name, source)
        if k not in self.gauges:
            self.gauges[k] = {
                'name': name,
                'source': source,
                'measure_time': ts,
            }
        value = float(m.VALUE)
        self.gauges[k]['value'] = value

    def build(self, metrics):

        """
        Build metric data to send to Librato

       :Parameters:
        - `metrics` : A list of metric objects from graphios
        """
        if not metrics:
            return

        # Construct the output
        for m in metrics:
            self.add_measure(m)

    def flush_payload(self, headers, g):
        """
        POST a payload to Librato.
        """

        body = json.dumps({'gauges': g})
        url = "%s/v1/metrics" % (self.api)
        req = urllib2.Request(url, body, headers)
        ret = True

        try:
            f = urllib2.urlopen(req, timeout=self.flush_timeout_secs)
            response = f.read()
            f.close()
        except urllib2.HTTPError as error:
            ret = False
            body = error.read()
            self.logger.warning('Failed to send metrics to Librato: Code: \
                                %d . Response: %s' % (error.code, body))
        except IOError as error:
            ret = False
            if hasattr(error, 'reason'):
                self.logger.warning('Error when sending metrics Librato \
                                    (%s)' % (error.reason))
            elif hasattr(error, 'code'):
                self.logger.warning('Error when sending metrics Librato \
                                    (%s)' % (error.code))
            else:
                self.logger.warning('Error when sending metrics Librato \
                                    and I dunno why')

        # should we not do something with the actual response? make sure it's
        # 200 ok, or something?
        return ret

    def flush(self):
        """
        POST a collection of gauges to Librato.
        """

        ret = True

        # Nothing to do
        if len(self.gauges) == 0:
            return ret

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': self.build_user_agent(),
            'Authorization': 'Basic %s' % self.build_basic_auth()
        }

        metrics = []
        count = 0
        for g in self.gauges.values():
            metrics.append(g)
            count += 1

            if count >= self.max_metrics_payload:
                ret = self.flush_payload(headers, metrics)
                count = 0
                metrics = []

        if count > 0:
            ret = self.flush_payload(headers, metrics)

        return ret

    def build_basic_auth(self):
        base64string = base64.encodestring('%s:%s' % (self.email, self.token))
        return base64string.translate(None, '\n')

    def build_user_agent(self):
        try:
            uname = os.uname()
            system = "; ".join([uname[0], uname[4]])
        except:
            system = os.name()

        pver = sys.version_info
        user_agent = '%s/%s (%s) Python-Urllib2/%d.%d' % \
                     (self.sink_name, self.sink_version,
                      system, pver[0], pver[1])
        return user_agent


def send(metrics):
    # Initialize the logger
    logging.basicConfig()

    # Intialize from our arguments
    librato = LibratoStore()

    # Flush
    librato.build(metrics)
    ret = librato.flush()

    return ret
