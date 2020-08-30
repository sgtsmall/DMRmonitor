#!/usr/bin/env python
#
###############################################################################
#   Copyright (C) 2016-2018 Cortney T. Buffington, N0MJS <n0mjs@me.com>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software Foundation,
#   Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
###############################################################################

'''
This module generates the configuration data structure for dmrmonitor.py and
assoicated programs that use it. It has been seaparated into a different
module so as to keep dmrmonitor.py easier to navigate. This file only needs
updated if the items in the main configuraiton file (usually dmrmonitor.cfg)
change.
'''

import configparser
import sys


from socket import gethostbyname

# Does anybody read this stuff? There's a PEP somewhere that says I should do this.
__author__ = 'Cortney T. Buffington, N0MJS'
__copyright__ = 'Copyright (c) 2016-2018 Cortney T. Buffington, N0MJS and the K0USY Group'
__credits__ = 'Colin Durbridge, G4EML, Steve Zingman, N4IRS; Mike Zingman, N4IRR; Jonathan Naylor, G4KLX; Hans Barthen, DL5DI; Torsten Shultze, DG1HT'
__license__ = 'GNU GPLv3'
__maintainer__ = 'Cort Buffington, N0MJS'
__email__ = 'n0mjs@me.com'


def build_config(_config_file):
    config = configparser.ConfigParser()

    if not config.read(_config_file):
        sys.exit('Configuration file \'' + _config_file +
                 '\' is not a valid configuration file! Exiting...')

    CONFIG = {}
    CONFIG['GLOBAL'] = {}
    CONFIG['WEBSITE'] = {}
    CONFIG['LOGGER'] = {}
    CONFIG['ALIASES'] = {}

    try:
        for section in config.sections():
            if section == 'GLOBAL':
                CONFIG['GLOBAL'].update({
                    'REPORT_NAME': config.get(section, 'REPORT_NAME'),
                    'CONFIG_INC': config.get(section, 'CONFIG_INC'),
                    'BRIDGES_INC': config.get(section, 'BRIDGES_INC'),
                    'DMRLINK_IP': config.get(section, 'DMRLINK_IP'),
                    'DMRLINK_PORT': config.getint(section, 'DMRLINK_PORT'),
                    'FREQUENCY': config.getint(section, 'FREQUENCY')
                })

            elif section == 'WEBSITE':
                CONFIG['WEBSITE'].update({
                    'PATH': config.get(section, 'PATH'),
                    'WEB_SERVER_PORT': config.getint(section, 'WEB_SERVER_PORT'),
                    'WEBSERVICE_PORT': config.getint(section, 'WEBSERVICE_PORT'),
                    'CLIENT_TIMEOUT': config.getint(section, 'CLIENT_TIMEOUT'),
                    'WEB_AUTH': config.get(section, 'WEB_AUTH'),
                    'WEB_USER': config.get(section, 'WEB_USER'),
                    'WEB_PASS': config.get(section, 'WEB_PASS'),
                    'WEB_TZ': config.get(section, 'WEB_TZ')
                })

            elif section == 'LOGGER':
                CONFIG['LOGGER'].update({
                    'LOG_PATH': config.get(section, 'LOG_PATH'),
                    'LOG_FILE': config.get(section, 'LOG_FILE'),
                    'LOG_HANDLERS': config.get(section, 'LOG_HANDLERS'),
                    'LOG_LEVEL': config.get(section, 'LOG_LEVEL'),
                    'LOG_NAME': config.get(section, 'LOG_NAME'),
                    'LOG_LASTHEARD': config.get(section, 'LOG_LASTHEARD')
                })
                if not CONFIG['LOGGER']['LOG_FILE']:
                    CONFIG['LOGGER']['LOG_FILE'] = '/dev/null'

            elif section == 'ALIASES':
                CONFIG['ALIASES'].update({
                    'TRY_DOWNLOAD': config.getboolean(section, 'TRY_DOWNLOAD'),
                    'PATH': config.get(section, 'PATH'),
                    'PEER_FILE': config.get(section, 'PEER_FILE'),
                    'SUBSCRIBER_FILE': config.get(section, 'SUBSCRIBER_FILE'),
                    'LOCAL_PEER_FILE': config.get(section, 'LOCAL_PEER_FILE'),
                    'LOCAL_SUB_FILE': config.get(section, 'LOCAL_SUB_FILE'),
                    'TGID_FILE': config.get(section, 'TGID_FILE'),
                    'PEER_URL': config.get(section, 'PEER_URL'),
                    'SUBSCRIBER_URL': config.get(section, 'SUBSCRIBER_URL'),
                    'STALE_TIME': config.getint(section, 'STALE_DAYS') * 86400,
                })

    except configparser.Error as err:
        sys.exit('Error processing configuration file -- {}'.format(err))

    return CONFIG


# Used to run this file direclty and print the config,
# which might be useful for debugging
if __name__ == '__main__':
    import sys
    import os
    import argparse
    from pprint import pprint
    from dmr_utils3.utils import int_id

    # Change the current directory to the location of the application
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))

    # CLI argument parser - handles picking up the config file from the command line, and sending a "help" message
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='store', dest='CONFIG_FILE',
                        help='/full/path/to/config.file (usually dmrmonitor.cfg)')
    cli_args = parser.parse_args()

    # Ensure we have a path for the config file, if one wasn't specified, then use the execution directory
    if not cli_args.CONFIG_FILE:
        cli_args.CONFIG_FILE = os.path.dirname(
            os.path.abspath(__file__)) + '/dmrmonitor.cfg'

    CONFIG = build_config(cli_args.CONFIG_FILE)
    pprint(CONFIG)
