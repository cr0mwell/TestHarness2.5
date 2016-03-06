#!/usr/tideway/bin/python
# -*- coding: utf-8 -*-
import logging


def create_logger(pattern_dir_name, level):
    """
        The function creates a logger instance
        which redirects all messages to '<pattern_dir_name>/tests/<pattern_dir_name>.log' file
        and to the standard console output.
        :param pattern_dir_name: str
        :param level: int
        :return: None
    """
    # Mapping of logging levels
    levels = {0: logging.ERROR, 1: logging.WARN, 2: logging.INFO, 3: logging.DEBUG}
    if not level:
        level = 2

    logging.basicConfig(level=levels[level], format='%(asctime)-15s %(levelname)-8s %(message)s',
                        filename='/usr/tideway/testdir/' + pattern_dir_name + '/tests/' + pattern_dir_name + '.log',
                        filemode='a+')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)-7s %(message)s'))
    console_handler.setLevel(levels[level])

    log = logging.getLogger('')
    log.addHandler(console_handler)
    return log
