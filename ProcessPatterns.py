#!/usr/tideway/bin/python
#  -*- coding: utf-8 -*-
import os
import subprocess
import fnmatch
import glob
import shutil

import MyLogger


def action(log, tkn_core, tkn_main, pattern_dir_name, skip_pattern_upload, tpl_version):
    """
        This function uploads the tested patterns to the Appliance.
        It firstly removes all the patterns from the Appliance.
        Afterward it processes all the patterns from the 'extra_files'.
        Then it processes the main pattern.
        Uploads all the patterns to the Discovery. returns a list of all uploaded files paths
        to include them into test.py latter
        :param tkn_core: str
        :param tkn_main: str
        :param pattern_dir_name: str
        :return: list
    """
    # Creating 'includes' list: it will contain all the patterns paths which will be included into test.py
    includes = list()
    parsed_includes = list()
    tmp_patterns_dir = ''

    # Removing all the patterns from the Appliance
    if not skip_pattern_upload:
        subprocess.call('/usr/tideway/bin/tw_pattern_management --force --remove-all -p System2$ 1>/dev/null',
                        shell=True)
        log.debug('Removed all pattern modules')

        # Creating temporary folder for processed patterns
        tmp_patterns_dir = '/usr/tideway/testdir/' + pattern_dir_name + '/processed_patterns'

        # Generating *.tpl files of *tplpre ones
        log.info('Running the TPLPreprocessor. Please wait')

        if not os.path.exists(tmp_patterns_dir):
            os.mkdir(tmp_patterns_dir)
    else:
        log.info('Leaving previously-uploaded pattern modules on the Appliance. '
                 'Collecting pattern names to include them into test.py file')

    try:
        log.debug('Adding extra_files...')
        # Processing the patterns within 'extra_files'
        f = open('/usr/tideway/testdir/' + pattern_dir_name + '/tests/extra_files', 'r')
        for rel_include_path in f.readlines():
            rel_include_path = rel_include_path.strip('\r\n ')
            if fnmatch.fnmatch(rel_include_path, '*.tplpre'):  # filtering empty lines of the file
                log.debug('Processing ' + os.path.basename(rel_include_path) + ' pattern')
                includes.append('../../../../PerforceCheckout/tkn_main/tku_patterns/CORE/' + rel_include_path)
                if not skip_pattern_upload:
                    subprocess.call('export TKN_CORE=' + tkn_core + ' && /usr/tideway/bin/python ' + tkn_main +
                                    '/buildscripts/TPLPreprocessor.py -f ' + tkn_core + '/' + rel_include_path +
                                    ' -o ' + tmp_patterns_dir + ' 1>/dev/null', shell=True)
                else:  # Adding 'parsed_includes'
                    parsed_includes.append(tpl_version + '/' + os.path.basename(rel_include_path))
    except IOError as err:
        log.error('Patterns preprocessing error: ' + str(err))

    # Processing 'SupportingFiles'
    log.debug('Adding SupportingFiles...')
    for f in glob.glob(tkn_core + '/SupportingFiles/*.tplpre'):
        log.debug('Processing ' + os.path.basename(f) + ' pattern')
        includes.append('../../../../PerforceCheckout/tkn_main/tku_patterns/CORE/SupportingFiles/' +
                        os.path.basename(f))
        if not skip_pattern_upload:
            subprocess.call('export TKN_CORE=' + tkn_core + ' && /usr/tideway/bin/python ' + tkn_main +
                            '/buildscripts/TPLPreprocessor.py -f ' + f + ' -o ' + tmp_patterns_dir + ' 1>/dev/null',
                            shell=True)
        else:  # Adding 'parsed_includes'
            parsed_includes.append(tpl_version + '/' + os.path.basename(f))

    # Processing files within main pattern directory
    log.debug('Adding files within the pattern directory...')
    for f in glob.glob('/usr/tideway/testdir/' + pattern_dir_name + '/*.tplpre'):
        log.debug('Processing ' + os.path.basename(f) + ' pattern')
        includes.append('../' + os.path.basename(f))
        if not skip_pattern_upload:
            subprocess.call('export TKN_CORE=' + tkn_core + ' && /usr/tideway/bin/python ' + tkn_main +
                            '/buildscripts/TPLPreprocessor.py -f ' + f + ' -o ' + tmp_patterns_dir + ' 1>/dev/null',
                            shell=True)
        else:  # Adding 'parsed_includes'
            parsed_includes.append(tpl_version + '/' + os.path.basename(f))

    if not skip_pattern_upload:
        # Uploading the patterns to the Discovery
        try:
            log.info('About to upload the following pattern modules: ' +
                     str(os.listdir('/usr/tideway/testdir/' + pattern_dir_name + '/processed_patterns/' + tpl_version)))
            for f in glob.glob('/usr/tideway/testdir/' + pattern_dir_name + '/processed_patterns/' + tpl_version +
                               '/*.tpl'):
                parsed_includes.append(tpl_version + '/' + os.path.basename(f))
                subprocess.call('/usr/tideway/bin/tw_pattern_management -p System2$ --install ' + f + '  1>/dev/null',
                                shell=True)
        except IOError as err:
            log.error('TPLPreprocessor error: ' + str(err))

        # Activating uploaded patterns
        log.debug('Activating patterns')
        subprocess.call('/usr/tideway/bin/tw_pattern_management -p System2$ --activate-all', shell=True)

        # Removig temporary patterns folder
        shutil.rmtree(tmp_patterns_dir)
    else:
        # If the new patterns upload was suppressed then parsed_includes contain *.tplpre names instead of *.tpl.
        # Normalizing...
        parsed_includes = map(lambda x: x.replace('tplpre', 'tpl'), parsed_includes)

    return includes, parsed_includes

if __name__ == '__main__':
    log = MyLogger.create_logger('WebsphereAppServer', 3)
    includes, parsed_includes = action(log, '/usr/PerforceCheckout/tkn_main/tku_patterns/CORE',
                                       '/usr/PerforceCheckout/tkn_main', 'WebsphereAppServer', True, 'tpl110')
    print includes
    print parsed_includes