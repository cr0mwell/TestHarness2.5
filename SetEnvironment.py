#!/usr/tideway/bin/python
# -*- coding: utf-8 -*-
import os
import sys
import re
import shutil
import glob
import subprocess

import MyLogger


def set_environment_variables(loglevel):
    """
        This function is setting the environment before running TH tests:
        * TKN_CORE
        * TKN_MAIN
        * PYTHONPATH
        Takes 'loglevel' integer for informational messages output.
        Returns a dict containing  environment variables
        :param loglevel: int
    """

    environment = dict()
    if loglevel >= 2:
        print('INFO    Setting the environment before running the tests')
    if 'TKN_CORE' in os.environ:
        environment['tkn_core'] = os.environ['TKN_CORE']
    elif os.path.exists('/usr/PerforceCheckout/tkn_main/tku_patterns/CORE'):
        environment['tkn_core'] = os.environ['TKN_CORE'] = '/usr/PerforceCheckout/tkn_main/tku_patterns/CORE'
    else:
        print('ERROR   TKN_CORE variable is not set. \'/usr/PerforceCheckout/tkn_main/tku_patterns/CORE\''
              'doesn\'t exist as well. Exiting')
        sys.exit(1)
    environment['tkn_main'] = os.environ['TKN_MAIN'] = re.search(r'^(/.*)/tku_patterns',
                                                                 os.environ['TKN_CORE']).group(1)
    environment['pythonpath'] = os.environ['PYTHONPATH'] = os.environ['PYTHONPATH'] + ':' +\
        environment['tkn_main'] + '/python'
    if loglevel >= 2:
        print('INFO    The following environment is set: TKN_CORE={0[tkn_core]},'
              'TKN_MAIN={0[tkn_main]}, PYTHONPATH={0[pythonpath]}'.format(environment))

    return environment


def addm_version():
    """
        Runs 'tw_scan_control --version' command to get the Discovery version.
        Returns Discovery TPL version obtained from Discovery version -> TPL version mapping
        :return: str
    """
    tpl_version_mapping = {'10.0': 'tpl18', '10.1': 'tpl19', '10.2': 'tpl110', '11.0': 'tpl111'}
    tpl_version = tpl_version_mapping[re.search(r'Version: (\d\d\.\d)',
                                      subprocess.check_output('/usr/tideway/bin/tw_scan_control --version',
                                                              shell=True)).group(1)]
    return tpl_version


def update_test_directory(loglevel, tkn_core, tkn_main, pattern_dir_name):
    """
        The function takes 'tkn_core' and 'tkn_main' environment variables.
        Also it takes 'loglevel' integer for informational messages output.
        Removes 'testdir', 'utils' and 'testutils' folders from the test environment.
        Re-creates 'testdir' folder, copies 'utils' and 'testutils' folders from the CORE
        to respectively '/usr/tideway/utils' and '/usr/tideway/python/testutils' locations
        before running the tests.
        Copies the tested pattern folder content into '/usr/tideway/testdir' folder
        :param loglevel: int
        :param tkn_core: str
        :param tkn_main: str
        :param pattern_dir_name: str
        :return: None
    """

    # Cleaning out obsolete files
    if loglevel > 2:
        print('DEBUG   Cleaning out \'testdir\' and local repository of TH python scripts')
    shutil.rmtree('/usr/tideway/testdir', ignore_errors=True)
    shutil.rmtree('/usr/tideway/python/testutils', ignore_errors=True)
    shutil.rmtree('/usr/tideway/utils', ignore_errors=True)
    # Copying new files from the P4
    # Will not check for any errors. 'check_pattern_folder()' will do it instead
    if loglevel > 2:
        print('DEBUG   Copying \'testdir\' and TH python scripts from P4 to the local repository')
    try:
        shutil.copytree(tkn_core + '/' + pattern_dir_name, '/usr/tideway/testdir/' + pattern_dir_name)
    except OSError:
        print('ERROR   Folder \'' + tkn_core + '/' + pattern_dir_name + '\' doesn\'t exist. Exiting')
        sys.exit(1)
    shutil.copytree(tkn_main + '/../rel/branches/zythum/r10_2_0_x/code/utils', '/usr/tideway/utils')
    shutil.copytree(tkn_main + '/../rel/branches/zythum/r10_2_0_x/code/python/testutils',
                    '/usr/tideway/python/testutils')
    if not os.path.exists('/usr/tideway/testdir/' + pattern_dir_name + '/tests/TEST'):
        shutil.copy(tkn_main + '/buildscripts/TestHarness_2.5/TEST', '/usr/tideway/testdir/' + pattern_dir_name + '/tests')
    if loglevel > 2:
        print('DEBUG   Setting permissions')
    subprocess.call('sudo chmod -R 777 /usr/tideway/testdir /usr/tideway/python/testutils /usr/tideway/utils '
                    '/usr/tideway/testdir/' + pattern_dir_name + '/tests/TEST', shell=True)
    return None


def check_pattern_folder(log, pattern_dir):
    """
        The function checks that the provided pattern folder contains a valid content:
        * pattern file <pattern_dir>/*.tplpre exists
        * 'tests' folder exists under <pattern_dir_name>
        * 'tests' folder contains either:
            - 'data' folder - for new tests;
            - 'dml' folder, 'test.py' file - for existent tests;

        Returns 'th_run_type' string with 'new_tests' or 'verify_tests' string.
        'pattern_dir' = '/usr/tideway/testdir/<PATTERN_DIR_NAME>'
        :param pattern_dir: str
        :return: str
    """

    th_run_type = None
    log.info('Checking the pattern folder structure')
    if not (os.path.exists(pattern_dir + '/tests') and len(glob.glob(pattern_dir + '/*.tplpre')) > 0):
        log.error('Can not proceed as either \'<PATTERN_DIR>/tests\' folder or'
                  ' \'<PATTERN_DIR>/*.tplpre\' file were not found. Exiting')
        sys.exit(1)
    if os.path.exists(pattern_dir + '/tests/data') and (os.path.exists(pattern_dir + '/tests/searchstring') or
                                                        os.path.exists(pattern_dir + '/tests/test.py')):
        th_run_type = 'new_tests'
    elif os.path.exists(pattern_dir + '/tests/dml') and os.path.exists(pattern_dir + '/tests/test.py'):
        th_run_type = 'verify_tests'
        # Updating test.py paths according to virtual testing environment
        test_py = open(pattern_dir + '/tests/test.py', 'r')
        test_py_content = test_py.read(os.path.getsize(pattern_dir + '/tests/test.py'))
        # Checking if test.py file was created externally. Then the substitution should happen
        if not re.search(r'self.preProcessTpl\(\[\'../../../../PerforceCheckout/', test_py_content):
            try:
                original_preprocess_paths = re.search(r'self.preProcessTpl\(\[([^\]]+)', test_py_content).group(1)
                updated_preprocess_paths = re.sub(r'\.\./\.\.',
                                                  '../../../../PerforceCheckout/tkn_main/tku_patterns/CORE',
                                                  original_preprocess_paths)
                original_upload_paths = re.search(r'self.loadTplFiles\(([^\)]+)', test_py_content).group(1)
                tpl_version = addm_version()
                test_py = open(pattern_dir + '/tests/test.py', 'w')
                test_py_content = re.sub(r'self\.assertTrue\(os\.path\.isdir\(\'tpl\d+',
                                         'self.assertTrue(os.path.isdir(\'' + tpl_version, test_py_content)
                updated_upload_paths = re.sub(r'tpl\d+', tpl_version, original_upload_paths)
                test_py_content = re.sub(original_preprocess_paths, updated_preprocess_paths, test_py_content)
                test_py_content = re.sub(original_upload_paths, updated_upload_paths, test_py_content)
                test_py.write(test_py_content)
            except (IOError, TypeError) as err:
                log.warn('Wasn\'t able to update pattern paths in \'test.py\' for playback tests: ' + str(err))
    if not th_run_type:
        log.error('Neither \'dml\' folder + test.py file nor \'data\' folder were found. '
                  'Please check your configuration and re-run the script')
        sys.exit(1)
    return th_run_type


def generate_searchstring(log, tests_dir):
    """
        The function generates '.../tests/searchstring' file from 'test.py'
        'tests_dir' = '/usr/tideway/testdir/<PATTERN_DIR_NAME>/tests'
        :param tests_dir: str
        :return: None
    """

    log.debug('Generating \'searchstring\' file out of \'test.py\'')
    try:
        testpy = open(tests_dir + '/test.py', 'r')
        searchstring = open(tests_dir + '/searchstring', 'w+')
        queries = re.findall(r'_QUERY\d = \'\'\'([^\']*)', testpy.read(os.path.getsize(tests_dir + '/test.py')))
        [searchstring.write(query + '\r\n') for query in queries]
    except IOError as err:
        log.error('Error when extracting queries from test.py file:' + str(err))
    except TypeError as err:
        log.error('Error when extracting queries from test.py file:' + str(err))
    return None


def generate_dml(log, pattern_dir_name, test_case_name):
    """
        The function generates '<test_case_name>.dml' file
        :param pattern_dir_name: str
        :param test_case_name: str
        :return: None
    """

    log.info('Generating dml file for \'' + test_case_name + '\' test case')
    if not os.path.exists('/usr/tideway/testdir/' + pattern_dir_name + '/tests/dml'):
        os.mkdir('/usr/tideway/testdir/' + pattern_dir_name + '/tests/dml')
    subprocess.call('/usr/tideway/sbin/tw_dml_extract -p System2$ -o /usr/tideway/testdir/' + pattern_dir_name +
                    '/tests/dml/' + test_case_name + '.dml "search Host" 1>/dev/null', shell=True)
    return None

if __name__ == '__main__':
    log = MyLogger.create_logger('WebSphereAppServer', 3)
    # print check_pattern_folder(log, '/usr/tideway/testdir/WebSphereAppServer')
    update_test_directory(3, '/usr/PerforceCheckout/tkn_main/tku_patterns/CORE', '/usr/PerforceCheckout/tkn_main', '')
