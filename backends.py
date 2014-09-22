# vim: set ts=4 sw=4 tw=79 et :

import socket
import cPickle as pickle
import struct
import re
import logging
import sys
import base64
import urllib2
import json
import os
# ###########################################################
# #### Librato Backend


class librato(object):
    def __init__(self, cfg):
        """
        Implements the librato backend-module
        """

        self.log = logging.getLogger("log.backends.librato")
        self.log.info("Librato Backend Initialized")
        self.api = "https://metrics-api.librato.com"
        self.sink_name = "graphios-librato"
        self.sink_version = "0.0.1"
        self.flush_timeout_secs = 5
        self.gauges = {}
        self.max_metrics_payload = 500

        try:
            cfg["email"]
        except:
            self.log.critical("please define email in the graphios.cfg")
            sys.exit(1)
        else:
            self.email = cfg['email']

        try:
            cfg["token"]
        except:
            self.log.critical("please define token in the graphios.cfg")
            sys.exit(1)
        else:
            self.token = cfg['token']

        try:
            cfg['namevals']
        except:
            self.namevals = ['GRAPHITEPREFIX', 'SERVICEDESC',
                             'GRAPHITEPOSTFIX', 'LABEL']
        else:
            self.namevals = cfg['namevals']

        try:
            cfg['sourcevals']
        except:
            self.sourcevals = ['HOSTNAME']
        else:
            self.sourcevals = cfg['sourcevals']

        try:
            cfg["floor_time_secs"]
        except:
            self.floor_time_secs = 15
        else:
            self.floor_time_secs = cfg["floor_time_secs"]

    def add_measure(self, m):
        ts = int(m.TIMET)
        if self.floor_time_secs is not None:
            ts = (ts / self.floor_time_secs) * self.floor_time_secs

        source = ''
        for s in self.sourcevals:
            source += getattr(m, s)
            source += '.'
        source = re.sub(r"\.$", '', source)  # fix sources that end in dot
        source = re.sub(r"\.\.", '.', source)  # fix sources with double dots

        name = ''
        for n in self.namevals:
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

    def flush_payload(self, headers, g):
        """
        POST a payload to Librato.
        """
        body = json.dumps({'gauges': g})
        url = "%s/v1/metrics" % (self.api)
        req = urllib2.Request(url, body, headers)

        try:
            f = urllib2.urlopen(req, timeout=self.flush_timeout_secs)
            response = f.read()     # <-- we never look at the response
            f.close()
        except urllib2.HTTPError as error:
            body = error.read()
            self.log.warning('Failed to send metrics to Librato: Code: \
                                %d . Response: %s' % (error.code, body))
        except IOError as error:
            if hasattr(error, 'reason'):
                self.log.warning('Error when sending metrics Librato \
                                    (%s)' % (error.reason))
            elif hasattr(error, 'code'):
                self.log.warning('Error when sending metrics Librato \
                                    (%s)' % (error.code))
            else:
                self.log.warning('Error when sending metrics Librato \
                                    and I dunno why')

        # should we not do something with the actual response? make sure it's
        # 200 ok, or something?

        # we capture the http error code and log it in the case of trouble in
        # the try section above, here's a sample log line from some metric data
        # that got rejected from librato because it's too old:

        """
        Failed to send metrics to Librato: Code: 400 . Response: {"errors":
        {"params":{"measure_time":["is too far in the past"]}}}
        """
        return len(g)

    def flush(self):
        """
        POST a collection of gauges to Librato.
        """
        # Nothing to do
        if len(self.gauges) == 0:
            return 0

        # Limit our payload sizes
        max_metrics_payload = 500       # this is never used

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
                ret = self.flush_payload(headers, metrics)    # ret is not used
                count = 0
                metrics = []

        if count > 0:
            self.flush_payload(headers, metrics)
            self.gauges = {}

        return count

    def build_basic_auth(self):

        base64string = base64.encodestring('%s:%s' % (self.email, self.token))
        return base64string.translate(None, '\n')

    def build_user_agent(self):

        sink_name = "graphios-librato"
        sink_version = "0.0.1"

        try:
            uname = os.uname()
            system = "; ".join([uname[0], uname[4]])
        except:
            system = os.name()

        pver = sys.version_info
        user_agent = '%s/%s (%s) Python-Urllib2/%d.%d' % \
                     (sink_name, sink_version,
                      system, pver[0], pver[1])
        return user_agent

    def send(self, metrics):

        # Construct the output
        for m in metrics:
            self.add_measure(m)

        # Flush
        ret = self.flush()

        return ret


############################################################
# #### Carbon back-end #####

class carbon(object):
    def __init__(self, cfg):
        self.log = logging.getLogger("log.backends.carbon")
        self.log.info("Carbon Backend Initialized")
        try:
            cfg['carbon_server']
        except:
            self.carbon_server = '127.0.0.1'
        else:
            self.carbon_server = cfg['carbon_server']

        try:
            cfg['carbon_port']
        except:
            self.carbon_port = 2004
        else:
            self.carbon_port = int(cfg['carbon_port'])

        try:
            cfg['replacement_character']
        except:
            self.replacement_character = '_'
        else:
            self.replacement_character = cfg['replacement_character']

        try:
            cfg['carbon_max_metrics']
            self.carbon_max_metrics = cfg['carbon_max_metrics']
        except:
            self.carbon_max_metrics = 200

        try:
            cfg['use_service_desc']
            self.use_service_desc = cfg['use_service_desc']
        except:
            self.use_service_desc = False

    def convert_pickle(self, metrics):
        """
            Converts the metric obj list into a pickle message
        """
        pickle_list = []
        messages = []
        for m in metrics:
            path = self.build_path(m)
            value = m.LABEL
            timestamp = m.TIMET
            metric_tuple = (path, (timestamp, value))
            pickle_list.append(metric_tuple)
        for pickle_list_chunk in self.chunks(pickle_list,
                                             self.carbon_max_metrics):
            payload = pickle.dumps(pickle_list_chunk)
            header = struct.pack("!L", len(payload))
            message = header + payload
            messages.append(message)
        return messages

    def chunks(self, l, n):
        """ Yield successive n-sized chunks from l.
        """
        for i in xrange(0, len(l), n):
            yield l[i:i + n]

    def build_path(self, m):
        """
            Builds a carbon metric
        """
        if self.use_service_desc:
            # we want: prefix.hostname.service_desc.postfix.perfdata
            service_desc = self.fixstring(m.SERVICEDESC)
            path = "%s.%s.%s.%s" % (m.GRAPHITEPREFIX, m.HOSTNAME,
                                    service_desc, m.GRAPHITEPOSTFIX, m.LABEL)

        else:
            path = "%s.%s.%s.%s" % (m.GRAPHITEPREFIX, m.HOSTNAME,
                                    m.GRAPHITEPOSTFIX, m.LABEL)
        path = re.sub(r"\.$", '', path)  # fix paths that end in dot
        path = re.sub(r"\.\.", '.', path)  # fix paths with double dots
        path = self.fix_string(path)
        return path

    def fix_string(self, my_string):
        """
        takes a string and replaces whitespace and invalid carbon chars with
        the global replacement_character
        """
        invalid_chars = '~!@#$:;%^*()+={}[]|\/<>'
        my_string = re.sub("\s", self.replacement_character, my_string)
        for char in invalid_chars:
            my_string = my_string.replace(char, self.replacement_character)
        return my_string

    def send(self, metrics):
        """
            Connect to the Carbon server
            Send the metrics
        """
        ret = 0
        sock = socket.socket()
        self.log.debug("Connecting to carbon at %s:%s" %
                       (self.carbon_server, self.carbon_port))
        try:
            sock.connect((self.carbon_server, self.carbon_port))
            self.log.debug("connected")
        except Exception, ex:
            self.log.warning("Can't connect to carbon: %s:%s %s" % (
                             self.carbon_server, self.carbon_port, ex))

        messages = self.convert_pickle(metrics)
        try:
            for message in messages:
                sock.sendall(message)
        except Exception, ex:
            self.log.critical("Can't send message to carbon error:%s" % ex)
        else:
            ret += 1

        sock.close()
        return ret


# ###########################################################
# #### statsd backend  #######################################

class statsd(object):
    def __init__(self, cfg):
        self.log = logging.getLogger("log.backends.statsd")
        self.log.info("Statsd backend initialized")
        try:
            cfg['statsd_server']
        except:
            self.statsd_server = '127.0.0.1'
        else:
            self.statsd_server = cfg['statsd_server']

        try:
            cfg['statsd_port']
        except:
            self.statsd_port = 8125
        else:
            self.statsd_port = int(cfg['statsd_port'])

    def convert(self, metrics):
        # Converts the metric object list into a list of statsd tuples
        out_list = []
        for m in metrics:
            path = '%s.%s.%s.%s' % (m.GRAPHITEPREFIX, m.HOSTNAME,
                                    m.GRAPHITEPOSTFIX, m.LABEL)
            path = re.sub(r'\.$', '', path)  # fix paths that end in dot
            path = re.sub(r'\.\.', '.', path)  # fix paths with empty values
            value = "%s|g" % m.VALUE  # you wanted a gauge right?
            metric_tuple = "%s:%s" % (path, value)
            out_list.append(metric_tuple)

        return out_list

    def send(self, metrics):
        # Fire metrics at the statsd server and hope for the best (loludp)
        ret = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.log.debug("sending to statsd at %s:%s" %
                       (self.statsd_server, self.statsd_port))

        mlist = self.convert(metrics)
        ret = 0
        for m in mlist:
            try:
                sock.sendto(m, (self.statsd_server, self.statsd_port))
            except Exception, ex:
                self.log.critical("Can't send metric to statsd error:%s" % ex)
            else:
                ret += 1

        return ret


# ###########################################################
# #### stdout backend  #######################################

class stdout(object):
    def __init__(self, cfg):
        self.log = logging.getLogger("log.backends.stdout")
        self.log.info("STDOUT Backend Initialized")

    def send(self, metrics):
        ret = 0
        for metric in metrics:
            ret += 1
            print("%s:%s" % ('LABEL', metric.LABEL))
            print("%s:%s" % ('VALUE ', metric.VALUE))
            print("%s:%s" % ('UOM ', metric.UOM))
            print("%s:%s" % ('DATATYPE ', metric.DATATYPE))
            print("%s:%s" % ('TIMET ', metric.TIMET))
            print("%s:%s" % ('HOSTNAME ', metric.HOSTNAME))
            print("%s:%s" % ('SERVICEDESC ', metric.SERVICEDESC))
            print("%s:%s" % ('PERFDATA ', metric.PERFDATA))
            print("%s:%s" % ('SERVICECHECKCOMMAND',
                             metric.SERVICECHECKCOMMAND))
            print("%s:%s" % ('HOSTCHECKCOMMAND ', metric.HOSTCHECKCOMMAND))
            print("%s:%s" % ('HOSTSTATE ', metric.HOSTSTATE))
            print("%s:%s" % ('HOSTSTATETYPE ', metric.HOSTSTATETYPE))
            print("%s:%s" % ('SERVICESTATE ', metric.SERVICESTATE))
            print("%s:%s" % ('SERVICESTATETYPE ', metric.SERVICESTATETYPE))
            print("%s:%s" % ('GRAPHITEPREFIX ', metric.GRAPHITEPREFIX))
            print("%s:%s" % ('GRAPHITEPOSTFIX ', metric.GRAPHITEPOSTFIX))
            print("-------")

        return ret


# ###########################################################
# #### start here  #######################################

if __name__ == "__main__":
    print("I'm just a lowly module. Try calling graphios.py instead")
    sys.exit(42)
