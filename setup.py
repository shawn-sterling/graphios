# vim: set ts=4 sw=4 tw=79 et :
from setuptools import setup
from setuptools.command.install import install as _install
from shutil import Error as FileError
from shutil import copy
from time import strftime
import os
import re


def find_nagios_cfg(lookin):
    """
    finds the nagios.cfg given list of directories
    """
    for path in lookin:
        for root, dirs, files in os.walk(path):
            if "nagios.cfg" in files:
                return os.path.join(root, "nagios.cfg")


def parse_nagios_cfg(nag_cfg):
    """
    parses the nagios.cfg
    """
    nconfig = {}
    inputfile = open(nag_cfg, 'r')
    for line in inputfile:
        if re.match('[a-zA-Z]', line[0]):
            try:
                option, value = line.split("=")
            except:
                continue
            else:
                nconfig[option.rstrip()] = value.rstrip()
    inputfile.close()
    return nconfig


def add_perfdata_config(nconfig, nag_cfg):
    """
    adds the graphios perfdata cfg to the nagios.cfg
    """
    main_config = [
        "\n",
        "###### Auto-generated Graphios configs #######",
        "process_performance_data=1",
        "service_perfdata_file=/var/spool/nagios/graphios/service-perfdata",
        "service_perfdata_file_template=DATATYPE::SERVICEPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tSERVICEDESC::$SERVICEDESC$\tSERVICEPERFDATA::$SERVICEPERFDATA$\tSERVICECHECKCOMMAND::$SERVICECHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$\tSERVICESTATE::$SERVICESTATE$\tSERVICESTATETYPE::$SERVICESTATETYPE$\tGRAPHITEPREFIX::$_SERVICEGRAPHITEPREFIX$\tGRAPHITEPOSTFIX::$_SERVICEGRAPHITEPOSTFIX$",
        "service_perfdata_file_mode=a",
        "service_perfdata_file_processing_interval=15",
        "service_perfdata_file_processing_command=graphios_perf_service",
        "host_perfdata_file=/var/spool/nagios/graphios/host-perfdata",
        "host_perfdata_file_template=DATATYPE::HOSTPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tHOSTPERFDATA::$HOSTPERFDATA$\tHOSTCHECKCOMMAND::$HOSTCHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$\tGRAPHITEPREFIX::$_HOSTGRAPHITEPREFIX$\tGRAPHITEPOSTFIX::$_HOSTGRAPHITEPOSTFIX$",
        "host_perfdata_file_mode=a",
        "host_perfdata_file_processing_interval=15",
        "host_perfdata_file_processing_command=graphios_perf_host",
    ]
    commands = [
        "define command {",
        "    command_name            graphios_perf_host",
        "    command_line            /bin/mv /var/spool/nagios/graphios/host-perfdata /var/spool/nagios/graphios/host-perfdata.$TIMET$",
        "}",
        "define command {",
        "    command_name            graphios_perf_service",
        "    command_line            /bin/mv /var/spool/nagios/graphios/service-perfdata /var/spool/nagios/graphios/service-perfdata.$TIMET$",
        "}"
    ]
    #add the graphios commands
    cstat = os.stat(nag_cfg)
    print("nagios uid: %s gid: %s" % (cstat.st_uid, cstat.st_gid))
    if "cfg_dir" in nconfig:
        command_file = os.path.join(nconfig["cfg_dir"],
                                    'graphios_commands.cfg')
    else:
        command_dir = os.path.join(os.path.dirname(nag_cfg), "objects")
        main_config.append("cfg_dir=%s" % command_dir)
        if not os.path.exists(command_dir):
            os.mkdir(command_dir)
            os.chown(command_dir, cstat.st_uid, cstat.st_gid)
        command_file = os.path.join(command_dir, "graphios_commands.cfg")
    cfile = open(command_file, 'a')
    for line in commands:
        cfile.writelines("%s\n" % line)
    cfile.close()
    os.chown(command_file, cstat.st_uid, cstat.st_gid)
    write_main_config(nconfig, nag_cfg, main_config)


def write_main_config(nconfig, nag_cfg, main_config):
    """
    writes the nagios.cfg
    """
    #now add the main config
    nfile = open(nag_cfg, 'a')
    if (
        "process_performance_data" in nconfig and
        nconfig["process_performance_data"] == "1"
    ):
        print("pre-existing perfdata config detected")
        for line in main_config:
            nfile.writelines("# %s\n" % line)
    else:
        for line in main_config:
            nfile.writelines("%s\n" % line)
    nfile.close()


def _post_install():
    """
    tries to find the nagios.cfg and insert graphios perf commands/cfg
    """
    lookin = ['/etc/nagios/', '/opt/nagios/', '/usr/local/nagios',
              '/usr/nagios']
    nag_cfg = find_nagios_cfg(lookin)
    if nag_cfg is None:
        print("sorry I couldn't find the nagios.cfg file")
        print("NO POST INSTALL COULD BE PERFORMED")
    else:
        print("found nagios.cfg in %s" % nag_cfg)
        nconfig = parse_nagios_cfg(nag_cfg)
        print("parsed nagcfg, nagios_log is at %s" % nconfig['log_file'])
        if backup_file(nag_cfg):
            add_perfdata_config(nconfig, nag_cfg)
        else:
            print("Backup failed, add modify nagios.cfg manually.")


def backup_file(file_name):
    """
    backs up the nagios.cfg, incase we break something.
    """
    my_time = strftime('%d-%m-%y')
    new_file_name = "%s.%s" % (file_name, my_time)
    print("backing up file:%s to %s.%s" % (file_name, new_file_name))
    try:
        copy(file_name, new_file_name)
        return True
    except (FileError, IOError, OSError) as e:
        print("Error:%s copying:%s to:%s" % (e, file_name, new_file_name))
    return False


class my_install(_install):
    """
    installs graphios
    """
    def run(self):
        _install.run(self)
        self.execute(_post_install, [], msg="Running post install task")


setup(name='graphios',
      version='2.0.0b',
      description='Emit Nagios metrics to Graphite, Statsd, and Librato',
      author='Shawn Sterling',
      author_email='shawn@systemtemplar.org',
      url='https://github.com/shawn-sterling/graphios',
      license='GPL v2',
      scripts=['graphios.py'],
      data_files=[(os.path.join('/', 'etc', 'graphios'), ["graphios.cfg"]),
          (os.path.join('/', 'etc', 'graphios', 'init'), ["graphios.conf",
          "graphios.init"])
      ],
      py_modules=['graphios_backends'],
      cmdclass={'install': my_install},
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Operations',
          'Programming Language :: Python :: 2.7',
      ],
      keywords='Nagios metrics graphing visualization',
      )
