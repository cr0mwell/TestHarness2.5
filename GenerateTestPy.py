#!/usr/tideway/bin/python
# -*- coding: utf-8 -*-
import os
import shutil
import re
from subprocess import call
from xml.etree import ElementTree

import MyLogger


def file_altering(log, pattern_dir_name, regex, substitution, file_path=None):
    """
        Current function contains the common code of all other functions within this module.
        It opens the file and substitutes the lines matched by the regex.
        :param pattern_dir_name: str
        :param substitution: str
        :param regex: str
        :return: None
    """
    if not file_path:
        file_path = '/usr/tideway/testdir/' + pattern_dir_name + '/tests/test.py_template'
    try:
        template_file = open(file_path, 'r')
        template_file_content = template_file.read(os.path.getsize(file_path))
        template_file = open(file_path, 'w')
        # template_file.write(substitution)
        template_file.write(re.sub(regex, substitution, template_file_content))
    except IOError as err:
        log.error('\'test.py\' update error: ' + str(err))
    except TypeError as err:
        log.error('Invalid \'test.py\' file content for substitution: ' + str(err))
    return None


def pre_format_template(log, pattern_dir_name):
    """
        The function copies from repository and
        does initial pre-formatting of the test.py_template file
        :return: None
    """

    log.debug('Running pre-configuration script for \'test.py\' file')
    shutil.copy(os.path.dirname(os.path.abspath(__file__)) + '/test.py_template', '/usr/tideway/testdir/' +
                pattern_dir_name + '/tests')
    call('chmod 777 /usr/tideway/testdir/' + pattern_dir_name + '/tests/test.py_template', shell=True)
    # unittest doesn't accept '-' character within the Class name. Normalizing the pattern name before the substitution
    pattern_dir_name_normalized = pattern_dir_name.replace('-', '')
    file_altering(log, pattern_dir_name, r'<pattern_dir_name>', pattern_dir_name_normalized, '/usr/tideway/testdir/' +
                  pattern_dir_name + '/tests/test.py_template')
    return None


def add_patterns(log, pattern_dir_name, includes, includes_parsed):
    """
        The function adds the paths of the included patterns(tplpre)
        and the paths of the parsed included patterns(tpl) into test.py script
        :param includes: list
        :param includes_parsed: list
        :return: None
    """
    log.debug('Adding included pattern paths into \'test.py\' file')
    file_altering(log, pattern_dir_name, r'<includes>', str(includes))
    file_altering(log, pattern_dir_name, r'<parsed_includes>', str(includes_parsed).strip('[]'))
    return None


def add_queries(log, pattern_dir_name):
    """
        The function reads the 'searchstring' file and adds query records into test.py
        :param pattern_dir_name: str
        :return: list
    """
    queries_list = list()
    formatted_query_list = list()
    log.debug('Adding Generic Queries block into \'test.py\' file')
    try:
        searchstring_file = open('/usr/tideway/testdir/' + pattern_dir_name + '/tests/searchstring', 'r')
        for query in searchstring_file.readlines():
            queries_list.append(query.strip('\r\n'))
    except IOError as err:
        log.error('Error when working with \'searchstring\' file: ' + str(err))
    try:
        [formatted_query_list.append('    SEARCH_QUERY' + str(index) + ' = \'\'\'' + query + '\'\'\'\r\n') for
         index, query in enumerate(queries_list, 1)]
    except TypeError as err:
        log.error('Error while parsing the queries obtained from \'searchstring\' file: ' + str(err))
    file_altering(log, pattern_dir_name, r'<queries_block>', ''.join(formatted_query_list))
    return queries_list


def parse_result_row(log, result_row):
    """
        Takes the ElementTree object, parses it and returns a list
        containing values of the respective type.
        :param result_row: Element
        :return: list
    """
    result = list()
    try:
        for element in result_row:
            if element.tag == 'string':
                if element.text:
                    # Escaping special characters
                    result.append(''.join(['\\' + x if x in ['\\'] else x for x in str(element.text)]))
                else:
                    result.append('')
            elif element.tag == 'int':
                result.append(int(element.text))
            elif element.tag == 'bool':
                result.append(bool(element.text))
            elif element.tag == 'list':
                result.append(parse_result_row(log, element))
    except NameError as err:
        log.error('Generic query file parsing error. Possibly there is no such an Element: ' + str(err))
    except TypeError as err:
        log.error('Generic query file parsing error. Can\'t convert the test into provided type: ' + str(err))

    return result


def add_test_case(log, pattern_dir_name, ips_list, test_case_name, generic_queries):
    """
        The function models test case function of the provided IP address list, TC name and
        of the results of the provided generic queries.
        Then it adds the function into test.py file
        :param pattern_dir_name: str
        :param ips_list: list
        :param test_case_name: str
        :param generic_queries: list
        :return: None
    """
    test_case_function = list()
    log.info('Adding expected data for ' + test_case_name + ' into \'test.py\' file')
    xmlfile = '/usr/tideway/testdir/' + pattern_dir_name + '/tests/tmp.xml'
    # Pre-formatting test case function
    test_case_function.append('    def test1_' + test_case_name + '(self):\n')
    test_case_function.append('        self.scan_dml(' + str(ips_list) + ', \'' + test_case_name + '\')\r\n')
    test_case_function.append('        self.scan_dml(' + str(ips_list) + ', \'' + test_case_name + '\')\r\n')
    # Adding expected data for each Generic Query
    for index, generic_query in enumerate(generic_queries, 1):
        results = list()
        query_result = '        self.verify_model(self.SEARCH_QUERY' + str(index) + ', '
        # Running tw_query command on the Appliance
        cmd_string = '/usr/tideway/bin/tw_query -p System2$ --xml --file=' + xmlfile + ' \'' + generic_query + '\''
        log.debug('Running command: ' + cmd_string)
        call(cmd_string, shell=True)
        # Parsing tmp.xml file and updating test_case_function with the results
        if os.path.exists(xmlfile):
            # Replacing empty field results(<void/>) by empty string(<string>''</string>)
            file_altering(log, pattern_dir_name, r'<void/>', '<string></string>', file_path=xmlfile)
            xmlroot = ElementTree.parse(xmlfile).getroot()[0]  # Obtaining the document tree
            attributes = [attribute.text for attribute in xmlroot[0][:]]  # Creating list of returned attributes
            for result_row in xmlroot[1:]:  # Creating a dict of <attribute>:<value> for every <row> tree
                try:
                    resulting_dict = dict(zip(attributes, parse_result_row(log, result_row)))
                    [resulting_dict.pop(i) for i,j in resulting_dict.items() if not j]  # Removing empty members
                    results.append(resulting_dict)
                except (TypeError, NameError) as err:
                    log.error('Invalid data format from \'tmp.xml\' file: ' + str(err))
            # Removing 'tmp.xml' file
            os.remove(xmlfile)
        try:
            query_result += str(results) + ', sort_key=\'' +\
                re.search(r'(?i)order by (\w+)', generic_query).group(1).lower() + '\')\r\n'
        except AttributeError as err:
            log.error('No match found for \'order by\' string in Generic Query: ' + str(err))
        test_case_function.append(query_result)

    # Adding a testcase into test.py file
    file_altering(log, pattern_dir_name, r'# <test_cases_block>', ''.join(test_case_function) + '# <test_cases_block>')
    return None


def add_old_test_cases(log, pattern_dir_name):
    """
        Adds old test cases from existent test.py file into test.py_template one.
        :param pattern_dir_name: str
        :return: None
    """
    log.debug('Adding old test case functions to \'test.py\'')
    try:
        file_path = '/usr/tideway/testdir/' + pattern_dir_name + '/tests/test.py'
        try:
            test_py = open(file_path, 'r')
            test_py_content = test_py.read(os.path.getsize(file_path))
            try:
                if re.search(r'# <test_cases_block>', test_py_content):
                    old_test_cases = re.search(r'(?s)(    def test.*)\r?\n# <test_cases_block>',
                                               test_py_content).group(1).replace('\\', '\\\\')
                else:
                    old_test_cases = re.search(r'(?s)(    def test.*)if __name__ == "__main__":',
                                               test_py_content).group(1).replace('\\', '\\\\')
                old_test_cases = old_test_cases.rstrip('\r\n ')

                # Updating QUERY names according to the test.py_template file
                old_test_cases = re.sub(r'self\.[^_]+_QUERY', 'self.SEARCH_QUERY', old_test_cases)
                if old_test_cases:
                    file_altering(log, pattern_dir_name, r'# <test_cases_block>', old_test_cases +
                                  '\r\n# <test_cases_block>')
            except AttributeError as err:
                log.error('No match found for test case functions ending in \'test.py\' file: ' + str(err))
        except IOError as err:
            log.error('No \'test.py\' was found to obtain existent test case functions from it: ' + str(err))
    except EnvironmentError as err:
        log.error(str(err))
    return None

if __name__ == '__main__':
    log = MyLogger.create_logger('WebsphereAppServer', 3)
    # f = open('/usr/tideway/testdir/WebSphereAppServer/tests/searchstring', 'r')
    # add_test_case(log, 'WebSphereAppServer', ['172.22.90.121', '172.22.90.140'], 'Windows_additional_tc',
    #              ['search SoftwareInstance where type has substring "IBM WebSphere Application Server"  order by name  show name,type, count, version, product_version, edition, service_pack,  install_root, server_name, cell_name, node_name, jmx_enabled, jmx_port, profile_dir'])
    pre_format_template(log, 'WebsphereAppServer')
    add_old_test_cases(log, 'WebsphereAppServer')
