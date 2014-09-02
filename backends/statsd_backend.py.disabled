# vim: set ts=4 sw=4 tw=79 et :

import socket
import logging
import re

# ###########################################################
# #### CONFIGURABLES  #######################################

# statsd server info
statsd_server = '127.0.0.1'

# statsd receiver port (normally udp/8125)
statsd_port = 8125

# #### You should stop changing things unless you know what you are doing #####
# #############################################################################

log = logging.getLogger('log.statsdmodule')


def __init__(self):
    log.info("******   Statsd Backend Initialized   *********")


def convert(metrics):
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


def send(metrics):
    # Fire metrics at the statsd server and hope for the best (loludp)

    ret = True
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    log.debug("sending to statsd at %s:%s" % (statsd_server, statsd_port))

    mlist = convert(metrics)
    for m in mlist:
        try:
            sock.sendto(m, (statsd_server, statsd_port))
        except Exception, ex:
            ret = False
            log.critical("Can't send metric to statsd error:%s" % ex)

    return ret
