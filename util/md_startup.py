#!/usr/bin/env python
# Created by Ramesh Sivaraman, Percona LLC.
# This will help us to start Percona Server

import os
import subprocess
import random
import shutil
import time
from util import sanity


class StartPerconaServer:
    def __init__(self, scriptdir, workdir, basedir, node, debug):
        self.scriptdir = scriptdir
        self.workdir = workdir
        self.basedir = basedir
        self.node = node
        self.debug = debug

    def sanity_check(self):
        """ Sanity check method will remove existing
            data directory and forcefully kill
            running MariaDB mysqld processes. This will also check
            the availability of mysqld binary file.
        """
        # kill existing mysqld process
        os.system("ps -ef | grep '" + self.workdir + "/conf/md[0-9].cnf'"
                  " | grep -v grep | awk '{print $2}' | xargs kill -9 >/dev/null 2>&1")
        # Create log directory
        if not os.path.exists(self.workdir + '/log'):
            os.mkdir(self.workdir + '/log')
        # Create configuration directory
        if not os.path.exists(self.workdir + '/conf'):
            os.mkdir(self.workdir + '/conf')
        # Check mysqld file
        if not os.path.isfile(self.basedir + '/bin/mysqld'):
            print(self.basedir + '/bin/mysqld does not exist')
            return 1
        return 0

    # This method will help us to check PS version
    def version_check(self):
        # Database version check
        version_info = os.popen(self.basedir + "/bin/mysqld --version 2>&1 | "
                                               "grep -oe '[0-9]\.[0-9][\.0-9]*' | head -n1").read()
        version = "{:02d}{:02d}{:02d}".format(int(version_info.split('.')[0]),
                                              int(version_info.split('.')[1]),
                                              int(version_info.split('.')[2]))
        return version

    def create_config(self, conf_extra=None):
        """ Method to create cluster configuration file
            based on the node count. To create configuration
            file it will take default values from conf/mdg.cnf.
            For customised configuration please add your values
            in conf/custom.conf.
        """
        version = sanity.version_check(self.basedir)    # Get server version
        port = random.randint(21, 30) * 1004
        port_list = []
        for j in range(1, self.node + 1):
            port_list += [port + (j * 100)]
        # Create PS configuration file
        if not os.path.isfile(self.scriptdir + '/conf/md.cnf'):
            print('Default mdg.cnf is missing in ' + self.scriptdir + '/conf')
            return 1
        else:
            shutil.copy(self.scriptdir + '/conf/custom.cnf', self.workdir + '/conf/custom.cnf')
        # Add custom mysqld options in configuration file
        for i in range(1, self.node + 1):
            shutil.copy(self.scriptdir + '/conf/md.cnf', self.workdir + '/conf/md' + str(i) + '.cnf')
            cnf_name = open(self.workdir + '/conf/md' + str(i) + '.cnf', 'a+')
            cnf_name.write('\nport=' + str(port_list[i - 1]) + '\n')
            if int(version) > int("050700"):
                cnf_name.write('log_error_verbosity=3\n')
            cnf_name.write('socket=/tmp/mdnode' + str(i) + '.sock\n')
            cnf_name.write('server_id=' + str(100 + i) + '\n')
            cnf_name.write('!include ' + self.workdir + '/conf/custom.cnf\n')
            if conf_extra == 'encryption':
                shutil.copy(self.scriptdir + '/conf/encryption.cnf',
                            self.workdir + '/conf/encryption.cnf')
                cnf_name.write('!include ' + self.workdir + '/conf/encryption.cnf\n')
            cnf_name.close()

        return 0

    def add_myextra_configuration(self, config_file):
        """ Adding extra configurations
            based on the testcase
        """
        if not os.path.isfile(config_file):
            print('Custom config ' + config_file + ' is missing')
            return 1
        # Add custom configurations
        config_file = config_file
        cnf_name = open(self.workdir + '/conf/custom.cnf', 'a+')
        cnf_name.write('\n')
        cnf_name.write('!include ' + config_file + '\n')
        cnf_name.close()
        return 0

    def initialize_cluster(self):
        """ Method to initialize the cluster database
            directories. This will initialize the cluster
            using --initialize-insecure option for
            passwordless authentication.
        """
        result = 1  # return value
        for i in range(1, self.node + 1):
            if os.path.exists(self.workdir + '/mdnode' + str(i)):
                os.system('rm -rf ' + self.workdir + '/mdnode' + str(i) + ' >/dev/null 2>&1')
            if not os.path.isfile(self.workdir + '/conf/md' + str(i) + '.cnf'):
                print('Could not find config file /conf/md' + str(i) + '.cnf')
                exit(1)
            version = self.version_check()      # Get server version
            # Initialize data directory
            if int(version) < int("1004"):
                os.mkdir(self.workdir + '/mdnode' + str(i))
                initialize_node = self.basedir + '/scripts/mysql_install_db --no-defaults --force ' \
                    '--basedir=' + self.basedir + ' --datadir=' + \
                    self.workdir + '/mdnode' + str(i) + ' > ' + \
                    self.workdir + '/log/md_startup' + str(i) + '.log 2>&1'
            else:
                initialize_node = self.basedir + '/scripts/mariadb-install-db --no-defaults --force ' \
                    ' --auth-root-authentication-method=normal --basedir=' + self.basedir + \
                    ' --datadir=' + self.workdir + '/mdnode' + str(i) + ' > ' + \
                    self.workdir + '/log/md_startup' + str(i) + '.log 2>&1'
            if self.debug == 'YES':
                print(initialize_node)
            run_query = subprocess.call(initialize_node, shell=True, stderr=subprocess.DEVNULL)
            result = ("{}".format(run_query))
        return int(result)

    def start_server(self, my_extra=None):
        """ Method to start the cluster nodes. This method
            will also check the startup status.
        """
        ping_status = 1     # return value
        if my_extra is None:
            my_extra = ''
        for i in range(1, self.node + 1):
            # Start server
            startup = self.basedir + '/bin/mysqld --defaults-file=' + self.workdir + \
                '/conf/md' + str(i) + '.cnf --datadir=' + self.workdir + '/mdnode' + str(i) + \
                ' --basedir=' + self.basedir + ' ' + my_extra + \
                ' --log-error=' + self.workdir + \
                '/log/mdnode' + str(i) + '.err > ' + self.workdir + \
                '/log/mdnode' + str(i) + '.err 2>&1 &'
            if self.debug == 'YES':
                print(startup)
            run_cmd = subprocess.call(startup, shell=True, stderr=subprocess.DEVNULL)
            result = ("{}".format(run_cmd))
            ping_query = self.basedir + '/bin/mysqladmin --user=root ' \
                                        '--socket=/tmp/mdnode' + str(i) + \
                                        '.sock ping > /dev/null 2>&1'
            for startup_timer in range(120):
                time.sleep(1)
                ping_check = subprocess.call(ping_query, shell=True, stderr=subprocess.DEVNULL)
                ping_status = ("{}".format(ping_check))
                if int(ping_status) == 0:
                    break  # break the loop if mysqld is running

        return int(ping_status)
