import logging


log = logging.getLogger('log.stdoutmodule')


def __init__(self):
    log.info("************* STDOUT Backend Initialized *****************")


def send(metrics):
    for metric in metrics:
        print("%s:%s" % ('LABEL', metric.LABEL))
        print("%s:%s" % ('VALUE ', metric.VALUE))
        print("%s:%s" % ('UOM ', metric.UOM))
        print("%s:%s" % ('DATATYPE ', metric.DATATYPE))
        print("%s:%s" % ('TIMET ', metric.TIMET))
        print("%s:%s" % ('HOSTNAME ', metric.HOSTNAME))
        print("%s:%s" % ('SERVICEDESC ', metric.SERVICEDESC))
        print("%s:%s" % ('PERFDATA ', metric.PERFDATA))
        print("%s:%s" % ('SERVICECHECKCOMMAND', metric.SERVICECHECKCOMMAND))
        print("%s:%s" % ('HOSTCHECKCOMMAND ', metric.HOSTCHECKCOMMAND))
        print("%s:%s" % ('HOSTSTATE ', metric.HOSTSTATE))
        print("%s:%s" % ('HOSTSTATETYPE ', metric.HOSTSTATETYPE))
        print("%s:%s" % ('SERVICESTATE ', metric.SERVICESTATE))
        print("%s:%s" % ('SERVICESTATETYPE ', metric.SERVICESTATETYPE))
        print("%s:%s" % ('GRAPHITEPREFIX ', metric.GRAPHITEPREFIX))
        print("%s:%s" % ('GRAPHITEPOSTFIX ', metric.GRAPHITEPOSTFIX))
        print("-------")

    return True
