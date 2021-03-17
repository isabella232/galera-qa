import os
import configparser
from util import utility


# Reading initial configuration
config = configparser.ConfigParser()
script_dir = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.normpath(os.path.join(script_dir, '../'))
config.read(parent_dir + '/config.ini')
workdir = config['config']['workdir']
basedir = config['config']['basedir']
user = config['config']['user']


class RQGDataGen:
    def __init__(self, basedir, workdir, user, debug):
        self.basedir = basedir
        self.workdir = workdir
        self.user = user
        self.debug = debug
        self.utility_cmd = utility.Utility(debug)
        self.version = self.utility_cmd.version_check(self.basedir)

    def initiate_rqg(self, module, db, socket):
        """ Method to initiate RQD data load against
            MariaDB Galera Cluster.
        """
        # Get RQG module
        module = parent_dir + '/randgen/conf/' + module
        master_port = self.basedir + "/bin/mysql --user=root --socket=" + socket + \
            ' -Bse"select @@port" 2>&1'
        port = os.popen(master_port).read().rstrip()
        # Create schema for RQG run
        create_db = self.basedir + "/bin/mysql --user=root --socket=" + socket + \
            ' -Bse"drop database if exists ' + db + \
            ';create database ' + db + ';" 2>&1'
        os.system(create_db)
        if int(self.version) > int("050700"):
            create_user = self.basedir + "/bin/mysql --user=root --socket=" + socket + \
                ' -Bse"create user rqg_test@\'%\' identified with mysql_native_password by \'\'; ' \
                'grant all on *.* to rqg_test@\'%\';" 2>&1'
            os.system(create_user)
        # Checking RQG module
        os.chdir(parent_dir + '/randgen')
        if not os.path.exists(module):
            print(module + ' does not exist in RQG')
            exit(1)
        # Run RQG
        for file in os.listdir(module):
            if file.endswith(".zz"):
                rqg_command = "perl " + parent_dir + "/randgen/gendata.pl " \
                              "--dsn=dbi:mysql:host=127.0.0.1:port=" \
                              + port + ":user=" + self.user + ":database=" + db + " --spec=" + \
                              module + '/' + file + " > " + \
                              self.workdir + "/log/rqg_run.log 2>&1"
                result = os.system(rqg_command)
                self.utility_cmd.check_testcase(result, "RQG data load (DB: " + db + ")")

    def galera_dataload(self, socket):
        """
            RQG data load for MariaDB Galera Cluster
        """
        if int(self.version) < int("1004"):
            rqg_config = ['galera', 'transactions', 'optimizer', 'mariadb', 'runtime', 'temporal']
        else:
            rqg_config = ['galera', 'transactions', 'partitioning', 'optimizer', 'mariadb', 'runtime', 'temporal']
        for config in rqg_config:
            self.initiate_rqg(config, 'db_' + config, socket)
