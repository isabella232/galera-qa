#!/usr/bin/env python3
import os
import sys
import argparse
import itertools
cwd = os.path.dirname(os.path.realpath(__file__))
parent_dir = os.path.normpath(os.path.join(cwd, '../../'))
sys.path.insert(0, parent_dir)
from config import *
from util import sysbench_run
from util import utility
from util import table_checksum
from util import db_connection
from util import galera_startup

# Read argument
parser = argparse.ArgumentParser(prog='Galera thread pool test', usage='%(prog)s [options]')
parser.add_argument('-e', '--encryption-run', action='store_true',
                    help='This option will enable encryption options')
parser.add_argument('-d', '--debug', action='store_true',
                    help='This option will enable debug logging')
args = parser.parse_args()
if args.encryption_run is True:
    encryption = 'YES'
else:
    encryption = 'NO'
if args.debug is True:
    debug = 'YES'
else:
    debug = 'NO'

utility_cmd = utility.Utility(debug)
utility_cmd.check_python_version()


class ThreadPooling:
    def start_server(self, node):
        my_extra = "--innodb_buffer_pool_size=2G --innodb_log_file_size=1G"
        utility_cmd.start_galera(parent_dir, WORKDIR, BASEDIR, node,
                                 WORKDIR + '/node1/mysql.sock', USER, encryption, my_extra)

    def sysbench_run(self, socket, db, port):
        # Sysbench data load
        sysbench = sysbench_run.SysbenchRun(BASEDIR, WORKDIR, socket, debug)
        result = sysbench.sanity_check(db)
        utility_cmd.check_testcase(result, "Sysbench run sanity check")
        result = sysbench.sysbench_load(db, 50, 50, SYSBENCH_NORMAL_TABLE_SIZE)
        utility_cmd.check_testcase(result, "Sysbench data load (threads : " + str(SYSBENCH_THREADS) + ")")
        # Sysbench OLTP read write run
        query = "sysbench /usr/share/sysbench/oltp_read_write.lua" \
                " --table-size=" + str(SYSBENCH_NORMAL_TABLE_SIZE) + \
                " --tables=" + str(50) + \
                " --threads=" + str(50) + \
                " --mysql-db=test --mysql-user=" + SYSBENCH_USER + \
                " --mysql-password=" + SYSBENCH_PASS + \
                " --db-driver=mysql --mysql-host=127.0.0.1 --mysql-port=" + str(port) + \
                "  --time=300 --db-ps-mode=disable run > " + WORKDIR + "/log/sysbench_read_write.log"
        if debug == 'YES':
            print(query)
        query_status = os.system(query)
        if int(query_status) != 0:
            print("ERROR!: sysbench read write run is failed")
            utility_cmd.check_testcase(result, "Sysbench read write run")
        utility_cmd.check_testcase(0, "Sysbench read write run")

    def thread_pooling_qa(self, socket, db):
        # Thread Pooling QA
        thread_handling_option = ['pool-of-threads', 'one-thread-per-connection']
        thread_pool_size = [2, 4, 8]
        thread_pool_max_threads = [2, 4, 8]
        for tp_option, tp_size, tp_max_thread in \
                itertools.product(thread_handling_option, thread_pool_size, thread_pool_max_threads):
            my_extra = "--thread_handling=" + tp_option + " --thread_pool_size=" + str(tp_size) + \
                       " --thread_pool_max_threads=" + str(tp_max_thread)
            # Start Galera cluster for encryption test
            utility_cmd.check_testcase(0, "Thread pooling options : " + my_extra)
            dbconnection_check = db_connection.DbConnection(USER, WORKDIR + '/node1/mysql.sock')
            server_startup = galera_startup.StartCluster(parent_dir, WORKDIR, BASEDIR, int(NODE), debug)
            result = server_startup.sanity_check()
            utility_cmd.check_testcase(result, "Startup sanity check")
            result = server_startup.create_config('none')
            utility_cmd.check_testcase(result, "Configuration file creation")
            result = server_startup.initialize_cluster()
            utility_cmd.check_testcase(result, "Initializing cluster")
            for i in range(1, int(NODE) + 1):
                n_name = open(WORKDIR + '/conf/node' + str(i) + '.cnf', 'a+')
                n_name.write('admin_address=127.0.0.1\n')
                n_name.write('admin_port=' + str(33062 + i) + '\n')
                n_name.close()

            result = server_startup.start_cluster(my_extra)
            utility_cmd.check_testcase(result, "Cluster startup")
            result = dbconnection_check.connection_check()
            utility_cmd.check_testcase(result, "Database connection")
            self.sysbench_run(WORKDIR + '/node1/mysql.sock', 'test', 33063)
            utility_cmd.stop_galera(WORKDIR, BASEDIR, NODE)


print("--------------------------------")
print("\nGalera Thread Pooling test")
print("--------------------------------")
thread_pooling = ThreadPooling()
thread_pooling.thread_pooling_qa(WORKDIR + '/node1/mysql.sock', 'test')

