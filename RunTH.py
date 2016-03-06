#!/usr/tideway/bin/python
# -*- coding: utf-8 -*-
import os
import sys
import re
import argparse
import subprocess
import shutil

import SetEnvironment
import MyLogger
import SetupDiscovery
import ProcessPatterns
import GenerateTestPy

# Creating arguments handlers
my_parser = argparse.ArgumentParser()
my_parser.add_argument('-f', '--pattern_folder', action='store', type=str,
                       help='Folder of the pattern, \
                             f.e. enter "AdobeCQ" if the pattern is located at "<TKN_MAIN>/tku_patterns/CORE/AdobeCQ"')
my_parser.add_argument('-v', action='count',
                       help='Verbosity of the log messages: "-v"-warn, "-vv"-info, "-vvv"-debug')
my_parser.add_argument('-skip_pattern_upload', action='store_true', help='skips patterns upload on the Discovery '
                                                                         '(useful option in case they are already there'
                                                                         ' and are up-to-date)')
my_parser.add_argument('-V', '--version', action='version', version='TestHarness tool v1.0')
arguments = my_parser.parse_args()

# Checking that pattern folder is provided
pattern_dir_name = arguments.pattern_folder.strip(' "\'') if arguments.pattern_folder else ''
if not pattern_dir_name or re.search(r'\\/', pattern_dir_name):
    print('ERROR   Please enter the pattern folder name')
    subprocess.call(['python', os.path.abspath(__file__), '-h'])
    sys.exit(1)

# Checking that RunTH.py is running under tideway
if 'tideway' not in os.popen('whoami').read():
    print('ERROR   \'RunTH.py\' should run under \'tideway\' user')
    sys.exit(1)

# Setting up the environment variables
environment = SetEnvironment.set_environment_variables(arguments.v)

# Updating the test scripts, copying the tested pattern into isolated environment
SetEnvironment.update_test_directory(arguments.v, environment['tkn_core'], environment['tkn_main'], pattern_dir_name)

# Creating logger
log = MyLogger.create_logger(pattern_dir_name, arguments.v)

####################################
# CHECKING PATTERN FOLDER STRUCTURE:
####################################
# *.tplpre file and 'tests' folder should exist.
# 'TEST' file and:
# either ../tests/dml folder and ../tests/test.py file for verifications tests
# or ../tests/data folder for new tests exist.
# Also setting the th_run_type to either 'verify_tests' or 'new_tests'
th_run_type = SetEnvironment.check_pattern_folder(log, '/usr/tideway/testdir/' + pattern_dir_name)

# Running the tests
os.chdir('/usr/tideway/testdir/' + pattern_dir_name + '/tests')
#########################
# CREATING NEW TEST DATA:
#########################
# generating test.py file and dml files from the test cases located in 'data' folder
# then will run TH against newly created test data
if th_run_type == 'new_tests':
    log.info('#########################################################################################\n'
             '        # CREATING NEW TEST DATA:\n'
             '        # generating test.py file and dml files from the test cases located in \'data\' folder\n'
             '        #########################################################################################')
    log.debug('Setting Discovery in playback, starting the scans')
    SetupDiscovery.playback_mode()

    # Uploading the patterns on the Discovery
    includes, parsed_includes = ProcessPatterns.action(log, environment['tkn_core'], environment['tkn_main'],
                                                       pattern_dir_name, arguments.skip_pattern_upload,
                                                       SetEnvironment.addm_version())

    # Generating 'searchstring' file if it doesn't exist
    if not os.path.exists('/usr/tideway/testdir/' + pattern_dir_name + '/tests/searchstring'):
        SetEnvironment.generate_searchstring(log, '/usr/tideway/testdir/' + pattern_dir_name + '/tests')

    # Pre-configuring test.py file
    GenerateTestPy.pre_format_template(log, pattern_dir_name)

    # Adding patterns to the test.py
    if not arguments.skip_pattern_upload:
        GenerateTestPy.add_patterns(log, pattern_dir_name, includes, parsed_includes)
    else:
        log.warn('Attention! No patterns will be added to \'test.py\' file as it\'s assumed that for the current '
                 'product it had been already generated. If you want them to be added, please re-run the script '
                 'without \'-skip_pattern_upload\' argument')

    # Adding Generic Queries into test.py
    queries_list = GenerateTestPy.add_queries(log, pattern_dir_name)

    # Checking the credential Proxy availability if its needed
    SetupDiscovery.proxy_check(log, '/usr/tideway/testdir/' + pattern_dir_name + '/tests/data')

    for test_case in os.listdir('/usr/tideway/testdir/' + pattern_dir_name + '/tests/data'):
        SetupDiscovery.run_test(log, test_case, pattern_dir_name, queries_list)

    # Adding previous test case data into test.py template
    GenerateTestPy.add_old_test_cases(log, pattern_dir_name)

    # Moving the 'test.py_template' -> 'test.py_old'
    # Moving the 'test.py_template' -> 'test.py'
    log.debug('Moving \'/usr/tideway/testdir/' + pattern_dir_name +
              '/tests/test.py_template\' -> \'/usr/tideway/testdir/' + pattern_dir_name + '/tests/test.py')
    if os.path.exists('/usr/tideway/testdir/' + pattern_dir_name + '/tests/test.py'):
        shutil.move('/usr/tideway/testdir/' + pattern_dir_name + '/tests/test.py',
                    '/usr/tideway/testdir/' + pattern_dir_name + '/tests/test.py_old')
    shutil.move('/usr/tideway/testdir/' + pattern_dir_name + '/tests/test.py_template',
                '/usr/tideway/testdir/' + pattern_dir_name + '/tests/test.py')

    # Moving the 'data' folder to 'data_processed'
    log.debug('Moving \'data\' -> \'data_processed\'')
    shutil.move('/usr/tideway/testdir/' + pattern_dir_name + '/tests/data',
                '/usr/tideway/testdir/' + pattern_dir_name + '/tests/data_processed')
#########################################
# RUNNING TESTS USING EXISTENT TEST DATA:
#########################################
# no new test cases or test.py file will be created. As well as dml data will stay intact.
# Just running the existent tests
else:
    log.info('#########################################################################################\n'
             '        # RUNNING TESTS USING EXISTENT TEST DATA:\n'
             '        # no new test cases or test.py file will be created. As well as dml data will stay intact\n'
             '        #########################################################################################')
    subprocess.call('. /usr/tideway/utils/start_manual_tests && export TKN_CORE=' + environment['tkn_core'] +
                    '&& export TKN_MAIN=' + environment['tkn_main'] +
                    ' && /usr/tideway/bin/python test.py', shell=True)
    # We need to separate the commands because in case of failure the previous command doesn't run 'stop_manual_tests'
    subprocess.call('. /usr/tideway/utils/stop_manual_tests', shell=True)
