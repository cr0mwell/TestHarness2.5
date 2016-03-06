#!/usr/tideway/bin/python
#  -*- coding: utf-8 -*-
import os
import re
import sys
import subprocess
import shutil
import time

import MyLogger
import GenerateTestPy
import SetEnvironment


def playback_mode():
    """
        Sets the Discovery in playback mode and ensures that the scans are started
        :return: None
    """
    subprocess.call('/usr/tideway/bin/tw_scan_control -p System2$ --silent --start', shell=True)
    subprocess.call('/usr/tideway/bin/tw_disco_control -p System2$ --playback 1>/dev/null', shell=True)
    return None


def clean_out_old_data(log):
    """
        Cleaning out '/usr/tideway/var/record' and '/usr/tideway/var/pool' folders
        :return: None
    """
    try:
        shutil.rmtree('/usr/tideway/var/pool')
    except OSError as err:
        log.info('Can\'t remove data from \'/usr/tideway/var/pool\' directory: ' + str(err))
    try:
        shutil.rmtree('/usr/tideway/var/record')
    except OSError as err:
        log.info('Can\'t remove data from \'/usr/tideway/var/record\' directory: ' + str(err))
    try:
        shutil.rmtree('/usr/tideway/var/slaves')
    except OSError as err:
        log.info('Can\'t remove data from \'/usr/tideway/var/slaves\' directory: ' + str(err))
    return None


def remove_hosts(log):
    """
        The function deletes all Host nodes on the Appliance.
        Returns error code depending on the operation success(0) or failure(1).
        :return: bool
    """
    try:
        subprocess.check_output('/usr/tideway/bin/python ' + os.path.dirname(os.path.abspath(__file__)) +
                                '/destroy_hosts.pyc', shell=True)
    except (AttributeError, ImportError) as err:
        log.error('Error while removing Hosts: ' + str(err))
    output = subprocess.Popen(['/usr/tideway/bin/tw_query', '-p', 'System2$', 'Search Host show name'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output.wait()
    hosts = set(output.stdout.readlines())
    if hosts:
        log.warn('Host nodes are still in the repository though should had been removed. Exiting')
        sys.exit(1)


def proxy_check(log, data_dir):
    """
        Checks if any of the TC names starts with 'Windows'. If yes, does a check that
        any credential Proxy is installed. Stops the testing if it's not.
        Takes '/usr/tideway/testdir/<PATTERN_DIR_NAME>/tests/data' path as 'data_dir'
        :param data_dir: str
        :return: None
    """
    log.debug('Checking that Windows proxy is installed')
    for tc_file in os.listdir(data_dir):
        if re.match(r'(?i)Windows', tc_file):
            win_proxy = subprocess.check_output(['/usr/tideway/bin/tw_restricted_winproxy_ctrl', '-p', 'System2$',
                                                 '--list-all-proxies'])
            if not re.search('(?i)credential\s*true\s*true', win_proxy):
                log.error('No Windows proxy is configured. Exiting')
                sys.exit(1)


def extract_ips(log, test_case_dir):
    """
        The function extracts all IP addresses for the cusrrent test case
        Returns a list of IPs
        :param test_case_dir: str
        :return: list
    """
    ip_addresses = []
    log.debug('Obtaining a list of the test case IP addresses')
    for directory in [test_case_dir + '/pool', test_case_dir + '/record']:
        if os.path.exists(directory):
            for dirpath, dirnames, files in os.walk(directory):
                try:
                    ip_address = re.search('\.(\d+(?:\.\d+){3})', dirpath.replace('/', '.'))
                    if ip_address:
                        ip_addresses.append(ip_address.group(1))
                except AttributeError as err:
                    log.error(str(err))

    return ip_addresses


def run_test(log, test_case_file, pattern_dir_name, queries_list):
    """
        The function runs the test case:
        * runs cleanout_old_data()
        * unzips the TC file if its data is archived
        * uploads the TC data to '/usr/tideway/pool' if 'pool_data' file exists or to '/usr/tideway/record' otherwise
        * runs the scan 3 times to ensure all the links are created
        * runs GenerateTestPy.add_test_case()
        * runs SetEnvironment.generate_dml()
        * removes the TC data folder if it was extracted from zip file

        :param test_case_file: str
        :param pattern_dir_name: str
        :return: None
    """

    should_remove_tc_folder = False
    ip_addresses = []
    test_case_name = re.match(r'(?i)([^.]*)(?:\.zip)?$', test_case_file).group(1)
    if not test_case_name:
        log.warn('No TC name was found. Something went wrong. Exiting')
        sys.exit(1)
    log.info('---------------------------------------------------------------\n'
             '        Running the test ' + test_case_name +
             '\n        ---------------------------------------------------------------')
    test_case_dir = '/usr/tideway/testdir/' + pattern_dir_name + '/tests/data/' + test_case_name

    # Cleaning out old data
    log.debug('Cleaning out record data from the previous scan')
    clean_out_old_data(log)

    # Removing the Hosts on Discovery
    log.debug('Destroying Hosts')
    remove_hosts(log)

    # Unziping the archive if the TC is packed
    if os.path.exists(test_case_dir + '.zip'):
        log.debug('Unzipping the test case data')
        should_remove_tc_folder = True
        subprocess.call('unzip -q ' + test_case_dir + '.zip -d /usr/tideway/testdir/' + pattern_dir_name +
                        '/tests/data', shell=True)

    try:
        # Checking if it's record or pool data
        try:
            if os.path.exists(test_case_dir + '/pool'):
                # Copying the pool data onto Discovery
                log.debug('Copying pool data on the Appliance')
                shutil.copytree(test_case_dir + '/pool', '/usr/tideway/var/pool')

            if os.path.exists(test_case_dir + '/record'):
                log.debug('Copying record data on the Appliance')
                shutil.copytree(test_case_dir + '/record', '/usr/tideway/var/record')

            # Obtain a list of the IPs within TC data
            ip_addresses = extract_ips(log, test_case_dir)

            if re.match(r'(?i)Windows', test_case_name) and os.path.exists(test_case_dir + '/slaves'):
                shutil.copytree(test_case_dir + '/slaves', '/usr/tideway/var/slaves')
        except OSError as err:
            log.warn(str(err))

        # Running the test 3 time so all the links could be created
        if ip_addresses:
            log.info('Scanning the IP range: ' + str(ip_addresses))
            for i in [1, 2, 3]:
                subprocess.call('/usr/tideway/bin/tw_scan_control -p System2$ --add ' + ' '.join(ip_addresses) +
                                ' 1>/dev/null', shell=True)
                # Need to wait until the scan is completed before staring other activities
                while True:
                    time.sleep(10)
                    if subprocess.check_output('/usr/tideway/bin/tw_scan_control -p System2$ --list',
                                               shell=True) == 'No scan ranges\n':
                        break
            # Adding the scan results into 'test.py'
            GenerateTestPy.add_test_case(log, pattern_dir_name, ip_addresses, test_case_name, queries_list)

            # Creating dml file of the record data
            SetEnvironment.generate_dml(log, pattern_dir_name, test_case_name)
        else:
            log.warn('No IP addresses were extracted for \'' + test_case_name + '\'. It will be skipped.')

        # Deleting the TC folder
        if should_remove_tc_folder:
            shutil.rmtree(test_case_dir)
    except (IOError, NameError, OSError) as err:
        log.error('Got an exception after unpacking the TC zip folder: ' + str(err))
    return None

if __name__ == '__main__':
    log = MyLogger.create_logger('HelpSystemsStandGuardAnti-Virus', 3)
    run_test(log, 'Unix_active_versioning', 'HelpSystemsStandGuardAnti-Virus',
             ['SEARCH SoftwareInstance WHERE type = "HelpSystems StandGuard Anti-Virus" ORDER BY key SHOW name, type, version, product_version',
              'SEARCH SoftwareInstance WHERE type = "HelpSystems StandGuard Anti-Virus" TRAVERSE InferredElement:Inference:Contributor:DiscoveredCommandResult ORDER BY cmd SHOW cmd',
              'SEARCH SoftwareInstance WHERE type = "HelpSystems StandGuard Anti-Virus" TRAVERSE InferredElement:Inference:Contributor:DiscoveredFile ORDER BY path SHOW path',
              'SEARCH SoftwareInstance WHERE type = "HelpSystems StandGuard Anti-Virus" TRAVERSE ElementWithDetail:Detail:Detail:Detail WHERE type = "Licensing Detail" ORDER BY name SHOW name'])
