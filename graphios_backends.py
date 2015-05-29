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
import ast
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
        self.whitelist = []
        self.metrics_sent = 0
        self.max_metrics_payload = 500

        try:
            cfg["librato_email"]
        except:
            self.log.critical("please define librato_email in graphios.cfg")
            sys.exit(1)
        else:
            self.email = cfg['librato_email']

        try:
            cfg["librato_token"]
        except:
            self.log.critical("please define librato_token in graphios.cfg")
            sys.exit(1)
        else:
            self.token = cfg['librato_token']

        try:
            cfg['librato_namevals']
        except:
            self.namevals = ['GRAPHITEPREFIX', 'SERVICEDESC',
                             'GRAPHITEPOSTFIX', 'LABEL']
        else:
            self.namevals = cfg['librato_namevals'].split(",")

        try:
            cfg['librato_sourcevals']
        except:
            self.sourcevals = ['HOSTNAME']
        else:
            self.sourcevals = cfg['librato_sourcevals'].split(",")

        try:
            cfg["librato_floor_time_secs"]
        except:
            self.floor_time_secs = 15
        else:
            self.floor_time_secs = cfg["librato_floor_time_secs"]

        try:
            cfg["librato_whitelist"]
        except:
            self.whitelist = [re.compile(".*")]
        else:
            for pattern in json.loads(cfg["librato_whitelist"]):
                self.log.debug("adding librato whitelist pattern %s" % pattern)
                self.whitelist.append(re.compile(pattern))

    def build_path(self, vals, m):
        path = ''
        for s in vals:
            path += getattr(m, s)
            path += '.'
        path = re.sub(r"^\.", '', path)  # fix sources that begin in dot
        path = re.sub(r"\.$", '', path)  # fix sources that end in dot
        path = re.sub(r"\.\.", '.', path)  # fix sources with double dots
        return path

    def k_not_in_whitelist(self, k):
        # return True if k isn't whitelisted
        # wl_match = True
        for pattern in self.whitelist:
            if pattern.search(k) is not None:
                return False
        return True

    def add_measure(self, m):
        ts = int(m.TIMET)
        if self.floor_time_secs is not None:
            ts = (ts / self.floor_time_secs) * self.floor_time_secs

        source = self.build_path(self.sourcevals, m)
        name = self.build_path(self.namevals, m)

        k = "%s\t%s" % (name, source)

        # bail if this metric isn't whitelisted
        if self.k_not_in_whitelist(k):
            return None

        # add the metric to our gauges dict
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
            # f.read()
            f.close()
        except urllib2.HTTPError as error:
            self.metrics_sent = 0
            body = error.read()
            self.log.warning('Failed to send metrics to Librato: Code: \
                                %d . Response: %s' % (error.code, body))
        except IOError as error:
            self.metrics_sent = 0
            if hasattr(error, 'reason'):
                self.log.warning('Error when sending metrics Librato \
                                    (%s)' % (error.reason))
            elif hasattr(error, 'code'):
                self.log.warning('Error when sending metrics Librato \
                                    (%s)' % (error.code))
            else:
                self.log.warning('Error when sending metrics Librato \
                                    and I dunno why')

    def flush(self):
        """
        POST a collection of gauges to Librato.
        """
        # Nothing to do
        if len(self.gauges) == 0:
            return 0

        # Limit our payload sizes
        # max_metrics_payload = 500  # this is never used, delete it?

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
                self.flush_payload(headers, metrics)
                count = 0
                metrics = []

        if count > 0:
            self.flush_payload(headers, metrics)
            self.gauges = {}

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

        self.metrics_sent = len(metrics)
        # Construct the output
        for m in metrics:
            self.add_measure(m)

        # Flush
        self.flush()

        return self.metrics_sent


############################################################
# #### Carbon back-end #####

class carbon(object):
    def __init__(self, cfg):
        self.log = logging.getLogger("log.backends.carbon")
        self.log.info("Carbon Backend Initialized")
        try:
            cfg['carbon_servers']
        except:
            self.carbon_servers = '127.0.0.1'
        else:
            self.carbon_servers = cfg['carbon_servers']

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
            self.carbon_max_metrics = int(self.carbon_max_metrics)
        except ValueError:
            self.log.critical("carbon_max_metrics needs to be a integer")
            sys.exit(1)

        try:
            cfg['use_service_desc']
            self.use_service_desc = cfg['use_service_desc']
        except:
            self.use_service_desc = False

        try:
            cfg['test_mode']
            self.test_mode = cfg['test_mode']
        except:
            self.test_mode = False

        # try:
        #     cfg['replace_hostname']
        #     self.replace_hostname = cfg['replace_hostname']
        # except:
        #     self.replace_hostname = True

        try:
            cfg['carbon_plaintext']
            self.carbon_plaintext = cfg['carbon_plaintext']
        except:
            self.carbon_plaintext = False

    def convert_messages(self, metrics):
        """
        Converts the metric obj list into graphite messages
        """
        metric_list = []
        messages = []
        for m in metrics:
            path = self.build_path(m)
            value = m.VALUE
            timestamp = m.TIMET
            if self.carbon_plaintext:
                metric_item = "%s %s %s\n" % (path, value, timestamp)
            else:
                metric_item = (path, (timestamp, value))
            if self.test_mode:
                print "%s %s %s" % (path, value, timestamp)
            metric_list.append(metric_item)
        for metric_list_chunk in self.chunks(metric_list,
                                             self.carbon_max_metrics):
            if self.carbon_plaintext:
                messages.append("".join(metric_list_chunk))
            else:
                payload = pickle.dumps(metric_list_chunk)
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
        if m.GRAPHITEPREFIX != "":
            pre = "%s." % m.GRAPHITEPREFIX
        else:
            pre = ""
        if m.GRAPHITEPOSTFIX != "":
            post = ".%s" % m.GRAPHITEPOSTFIX
        else:
            post = ""
        # if self.replace_hostname:
        #     hostname = m.HOSTNAME.replace('.', self.replacement_character)
        # else:
        hostname = m.HOSTNAME
        if self.use_service_desc:
            # we want: (prefix.)hostname.service_desc(.postfix).perfdata
            service_desc = self.fix_string(m.SERVICEDESC)
            path = "%s%s.%s%s.%s" % (pre, hostname, service_desc, post,
                                     m.LABEL)
        else:
            path = "%s%s%s.%s" % (pre, hostname, post, m.LABEL)
        path = re.sub(r"\.$", '', path)  # fix paths that end in dot
        path = re.sub(r"\.\.", '.', path)  # fix paths with double dots
        path = self.fix_string(path)
        return path

    def fix_string(self, my_string):
        """
        takes a string and replaces whitespace and invalid carbon chars with
        the global replacement_character
        """
        invalid_chars = '~!$:;%^*()+={}[]|\/<>'
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
        servers = self.carbon_servers.split(",")
        for serv in servers:
            if ":" in serv:
                server, port = serv.split(":")
                port = int(port)
            else:
                server = serv
                if self.carbon_plaintext:
                    port = 2003
                else:
                    port = 2004
            self.log.debug("Connecting to carbon at %s:%s" % (server, port))
            try:
                sock.connect((socket.gethostbyname(server), port))
                self.log.debug("connected")
            except Exception, ex:
                self.log.warning("Can't connect to carbon: %s:%s %s" % (
                                 server, port, ex))

            messages = self.convert_messages(metrics)
            try:
                for message in messages:
                    sock.sendall(message)
            except Exception, ex:
                self.log.critical("Can't send message to carbon error:%s" % ex)
                sock.close()
                return 0
            # this only gets returned if nothing failed.
            ret += len(metrics)
            sock.close()
        return ret


# ###########################################################
# #### statsd backend  #######################################

class statsd(object):
    def __init__(self, cfg):
        self.log = logging.getLogger("log.backends.statsd")
        self.log.info("Statsd backend initialized")
        try:
            cfg['statsd_servers']
        except:
            self.statsd_servers = '127.0.0.1'
        else:
            self.statsd_servers = cfg['statsd_servers']

    def set_type(self, metric):
        # detect and set the metric type
        if re.search("gauge", metric.METRICTYPE):
            return 'g'
        elif re.search("counter", metric.METRICTYPE):
            return 'c'
        elif re.search("time", metric.METRICTYPE):
            return 'ms'
        elif re.search("set", metric.METRICTYPE):
            return 's'
        else:
            return 'g'  # default to gauge

    def convert(self, metrics):
        # Converts the metric object list into a list of statsd tuples
        out_list = []
        for m in metrics:
            path = '%s.%s.%s.%s' % (m.GRAPHITEPREFIX, m.HOSTNAME,
                                    m.GRAPHITEPOSTFIX, m.LABEL)
            path = re.sub(r'\.$', '', path)  # fix paths that end in dot
            path = re.sub(r'\.\.', '.', path)  # fix paths with empty values
            mtype = self.set_type(m)  # gauge|counter|timer|set
            value = "%s|%s" % (m.VALUE, mtype)  # emit literally this to statsd
            metric_tuple = "%s:%s" % (path, value)
            out_list.append(metric_tuple)

        return out_list

    def send(self, metrics):
        # Fire metrics at the statsd server and hope for the best (loludp)
        ret = True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        mlist = self.convert(metrics)
        ret = 0
        servers = self.statsd_servers.split(",")
        for serv in servers:
            if ":" in serv:
                server, port = serv.split(":")
                port = int(port)
            else:
                server = serv
                port = 8125
            self.log.debug("sending to statsd at %s:%s" % (server, port))
            for m in mlist:
                try:
                    sock.sendto(m, (socket.gethostbyname(server), port))
                except Exception, ex:
                    self.log.critical("Can't send metric to statsd error:%s"
                                      % ex)
                else:
                    ret += 1

        return ret

# ###########################################################
# #### influxdb backend  ####################################

class influxdb(object):
    def __init__(self, cfg):
        self.log = logging.getLogger("log.backends.influxdb")
        self.log.info("InfluxDB backend initialized")
        self.scheme = "http"
        self.default_ports = {'https': 8087, 'http': 8086}
        self.timeout = 5

        if 'influxdb_use_ssl' in cfg:
            if cfg['influxdb_use_ssl']:
                self.scheme = "https"

        if 'influxdb_servers' in cfg:
            self.influxdb_servers = cfg['influxdb_servers'].split(',')
        else:
            self.influxdb_servers = ['127.0.0.1:%i' %
                                     self.default_ports[self.scheme]]

        if 'influxdb_user' in cfg:
            self.influxdb_user = cfg['influxdb_user']
        else:
            self.log.critical("Missing influxdb_user in graphios.cfg")
            sys.exit(1)

        if 'influxdb_password' in cfg:
            self.influxdb_password = cfg['influxdb_password']
        else:
            self.log.critical("Missing influxdb_password in graphios.cfg")
            sys.exit(1)

        if 'influxdb_db' in cfg:
            self.influxdb_db = cfg['influxdb_db']
        else:
            self.influxdb_db = "nagios"

        if 'influxdb_max_metrics' in cfg:
            self.influxdb_max_metrics = cfg['influxdb_max_metrics']
        else:
            self.influxdb_max_metrics = 250

        try:
            self.influxdb_max_metrics = int(self.influxdb_max_metrics)
        except ValueError:
            self.log.critical("influxdb_max_metrics needs to be a integer")
            sys.exit(1)

    def build_url(self, server):
        """ Returns a url to specified InfluxDB-server """
        test_port = server.split(':')
        if len(test_port) < 2:
            server = "%s:%i" % (server, self.default_ports[self.scheme])

        return "%s://%s/db/%s/series?u=%s&p=%s" % (self.scheme, server,
                                                   self.influxdb_db,
                                                   self.influxdb_user,
                                                   self.influxdb_password)

    def build_path(self, m):
        """ Returns a path """
        path = ""

        if m.GRAPHITEPREFIX != "":
            path = "%s.%s." % (m.GRAPHITEPREFIX, m.HOSTNAME)
        else:
            path = "%s." % m.HOSTNAME

        if m.SERVICEDESC != "":
            path = "%s%s." % (path, m.SERVICEDESC)

        path = "%s%s" % (path, m.LABEL)

        if m.GRAPHITEPOSTFIX != "":
            path = "%s.%s" % (path, m.GRAPHITEPOSTFIX)

        return path

    def chunks(self, l, n):
        """ Yield successive n-sized chunks from l. """
        for i in xrange(0, len(l), n):
            yield l[i:i+n]

    def send(self, metrics):
        """ Connect to influxdb and send metrics """
        ret = 0
        perfdata = {}
        series = []
        for m in metrics:
            ret += 1

            path = self.build_path(m)

            if path not in perfdata:
                perfdata[path] = []

            # influx assumes timestamp in milliseconds
            timet_ms = int(m.TIMET)*1000

            # Ensure a int/float gets passed
            try:
                value = int(m.VALUE)
            except ValueError:
                try:
                    value = float(m.VALUE)
                except ValueError:
                    value = 0

            perfdata[path].append([timet_ms, value])

        for k, v in perfdata.iteritems():
            series.append({"name": k, "columns": ["time", "value"],
                           "points": v})

        series_chunks = self.chunks(series, self.influxdb_max_metrics)
        for chunk in series_chunks:
            for s in self.influxdb_servers:
                self.log.debug("Connecting to InfluxDB at %s" % s)
                json_body = json.dumps(chunk)
                req = urllib2.Request(self.build_url(s), json_body)
                req.add_header('Content-Type', 'application/json')

                try:
                    r = urllib2.urlopen(req, timeout=self.timeout)
                    r.close()
                except urllib2.HTTPError as e:
                    ret = 0
                    body = e.read()
                    self.log.warning('Failed to send metrics to InfluxDB. \
                                        Status code: %d: %s' % (e.code, body))
                except IOError as e:
                    ret = 0
                    fail_string = "Failed to send metrics to InfluxDB. "
                    if hasattr(e, 'code'):
                        fail_string = fail_string + "Status code: %s" % e.code
                    if hasattr(e, 'reason'):
                        fail_string = fail_string + str(e.reason)
                    self.log.warning(fail_string)

        return ret



# ###########################################################
# #### influxdb-0.9 backend  ####################################

class influxdb09(object):
    def __init__(self, cfg):
        self.log = logging.getLogger("log.backends.influxdb")
        self.log.info("InfluxDB backend initialized")
        self.scheme = "http"
        self.default_ports = {'https': 8087, 'http': 8086}
        self.timeout = 5

        if 'influxdb_use_ssl' in cfg:
            if cfg['influxdb_use_ssl']:
                self.scheme = "https"

        if 'influxdb_servers' in cfg:
            self.influxdb_servers = cfg['influxdb_servers'].split(',')
        else:
            self.influxdb_servers = ['127.0.0.1:%i' %
                                     self.default_ports[self.scheme]]

        if 'influxdb_user' in cfg:
            self.influxdb_user = cfg['influxdb_user']
        else:
            self.log.critical("Missing influxdb_user in graphios.cfg")
            sys.exit(1)

        if 'influxdb_password' in cfg:
            self.influxdb_password = cfg['influxdb_password']
        else:
            self.log.critical("Missing influxdb_password in graphios.cfg")
            sys.exit(1)

        if 'influxdb_db' in cfg:
            self.influxdb_db = cfg['influxdb_db']
        else:
            self.influxdb_db = "nagios"

        if 'influxdb_max_metrics' in cfg:
            self.influxdb_max_metrics = cfg['influxdb_max_metrics']
        else:
            self.influxdb_max_metrics = 250

        if 'influxdb_extra_tags' in cfg:
            self.influxdb_extra_tags = ast.literal_eval(cfg['influxdb_extra_tags'])
            print self.influxdb_extra_tags
        else:
            self.influxdb_extra_tags = {}

        try:
            self.influxdb_max_metrics = int(self.influxdb_max_metrics)
        except ValueError:
            self.log.critical("influxdb_max_metrics needs to be a integer")
            sys.exit(1)

    def build_url(self, server):
        """ Returns a url to specified InfluxDB-server """
        test_port = server.split(':')
        if len(test_port) < 2:
            server = "%s:%i" % (server, self.default_ports[self.scheme])

        return "%s://%s/write?u=%s&p=%s" % (self.scheme, server,
                                                   self.influxdb_user,
                                                   self.influxdb_password)

    def chunks(self, l, n):
        """ Yield successive n-sized chunks from l. """
        for i in xrange(0, len(l), n):
            yield l[i:i+n]

    def send(self, metrics):
        from pprint import pprint
        """ Connect to influxdb and send metrics """
        ret = 0
        perfdata = []
        for m in metrics:
            ret += 1

            if (m.SERVICEDESC == ''):
                path = m.HOSTCHECKCOMMAND
            else:
                path = m.SERVICEDESC

            # Ensure a int/float gets passed
            try:
                value = int(m.VALUE)
            except ValueError:
                try:
                    value = float(m.VALUE)
                except ValueError:
                    value = 0

            tags = { "check": m.LABEL, "host": m.HOSTNAME }
            tags.update(self.influxdb_extra_tags)

            perfdata.append({
                                "timestamp": int(m.TIMET),
                                "name": path,
                                "tags": tags,
                                "fields": {"value": value}
                            })


        series_chunks = self.chunks(perfdata, self.influxdb_max_metrics)
        for chunk in series_chunks:
            series = {"database": self.influxdb_db, "points": chunk}
            for s in self.influxdb_servers:
                self.log.debug("Connecting to InfluxDB at %s" % s)
                json_body = json.dumps(series)
                req = urllib2.Request(self.build_url(s), json_body)
                req.add_header('Content-Type', 'application/json')

                try:
                    pass
                    #r = urllib2.urlopen(req, timeout=self.timeout)
                    #r.close()
                except urllib2.HTTPError as e:
                    ret = 0
                    body = e.read()
                    self.log.warning('Failed to send metrics to InfluxDB. \
                                        Status code: %d: %s' % (e.code, body))
                except IOError as e:
                    ret = 0
                    fail_string = "Failed to send metrics to InfluxDB. "
                    if hasattr(e, 'code'):
                        fail_string = fail_string + "Status code: %s" % e.code
                    if hasattr(e, 'reason'):
                        fail_string = fail_string + str(e.reason)
                    self.log.warning(fail_string)

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
