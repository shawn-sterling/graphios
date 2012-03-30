# Introduction

Graphios is a script to put nagios perfdata into graphite (carbon).

# Requirements

* A working nagios / icinga server
* A running carbon server (carbon-cache.py) (part of graphite)
* Python 2.4 or later

# License

Graphios is release under the [GPL v2](http://www.gnu.org/licenses/gpl-2.0.html).

# Documentation

The goal of graphios is to get nagios perf data into graphite (carbon).

The way we accomplish this is by setting up custom variables for services and hosts called \_graphiteprefix and \_graphitepostfix. This allows you to control the string that gets sent to graphite. You can set just the prefix or just the posfix.

The format is simply:

graphiteprefix.hostname.graphitepostfix.perfdata

What the perfdata is, depends on what perfdata your nagios plugin provides.

Simple Example
--------------

A simple example is check\_host\_alive (which is just check\_icmp). The check\_icmp plugin provides the following perfstring:

rta=4.029ms;10.000;30.000;0; pl=0%;5;10;; rtmax=4.996ms;;;; rtmin=3.066ms;;;;

My test host looks like this:

<pre>
define host {
    host_name                   myhost
    check_command               check_host_alive
    _graphiteprefix             monitoring.nagios01.pingto
}
</pre>

Graphios would then send the following to carbon:

    monitoring.nagios01.pingto.myhost.rta 4.029 nagios_timet
    monitoring.nagios01.pingto.myhost.pl 0 nagios_timet
    monitoring.nagios01.pingto.myhost.rtmax 4.996 nagios_timet
    monitoring.nagios01.pingto.myhost.rtmin 3.066 nagios_timet

The nagios\_timet is the nagios provided unix epoch time when the plugin results were received.
The idea behind 'pingto' is that this is the pingtime from nagios01 to myhost.

Another example
---------------

We have a load plugin that provides the following perfdata:

load1=8.41;20;22;; load5=6.06;18;20;; load15=5.58;16;18

And a service setup like this:

<pre>
define service {
    service_description         Load
    host_name                   myhost
    _graphiteprefix             datacenter01.webservers
    _graphitepostfix            nrdp.load
}
</pre>

Would give the following:

    datacenter01.webservers.myhost.nrdp.load.load1 8.41 nagios_timet
    datacenter01.webservers.myhost.nrdp.load.load5 6.06 nagios_timet
    datacenter01.webservers.myhost.nrdp.load.load15 5.58 nagios_timet

(nrdp = what provided the results, load = plugin name, the load1,load5, and load15 are from the plugin).


Automatic names
---------------

Who not Automatic names instead of custom variables?

I set this up first actually, I would convert service\_descriptions to be 'my-service-description' and have it so that each host was:

hostname.my-service-description.perfdata

This got unorganized pretty fast, so I had to create several custom rules and made a config file to manage all the custom rules. So then you had to manage a custom config file and the nagios configs, which I decided didn't make sense for me. This method may work for some people but for my organization it's just not going to work, so I went with keeping all of the nagios config in nagios. If you have a better idea of how to integrate nagios and graphite I'd love to hear it.


Big Fat Warning
---------------

Graphios assumes your checks are using the same unit of measurement. Most plugins support this, some do not. check\_icmp) always reports in ms for example. If your plugins do not support doing this, you can wrap your plugins using check\_mp (another program I made, should be on github shortly if not already).


# Installation

This is recommended for intermediate+ Nagios administrators. If you are just learning Nagios this might be a difficult pill to swallow depending on your experience level.

I have been using this in production on a medium size nagios installation for a couple months.

Setting this up on the nagios front is very much like pnp4nagios with npcd. (You do not need to have any pnp4nagios experience at all). If you are already running pnp4nagios , check out my pnp4nagios notes (below).

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


(3) graphios.py
---------------

It doesn't matter where graphios.py lives, I put it in ~nagios/bin . You can put it where-ever makes you happy.

The graphios.py can run as whatever user you want, as long as you have access to the spool directory, and log file.

#### NOTE: You WILL need to edit this script and change a few variables, they are right near the top and commented in the script. Here they are in case you are blind:

<pre>
############################################################
##### You will likely need to change some of the below #####

# carbon server info
carbon_server = '127.0.0.1'

# carbon pickle receiver port (normally 2004)
carbon_port = 2004

# nagios spool directory
spool_directory = '/var/spool/nagios/graphios'

# graphios log info
log_file = '/var/log/nagios/graphios.log'
log_max_size = 25165824         # 24 MB
log_level = logging.INFO
#log_level = logging.DEBUG      # DEBUG is quite verbose

# How long to sleep between processing the spool directory
sleep_time = 15

# when we can't connect to carbon, the sleeptime is doubled until we hit max
sleep_max = 480

# test mode makes it so we print what we would add to carbon, and not delete
# any files from the spool directory. log_level must be DEBUG as well.
test_mode = False

##### You should stop changing things unless you know what you are doing #####
##############################################################################
</pre>

For the first time getting this running, just run at the console (vs using the init script). You may want to set log\_level to 'DEBUG' and test\_mode to True if you want to see what will be sent to graphite. Do not forget to change them back after, as the DEBUG log\_level is very verbose, there is a log limit, but why trash disk when you don't have to?

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


(4) Optional init script: graphios
----------------------------------

You don't need an init script if you don't want one. For the first time you may want to run graphios.py at console.

cp graphios.init /etc/init.d/graphios
chown root:root /etc/init.d/graphios
chmod 750 /etc/init.d/graphios

#### NOTE: You may need to change the location and username that the script runs as. this slightly depending on where you decided to put graphios.py

The lines you will likely have to change:
<pre>
prog="/opt/nagios/bin/graphios.py"
GRAPHIOS_USER="nagios"
</pre>

(5) Your host and service configs
---------------------------------

Once you have done the above you need to add a custom variable to the hosts and services that you want sent to graphite.

The format that will be sent to carbon is:

<pre>
_graphiteprefix.hostname._graphitepostfix.perfdata
</pre>

You do not need to set both graphiteprefix and graphitepostfix. Just one or the other will do. If you do not set at least one of them, the data will not be sent to graphite at all.

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

Are you already running pnp4nagios? And want to just try this out and see if you like it? Cool! This is very easy to do without breaking your PNP4Nagios configuration (but do a backup just in case).

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


# Trouble getting it working?

I will help the first few people that have problems getting this working, and update the documentation on what is not clear. I am not offering to teach you how to setup Nagios, this is for intermediate+ nagios users. Email me at shawn@systemtemplar.org and I will do what I can to help.

# Got it working?

Cool! Drop me a line and let me know how it goes.

# Find a bug?

Open an Issue on github and I will try to fix it asap.

# Contributing

I'm open to any feedback / patches / suggestions.

I'm still learning python so any python advice would be much appreciated.

Shawn Sterling shawn@systemtemplar.org
