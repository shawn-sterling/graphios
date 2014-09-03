# vim: set ts=4 sw=4 tw=79 et :

import socket
import cPickle as pickle
import struct
import re
import logging


############################################################
# #### You will likely need to change some of the below #####

# carbon server info
carbon_server = '127.0.0.1'

# carbon pickle receiver port (normally 2004)
carbon_port = 2004

# Character to use as replacement for invalid characters in metric names
replacement_character = '_'

# #### You should stop changing things unless you know what you are doing #####
##############################################################################

log = logging.getLogger('log.carbonmodule')


def __init__(self):
    log.info("******* Carbon Backend Initialized ********")


def convert_pickle(metrics):
    """
        Converts the metric obj list into a pickle message
    """
    pickle_list = []
    for m in metrics:
        path = "%s.%s.%s.%s" % (m.GRAPHITEPREFIX, m.HOSTNAME,
                                m.GRAPHITEPOSTFIX, m.LABEL)
        value = m.LABEL
        timestamp = m.TIMET
        path = re.sub(r"\.$", '', path)  # fix paths that end in dot
        path = re.sub(r"\.\.", '.', path)  # fix paths with double dots
        path = fix_carbon_string(path)
        metric_tuple = (path, (timestamp, value))
        pickle_list.append(metric_tuple)

    payload = pickle.dumps(pickle_list)
    header = struct.pack("!L", len(payload))
    message = header + payload
    return message


def fix_carbon_string(my_string):
    """
        takes a string and replaces whitespace and invalid carbon chars with
        the global replacement_character
    """
    invalid_chars = '~!@#$:;%^*()+={}[]|\/<>'
    my_string = re.sub("\s", replacement_character, my_string)
    for char in invalid_chars:
        my_string = my_string.replace(char, replacement_character)
    return my_string


def send(metrics):
    """
        Connect to the Carbon server
        Send the metrics
    """
    ret = True
    sock = socket.socket()
    log.debug("Connecting to carbon at %s:%s" % (carbon_server, carbon_port))
    try:
        sock.connect((carbon_server, carbon_port))
        log.debug("connected")
    except Exception, ex:
        ret = False
        log.warning("Can't connect to carbon: %s:%s %s" %
                    (carbon_server, carbon_port, ex))

    message = convert_pickle(metrics)
    try:
        sock.sendall(message)
    except Exception, ex:
        ret = False
        log.critical("Can't send message to carbon error:%s" % ex)

    sock.close()
    return ret
