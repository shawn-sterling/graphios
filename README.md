# Introduction

Graphios is a script to emit nagios perfdata to various upstream metrics
processing and time-series (graphing) systems. It's currently compatible with
[graphite], [statsd], and [Librato], with [influxDB], [Heka], and possibly
[RRDTool] support coming soon. Graphios can emit Nagios metrics to any number
of supported upstream metrics systems simultaenously.

# Requirements

* A working nagios / icinga server
* A functional carbon or statsd daemon, and/or Librato credentials
* Python 2.4 or later

# License

Graphios is released under the [GPL v2](http://www.gnu.org/licenses/gpl-2.0.html).

# Documentation

The goal of graphios is to get nagios perf data into a graphing system like
graphite (carbon). Systems like these typically use a dot-delimited metric name
to store each metric hierarcicly, so it can be easily located later.

Graphios creates these metric names one of two ways.

1 - by reading a pair of custom variables that
you configure for services and hosts called \_graphiteprefix and
\_graphitepostfix.  Together, these custom variables enable you to control the
metric name that gets sent to whatever back-end metrics system you're using.
You don't have to set them both, but things will certainly be less confusing
for you if you set at least one or the other.

2 - by using your service description in the format:

\_graphiteprefix.hostname.service-description.\_graphitepostfix.perfdata

so if you didn't feel like setting your graphiteprefix and postfix, it would
just use:

hostname.service-description.perfdata

If you are using option 2, that means EVERY service will be sent to graphite.
You will also want to make sure your service descriptions are consistant or
your backend naming will be really weird.

I think most people will use the first option, so let's work with that for a
bit. What gets sent to graphite is this:

graphiteprefix.hostname.graphitepostfix.perfdata

The specific content of the perfdata section depends on each particular Nagios
plugin's output.

Simple Example
--------------

A simple example is the check\_host\_alive command (which calls the check\_icmp
plugin by default). The check\_icmp plugin returns the following perfstring:

rta=4.029ms;10.000;30.000;0; pl=0%;5;10;; rtmax=4.996ms;;;; rtmin=3.066ms;;;;

If we configured a host with a custom graphiteprefix variable like this:

<pre>
define host {
    host_name                   myhost
    check_command               check_host_alive
    _graphiteprefix             ops.nagios01.pingto
}
</pre>

Graphios will construct and emit the following metric name to the upstream metric system:

    ops.nagios01.pingto.myhost.rta 4.029 nagios_timet
    ops.nagios01.pingto.myhost.pl 0 nagios_timet
    ops.nagios01.pingto.myhost.rtmax 4.996 nagios_timet
    ops.nagios01.pingto.myhost.rtmin 3.066 nagios_timet

Where *nagios\_timet* is the a unix epoch time stamp from when the plugin
results were received by Nagios core.  Your prefix is of course, entirely up to
you. In our example, our prefix refers to the Team that created the metric
(Ops), becuause our upstream metrics system is used by many different teams.
Afer the team name, we've identified the specific Nagios host that took this
measurement, because we actually have several Nagios boxes, and finally,
'pingto' is the name of this specific metric: the *ping* time from nagios01
*to* myhost.

Another example
---------------

Lets take a look at the check_load plugin, which returns the following
perfdata:

load1=8.41;20;22;; load5=6.06;18;20;; load15=5.58;16;18

Our service is defined like this:

<pre>
define service {
    service_description         Load
    host_name                   myhost
    _graphiteprefix             datacenter01.webservers
    _graphitepostfix            nrdp.load
}
</pre>

With this confiuration, graphios generates the following metric names:

    datacenter01.webservers.myhost.nrdp.load.load1 8.41 nagios_timet
    datacenter01.webservers.myhost.nrdp.load.load5 6.06 nagios_timet
    datacenter01.webservers.myhost.nrdp.load.load15 5.58 nagios_timet

As you can probably guess, our custom prefix in this example identifies the
specific data center, and server-type from which these metrics originated,
while our postfix refers to the check_nrdp plugin, which is the means by which
we collected the data, followed finally by the metric-type.

You should think carefully about how you name your metrics, because later on,
these names will enable you to easily combine metrics (like load1) across
various sources (like all webservers).

# A few words on Naming things for Librato

The default configuration that works for Graphite also does what you'd expect
for Librato, so if you're just getting started, and you want to check out
Librato, don't worry about it, ignore this section and forge ahead.

But you're a power user, you should be aware that the Librato Backend is
actually generating a differet metric name than the other plugins.
Librato is a very metrics-centric platform. Metrics are the first-class entity,
and sources (like hosts), are actually a separate dimension in their system.
This is very cool when you're monitoring ephemeral things that aren't hosts,
like threads, or worker processes, but it slightly complicates things here.

So, for example, where the Graphite plugin generates a name like this (from the
example above):

    datacenter01.webservers.myhost.nrdp.load.load1

The Librato plugin will generate a name that omits the hostname:

    datacenter01.webservers.nrdp.load.load1

And then it will automatically send the hostname as the source dimension when
it emits the metric to Librato. For 99% of everyone, this is exactly what you
want. But if you're a 1%'er you can influence this behavior by modifying the
"namevals" and "sourcevals" lists in the librato section of the graphios.cfg

Automatic names
---------------

UPDATED: Graphios now supports automatic names, because custom variables are
hard. :)

This is an all or nothing setting, meaning if you turn this on all services
will now send to graphios (instead of just the ones with the prefix and postfix
setup). This will work fine, so long as you have very consistent service
descriptions.

To turn this on, modify the graphios.cfg and change:

use_service_desc = False
to
use_service_desc = True

Big Fat Warning
---------------

Graphios assumes your checks are using the same unit of measurement. Most
plugins support this, some do not. check\_icmp) always reports in ms for
example. If your plugins do not support doing this, you can wrap your plugins
using check\_mp (another program I made, should be on github shortly if not
already).


# Installation

This is recommended for intermediate+ Nagios administrators. If you are just
learning Nagios this might be a difficult pill to swallow depending on your
experience level.

I have been using this in production on a medium size nagios installation for a
couple months.

Setting this up on the nagios front is very much like pnp4nagios with npcd.
(You do not need to have any pnp4nagios experience at all). If you are already
running pnp4nagios , check out my pnp4nagios notes (below).

Steps:

(1) nagios.cfg
--------------

Your nagios.cfg is going to need to modified to send the graphite data to the perfdata files.

<pre>
service_perfdata_file=/var/spool/nagios/graphios/service-perfdata
service_perfdata_file_template=DATATYPE::SERVICEPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tSERVICEDESC::$SERVICEDESC$\tSERVICEPERFDATA::$SERVICEPERFDATA$\tSERVICECHECKCOMMAND::$SERVICECHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$\tSERVICESTATE::$SERVICESTATE$\tSERVICESTATETYPE::$SERVICESTATETYPE$\tGRAPHITEPREFIX::$_SERVICEGRAPHITEPREFIX$\tGRAPHITEPOSTFIX::$_SERVICEGRAPHITEPOSTFIX$

service_perfdata_file_mode=a
service_perfdata_file_processing_interval=15
service_perfdata_file_processing_command=graphite_perf_service

host_perfdata_file=/var/spool/nagios/graphios/host-perfdata
host_perfdata_file_template=DATATYPE::HOSTPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tHOSTPERFDATA::$HOSTPERFDATA$\tHOSTCHECKCOMMAND::$HOSTCHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$\tGRAPHITEPREFIX::$_HOSTGRAPHITEPREFIX$\tGRAPHITEPOSTFIX::$_HOSTGRAPHITEPOSTFIX$

host_perfdata_file_mode=a
host_perfdata_file_processing_interval=15
host_perfdata_file_processing_command=graphite_perf_host
</pre>

Which sets up some custom variables, specifically:
for services:
$\_SERVICEGRAPHITEPREFIX
$\_SERVICEGRAPHITEPOSTFIX

for hosts:
$\_HOSTGRAPHITEPREFIX
$\_HOSTGRAPHITEPOSTFIX

The prepended HOST and SERVICE is just the way nagios works, \_HOSTGRAPHITEPREFIX means it's the \_GRAPHITEPREFIX variable from host configuration.

(2) nagios commands
-------------------

There are 2 commands we setup in the nagios.cfg:

graphite\_perf\_service
graphite\_perf\_host

Which we now need to define:

I use include dirs, so I make a new file called graphios\_commands.cfg inside my include dir. Do that, or add the below commands to one of your existing nagios config files.

#### NOTE: Your spool directory may be different, this is setup in step (1) the service_perfdata_file, and host_perfdata_file.

<pre>
define command {
    command_name            graphite_perf_host
    command_line            /bin/mv /var/spool/nagios/graphios/host-perfdata /var/spool/nagios/graphios/host-perfdata.$TIMET$

}

define command {
    command_name            graphite_perf_service
    command_line            /bin/mv /var/spool/nagios/graphios/service-perfdata /var/spool/nagios/graphios/service-perfdata.$TIMET$
}
</pre>

All these commands do is move the current files to a different filename that we can process without interrupting nagios. This way nagios doesn't have to sit around waiting for us to process the results.


(3) graphios.py, and backends.py
---------------

It doesn't matter where graphios.py lives, I put it in ~nagios/bin . You can
put it where-ever makes you happy.

The graphios.py can run as whatever user you want, as long as you have access
to the spool directory, and log file.

The backend modules graphios uses to ship metrics to the various
metrics-backends it supports is housed in a separate file called backends.py.
This file should be copied into the same directory as graphios.py

(4) graphios.cfg
---------------
You can copy graphios.cfg to /etc or store it together with graphios.py. In
either case, you may need to modify it to suit your environment.

Out of the box, it enables the carbon back-end and sends pickled metrics to
127.0.0.1:2004.  It also specifies the location of the graphios log and spool
directories, and controls things like log levels, sleep intervals, and of
course, backends like carbon, statsd, and librato.

(5) Run it!
---------------

We recommend running graphios.py from the console for the first time, rather
than using the init script. You may want to temporarily set log\_level to
'DEBUG' and test\_mode to True in graphios.cfg just to see what metrics you'll
emit. Don't forget to change them back after, as the DEBUG log\_level is very
verbose, and nothing will actually happen at all until you disable test mode.

Some of these can also be set via command line parameters:
<pre>
$ ./graphios.py -h

Usage: graphios.py [options]
sends nagios performance data to carbon.

Options:
  -h, --help            show this help message and exit
  -v, --verbose         sets logging to DEBUG level
  --spool-directory=SPOOL_DIRECTORY
                        where to look for nagios performance data
  --log-file=LOG_FILE   file to log to

</pre>


(6) Optional init script: graphios
----------------------------------

Remember: *screen* is not a daemon management tool.

<pre>
cp graphios.init /etc/init.d/graphios
chown root:root /etc/init.d/graphios
chmod 750 /etc/init.d/graphios
</pre>

#### NOTE: You may need to change the location and username that the script runs as. this slightly depending on where you decided to put graphios.py

The lines you will likely have to change:
<pre>
prog="/opt/nagios/bin/graphios.py"
# or use the command line options:
#prog="/opt/nagios/bin/graphios.py --log-file=/dir/mylog.log --spool-directory=/dir/my/sool"
GRAPHIOS_USER="nagios"
</pre>

(7) Your host and service configs
---------------------------------

Once you have done the above you need to add a custom variable to the hosts and
services that you want sent to graphite.

The format that will be sent to carbon is:

<pre>
_graphiteprefix.hostname._graphitepostfix.perfdata
</pre>

You do not need to set both graphiteprefix and graphitepostfix. Just one or the
other will do. If you do not set at least one of them, the data will not be
sent to graphite at all.

Examples:

<pre>
define host {
    name                        myhost
    check_command               check_host_alive
    _graphiteprefix             monitoring.nagios01.pingto
}
</pre>

Which would create the following graphite entries with data from the check\_host\_alive plugin:

    monitoring.nagios01.pingto.myhost.rta
    monitoring.nagios01.pingto.myhost.rtmin
    monitoring.nagios01.pingto.myhost.rtmax
    monitoring.nagios01.pingto.myhost.pl

<pre>
define service {
    service_description         MySQL threads connected
    host_name                   myhost
    check_command               check_mysql_health_threshold!threads-connected!3306!1600!1800
    _graphiteprefix             monitoring.nagios01.mysql
}
</pre>

Which gives me:

    monitoring.nagios01.mysql.myhost.threads_connected

See the Documentation (above) for more explanation on how this works.



# PNP4Nagios Notes:

Are you already running pnp4nagios? And want to just try this out and see if
you like it? Cool! This is very easy to do without breaking your PNP4Nagios
configuration (but do a backup just in case).

Steps:

(1) In your nagios.cfg:
-----------------------

Add the following at the end of your:

<pre>
host_perfdata_file_template
\tGRAPHITEPREFIX::$_HOSTGRAPHITEPREFIX$\tGRAPHITEPOSTFIX::$_HOSTGRAPHITEPOSTFIX$

service_perfdata_file_template
\tGRAPHITEPREFIX::$_SERVICEGRAPHITEPREFIX$\tGRAPHITEPOSTFIX::$_SERVICEGRAPHITEPOSTFIX$
</pre>

This will add the variables to your check results, and will be ignored by pnp4nagios.

(2) Change your commands:
-------------------------

(find your command names under host\_perfdata\_file\_processing\_command and service\_perfdata\_file\_processing\_command in your nagios.cfg)

You likely have 2 commands setup that look something like these two:

<pre>
define command{
       command_name    process-service-perfdata-file
       command_line    /bin/mv /usr/local/pnp4nagios/var/service-perfdata /usr/local/pnp4nagios/var/spool/service-perfdata.$TIMET$
}

define command{
       command_name    process-host-perfdata-file
       command_line    /bin/mv /usr/local/pnp4nagios/var/host-perfdata /usr/local/pnp4nagios/var/spool/host-perfdata.$TIMET$
}
</pre>

Instead of just moving the file; move it then copy it, then we can point graphios at the copy.

You can do this by either:

(1) Change the command\_line to something like:

<pre>
command_line    "/bin/mv /usr/local/pnp4nagios/var/host-perfdata /usr/local/pnp4nagios/var/spool/host-perfdata.$TIMET$ && cp /usr/local/pnp4nagios/var/spool/host-perfdata.$TIMET$ /usr/local/pnp4nagios/var/spool/graphios"
</pre>

OR

(2) Make a script:

<pre>
#!/bin/bash
/bin/mv /usr/local/pnp4nagios/var/host-perfdata /usr/local/pnp4nagios/var/spool/host-perfdata.$TIMET$
cp /usr/local/pnp4nagios/var/spool/host-perfdata.$TIMET$ /usr/local/pnp4nagios/var/spool/graphios

change the command_line to be:
command_line    /path/to/myscript.sh
</pre>

You should now be able to start at step 3 on the above instructions.

# OMD (Open Monitoring Distribution) Notes:

* UPDATE - OMD 5.6 was released on 10/02/2012
* The only changes that you would need to make to 5.6 is add the changes in step 2 (omd-process-host/service-perfdata-file commands)

OMD 5.6 is different form earlier versions in the way NPCD is setup. (Download the 5.6 source code to see the config differences)
This guide assumes you are using OMD 5.4 (Current Stable Release)

* Warning I'm not sure of the impacts that this might have when actually upgrading to 5.6
* Make sure to update SITENAME with your OMD site

(1) Update OMD 5.4's etc/pnp4nagios/nagios_npcdmod.cfg so that it looks like this:

<pre>
#
# PNP4Nagios Bulk Mode with npcd
#
process_performance_data=1

#
# service performance data
#
service_perfdata_file=/omd/sites/SITENAME/var/pnp4nagios/service-perfdata
service_perfdata_file_template=DATATYPE::SERVICEPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tSERVICEDESC::$SERVICEDESC$\tSERVICEPERFDATA::$SERVICEPERFDATA$\tSERVICECHECKCOMMAND::$SERVICECHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$\tSERVICESTATE::$SERVICESTATE$\tSERVICESTATETYPE::$SERVICESTATETYPE$\tGRAPHITEPREFIX::$_SERVICEGRAPHITEPREFIX$\tGRAPHITEPOSTFIX::$_SERVICEGRAPHITEPOSTFIX$
service_perfdata_file_mode=a
service_perfdata_file_processing_interval=15
service_perfdata_file_processing_command=omd-process-service-perfdata-file

#
# host performance data
#
host_perfdata_file=/omd/sites/SITENAME/var/pnp4nagios/host-perfdata
host_perfdata_file_template=DATATYPE::HOSTPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tHOSTPERFDATA::$HOSTPERFDATA$\tHOSTCHECKCOMMAND::$HOSTCHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$\tGRAPHITEPREFIX::$_HOSTGRAPHITEPREFIX$\tGRAPHITEPOSTFIX::$_HOSTGRAPHITEPOSTFIX$
host_perfdata_file_mode=a
host_perfdata_file_processing_interval=15
host_perfdata_file_processing_command=omd-process-host-perfdata-file
</pre>

(2) Update etc/nagios/conf.d/pnp4nagios.cfg

<pre>
define command{
       command_name    omd-process-service-perfdata-file
       command_line    /bin/mv /omd/sites/SITENAME/var/pnp4nagios/service-perfdata /omd/sites/prod/var/pnp4nagios/spool/service-perfdata.$TIMET$ && cp /omd/sites/prod/var/pnp4nagios/spool/service-perfdata.$TIMET$ /omd/sites/prod/var/graphios/spool/
}

define command{
       command_name    omd-process-host-perfdata-file
       command_line    /bin/mv /omd/sites/SITENAME/var/pnp4nagios/host-perfdata /omd/sites/prod/var/pnp4nagios/spool/host-perfdata.$TIMET$ && cp /omd/sites/prod/var/pnp4nagios/spool/host-perfdata.$TIMET$ /omd/sites/prod/var/graphios/spool/
}
</pre>


# Check_MK Notes:

How to set custom variables for services and hosts using check_mk config files.

(1) For host perf data, its simple just create a new file named "extra_host_conf.mk" (inside your check_mk conf.d dir)

(2) Run check_mk -O to generate your updated configs and reload Nagios

(3) Test via check_mk -N hostname | less, to see if your prefix or postfix is there.

<pre>
extra_host_conf["_graphiteprefix"] = [
  ( "DESIREDPREFIX.ping", ALL_HOSTS),
]
</pre>

For service perf data create a file called, "extra_service_conf.mk", remember you can use your host tags or any of kinds of tricks with check_mk config files.

<pre>
extra_service_conf["_graphiteprefix"] = [
  ( "DESIREDPREFIX.check_mk", ALL_HOSTS, ["Check_MK"]),
  ( "DESIREDPREFIX.cpu.load", ALL_HOSTS, ["CPU load"]),
]
</pre>


# Trouble getting it working?

Many people are running graphios now (cool!), but if you are having trouble
getting it working let me know. I am not offering to teach you how to setup
Nagios, this is for intermediate+ nagios users. Email me at
shawn@systemtemplar.org and I will do what I can to help.

# Got it working?

Cool! Drop me a line and let me know how it goes.

# Find a bug?

Open an Issue on github and I will try to fix it asap.

# Contributing

I'm open to any feedback / patches / suggestions.

Shawn Sterling shawn@systemtemplar.org
