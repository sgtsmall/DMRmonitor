#!/usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
# updated 2020 VK2PSF
# first pass to align config file format
# Copyright (C) 2016  Cortney T. Buffington, N0MJS <n0mjs@me.com>
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

THIS IS EXTREMELY IMPORTANT:

Using this program effectively requires that you make certain changes in
your dmrlink configuration. In order for this program to work correctly,
All systems must be configured with:

RCM: True
CON_APP: True

'''

from __future__ import print_function

# Standard modules

import sys

# Twisted modules
from twisted.internet.protocol import ReconnectingClientFactory, Protocol
from twisted.protocols.basic import NetstringReceiver
from twisted.internet import reactor, task
from twisted.web.server import Site
from twisted.web.static import File
from twisted.web.resource import Resource
import base64
# Autobahn provides websocket service under Twisted
from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory

# Specific functions to import from standard modules
from pprint import pprint
from time import time, strftime, localtime
from cPickle import loads
from binascii import b2a_hex as h
from os.path import getmtime
from os import environ
from collections import deque
import csv
from itertools import islice
# Web templating environment
from jinja2 import Environment, PackageLoader, select_autoescape

# Utilities from K0USY Group sister project
from dmr_utils.utils import int_id, get_alias, try_download, mk_full_id_dict
import config
import log

# IPSC constants
from ipsc_const import *

# Opcodes for reporting protocol to DMRlink
OPCODE = {
    'CONFIG_REQ': '\x00',
    'CONFIG_SND': '\x01',
    'BRIDGE_REQ': '\x02',
    'BRIDGE_SND': '\x03',
    'CONFIG_UPD': '\x04',
    'BRIDGE_UPD': '\x05',
    'LINK_EVENT': '\x06',
    'BRDG_EVENT': '\x07',
    'RCM_SND':    '\x08'
    }

# Global Variables:
CONFIG      = {}
CTABLE      = {}
BRIDGES     = {}
BTABLE      = {}
BTABLE['BRIDGES'] = {}
BRIDGES_RX  = ''
CONFIG_RX   = ''
LOGBUF      = deque(100*[''], 100)
RED         = '#ff0000'
GREEN       = '#00ff00'
BLUE        = '#0000ff'
ORANGE      = '#ff8000'
WHITE       = '#ffffff'


# Does anybody read this stuff? There's a PEP somewhere that says I should do this.
__author__     = 'Alex Stewart, VK2PSF'
__copyright__  = 'Copyright (c) 2016-2019,2020 VK2PSF ,Cortney T. Buffington, N0MJS and the K0USY Group'
__credits__    = 'Colin Durbridge, G4EML, Steve Zingman, N4IRS; Mike Zingman, N4IRR; Jonathan Naylor, G4KLX; Hans Barthen, DL5DI; Torsten Shultze, DG1HT'
__license__    = 'GNU GPLv3'
__maintainer__ = 'Alex Stewart , N0MJS'
__email__      = 'vk2psf@arrl.net'

# Global variables used whether we are a module or __main__
systems = {}

# Shut ourselves down gracefully by disconnecting from the masters and peers.
def dmrmonitor_handler(_signal, _frame):
    for system in systems:
        logger.info('(GLOBAL) SHUTDOWN: DE-REGISTER SYSTEM: %s', system)
        systems[system].dereg()

# For importing HTML templates
def get_template(_file):
    with open(_file, 'r') as html:
        return html.read()

# Alias string processor
def alias_string(_id, _dict):
    alias = get_alias(_id, _dict, 'CALLSIGN', 'CITY', 'STATE')
    if type(alias) == list:
        for x,item in enumerate(alias):
            if item == None:
                alias.pop(x)
        return ', '.join(alias)
    else:
        return alias

def alias_short(_id, _dict):
    alias = get_alias(_id, _dict, 'CALLSIGN', 'NAME')
    if type(alias) == list:
        for x,item in enumerate(alias):
            if item == None:
                alias.pop(x)
        return ', '.join(alias)
    else:
        return str(alias)

def alias_call(_id, _dict):
    alias =  get_alias(_id, _dict, 'CALLSIGN')
    if type(alias) == list:
        return str(alias[0])
    else:
        return str(alias)

def alias_tgid(_id, _dict):
    alias = get_alias(_id, _dict, 'NAME')
    if type(alias) == list:
        return str(alias[0])
    else:
        return str(alias)

#
# REPEATER CALL MONITOR (RCM) PACKET PROCESSING
#
def process_rcm(_data):
    now = time()
    _cnow = strftime('%Y-%m-%d %H:%M:%S', localtime(now))
    _payload = _data.split(',', 1)
    _name = _payload[0]
    _data = _payload[1]
    _packettype = _data[0]
    if _packettype == CALL_MON_STATUS:
        logger.debug('RCM STATUS: {}: {}'.format(_name, repr(_data)))
        _source   = _data[1:5]
        _sourcei  = int_id(_data[1:5])
        _src_peer = int_id(_data[5:9]) #p5
        #_seq_num  = _data[9:13]
        _ts       = int_id(_data[13])+1 #p7
        _status   = STATUS[_data[15]] # suspect [14:16] but nothing in leading byte?
        _src_sub  = int_id(_data[16:19]) #p6
        _dest     = int_id(_data[19:22]) #p8
        _type     = TYPE[_data[22]] #p9
        #_prio     = _data[23]
        #_sec      = _data[24]

        if _status != 'End' and _status != 'BSID ON':
            CTABLE[_name]['PEERS'][_source][_ts]['STATUS'] = _status
            CTABLE[_name]['PEERS'][_source][_ts]['TYPE'] = _type
            CTABLE[_name]['PEERS'][_source][_ts]['SRC_SUB'] = alias_short(_src_sub, subscriber_ids)
            CTABLE[_name]['PEERS'][_source][_ts]['SRC_PEER'] = alias_call(_src_peer, peer_ids)
            CTABLE[_name]['PEERS'][_source][_ts]['DEST'] = _dest
            CTABLE[_name]['PEERS'][_source][_ts]['COLOR'] = GREEN
            CTABLE[_name]['PEERS'][_source][_ts]['LAST'] = now
        else:

            CTABLE[_name]['PEERS'][_source][_ts]['STATUS'] = ''
            CTABLE[_name]['PEERS'][_source][_ts]['TYPE'] = ''
            CTABLE[_name]['PEERS'][_source][_ts]['SRC_SUB'] = ''
            CTABLE[_name]['PEERS'][_source][_ts]['SRC_PEER'] = ''
            CTABLE[_name]['PEERS'][_source][_ts]['DEST'] = ''
            CTABLE[_name]['PEERS'][_source][_ts]['COLOR'] = WHITE
            CTABLE[_name]['PEERS'][_source][_ts]['LAST'] = now
#   p[9], p[0], p[1], p[3], p[5], alias_call(int(p[5]), subscriber_ids), p[7], p[8],alias_tgid(int(p[8]),talkgroup_ids),p[6], alias_short(int(p[6]), subscriber_ids))
#9 - , 0 - calltype, 1 - action , 2 - trx , 3 - system, 4 - streamid, 5 - alias_call , 6 - _src_sub,7 -timeslot , 8 - tgid[_dest],
            if LASTHEARD:
                logger.info('LASTHEARD TS:{} TG: {:>5} {:12.12s} ID:{:8} {:25.25s}  RPT:{:8} {:20.20s} X:{}'.format(_ts, _dest, alias_tgid(_dest, talkgroup_ids), _src_sub, alias_short(_src_sub, subscriber_ids) , _src_peer, alias_call(_src_peer, peer_ids), _sourcei))
#                log_lh_message = '{},{},{},{},{},{},{},TS{},TG{},{},{},{}'.format(_now, p[9], p[0], p[1], p[3], p[5], alias_call(int(p[5]), subscriber_ids), p[7], p[8],alias_tgid(_dest,talkgroup_ids),p[6], alias_short(int(p[6]), subscriber_ids))
                log_lh_message = '{},{},{},{},{},{},TS{},TG{},{},{},{}'.format(_cnow, _type, _status, _sourcei,  _src_peer, alias_call(_src_peer, peer_ids), _ts, _dest, alias_tgid(_dest, talkgroup_ids),_src_sub, alias_short(_src_sub, subscriber_ids))
                lh_logfile = open(LOG_PATH+"lastheard.log", "a")
                lh_logfile.write(log_lh_message + '\n')
                lh_logfile.close()
                my_list=[]
                n=0
                f = open("templates/lastheard.html", "w")
                f.write("<br><fieldset style=\"border-radius: 8px; background-color:#e0e0e0e0; text-algin: lef; margin-left:15px;margin-right:15px;font-size:14px;border-top-left-radius: 10px; border-top-right-radius: 10px;border-bottom-left-radius: 10px; border-bottom-right-radius: 10px;\">\n")
                f.write("<legend><b><font color=\"#000\">&nbsp;.: Lastheard :.&nbsp;</font></b></legend>\n")
                f.write("<table style=\"width:100%; font: 10pt arial, sans-serif\">\n")
                f.write("<TR style=\" height: 32px;font: 10pt arial, sans-serif; background-color:#9dc209; color:black\"><TH>Date</TH><TH>Time</TH><TH>Slot</TH><TH>Callsign (DMR-Id)</TH><TH>Name</TH><TH>TG#</TH><TH>TG Name</TH><TH>Source ID</TH><TH>System</TH></TR>\n")
                with open(LOG_PATH+"lastheard.log", "r") as textfile:
                    for row in islice(reversed(list(csv.reader(textfile))),100):
                      dur="1.0"
#                    duration=row[1]
#                    dur=str(int(float(duration.strip())))
                      if row[9] not in my_list:
                         if len(row) < 12:
                             hline="<TR style=\"background-color:#f9f9f9f9;\"><TD>"+row[0][:10]+"</TD><TD>"+row[0][11:16]+"</TD><TD>"+row[6][2:]+"</TD><TD><font color=brown><b><a target=\"_blank\" href=https://qrz.com/db/"+row[10]+">"+row[10]+"</a></b></font><span style=\"font: 7pt arial,sans-serif\"> ("+row[9]+")</span></TD><TD><font color=#002d62><b></b></font></TD><TD><font color=blue><b>"+row[7][2:]+"</b></font></TD><TD><font color=green><b>"+row[8]+"</b></font></TD><TD>"+row[4]+"</TD><TD>"+row[3]+"</TD></TR>"
                             my_list.append(row[9])
                             n += 1
                         else:
                             hline="<TR style=\"background-color:#f9f9f9f9;\"><TD>"+row[0][:10]+"</TD><TD>"+row[0][11:16]+"</TD><TD>"+row[6][2:]+"</TD><TD><font color=brown><b><a target=\"_blank\" href=https://qrz.com/db/"+row[10]+">"+row[10]+"</a></b></font><span style=\"font: 7pt arial,sans-serif\"> ("+row[9]+")</span></TD><TD><font color=#002d62><b>"+row[11]+"</b></font></TD><TD><font color=blue><b>"+row[7][2:]+"</b></font></TD><TD><font color=green><b>"+row[8]+"</b></font></TD><TD>"+row[4]+"</TD><TD>"+row[3]+"</TD></TR>"
                             my_list.append(row[9])
                             n += 1
                         f.write(hline+"\n")
                      if n == 10:
                         break
                f.write("</table></fieldset><br>")
                f.close()
                # End of Lastheard

    elif _packettype == CALL_MON_RPT:
        logger.debug('RCM REPEAT: {}: {}'.format(_name, repr(_data)))
        _source   = _data[1:5]
        _ts_state = [0, _data[5], _data[6]]
        for i in range(1,3):
            if _ts_state[i] == '\x01':
                CTABLE[_name]['PEERS'][_source][i]['STATUS'] = 'Repeating'
                CTABLE[_name]['PEERS'][_source][i]['COLOR'] = GREEN
            elif _ts_state[i] == '\x03':
                CTABLE[_name]['PEERS'][_source][i]['STATUS'] = 'Disabled'
                CTABLE[_name]['PEERS'][_source][i]['COLOR'] = RED
            elif _ts_state[i] == '\x04':
                CTABLE[_name]['PEERS'][_source][i]['STATUS'] = 'Enabled'
                CTABLE[_name]['PEERS'][_source][i]['COLOR'] = GREEN
            else:
                CTABLE[_name]['PEERS'][_source][i]['STATUS'] = ''
                CTABLE[_name]['PEERS'][_source][i]['COLOR'] = WHITE
            CTABLE[_name]['PEERS'][_source][i]['LAST'] = now

    elif _packettype == CALL_MON_NACK:
        logger.debug('RCM NACK: {}: {}'.format(_name, repr(_data)))
        _source = _data[1:5]
        _nack = _data[5]
        if _nack == '\x05':
            for i in range(1,3):
                CTABLE[_name]['PEERS'][_source][i]['STATUS'] = 'BSID ON'
                CTABLE[_name]['PEERS'][_source][i]['COLOR'] = ORANGE
        elif _nack == '\x06':
            for i in range(1,3):
                CTABLE[_name]['PEERS'][_source][i]['STATUS'] = ''
                CTABLE[_name]['PEERS'][_source][i]['COLOR'] = WHITE

        for i in range(1,3):
            #CTABLE[_name]['PEERS'][_source][i]['TYPE'] = ''
            #CTABLE[_name]['PEERS'][_source][i]['SRC_SUB'] = ''
            #CTABLE[_name]['PEERS'][_source][i]['SRC_PEER'] = ''
            #CTABLE[_name]['PEERS'][_source][i]['DEST'] = ''
            CTABLE[_name]['PEERS'][_source][i]['LAST'] = now
    else:
        logger.error('unknown call mon recieved: {}'.format(repr(_packettype)))
        return

    build_stats()

# DMRlink Table Functions
def add_peer(_stats_peers, _peer, _config_peer_data, _type):
    now = time()
    logger.debug('Adding peer: {}'.format(repr(_peer)))
    _stats_peers[_peer] = {}
    _stats_peers[_peer]['TYPE'] = _type
    _stats_peers[_peer]['RADIO_ID'] = int_id(_peer)
    _stats_peers[_peer]['ALIAS'] = alias_string(int_id(_peer), peer_ids)
    _stats_peers[_peer]['IP'] = _config_peer_data['IP']
    _stats_peers[_peer]['CONNECTED'] = _config_peer_data['STATUS']['CONNECTED']
    _stats_peers[_peer]['KEEP_ALIVES_SENT'] = _config_peer_data['STATUS']['KEEP_ALIVES_SENT']
    _stats_peers[_peer]['KEEP_ALIVES_RECEIVED'] = _config_peer_data['STATUS']['KEEP_ALIVES_RECEIVED']
    _stats_peers[_peer]['KEEP_ALIVES_MISSED'] = _config_peer_data['STATUS']['KEEP_ALIVES_MISSED']
    _stats_peers[_peer][1] = {'STATUS': '', 'TYPE': '', 'SRC_PEER': '', 'SRC_SUB': '', 'DEST': '', 'COLOR': WHITE, 'LAST': now}
    _stats_peers[_peer][2] = {'STATUS': '', 'TYPE': '', 'SRC_PEER': '', 'SRC_SUB': '', 'DEST': '', 'COLOR': WHITE, 'LAST': now}

def update_peer(_stats_peers, _peer, _config_peer_data):
    logger.debug('Updating peer: {}'.format(repr(_peer)))
    _stats_peers[_peer]['CONNECTED'] = _config_peer_data['STATUS']['CONNECTED']
    _stats_peers[_peer]['KEEP_ALIVES_SENT'] = _config_peer_data['STATUS']['KEEP_ALIVES_SENT']
    _stats_peers[_peer]['KEEP_ALIVES_RECEIVED'] = _config_peer_data['STATUS']['KEEP_ALIVES_RECEIVED']
    _stats_peers[_peer]['KEEP_ALIVES_MISSED'] = _config_peer_data['STATUS']['KEEP_ALIVES_MISSED']

def delete_peers(_peers_to_delete, _stats_table_peers):
    for _peer in _peers_to_delete:
        del _stats_table_peers[_peer]
        logger.debug('Deleting peer: {}'.format(repr(_peer)))

def build_dmrlink_table(_config, _stats_table):
    for _ipsc, _ipsc_data in _config.iteritems():
        _stats_table[_ipsc] = {}
        _stats_table[_ipsc]['PEERS'] = {}
        _stats_table[_ipsc]['MASTER'] = _config[_ipsc]['LOCAL']['MASTER_PEER']
        _stats_table[_ipsc]['RADIO_ID'] = int_id(_config[_ipsc]['LOCAL']['RADIO_ID'])
        _stats_table[_ipsc]['IP'] = _config[_ipsc]['LOCAL']['IP']
        _stats_peers = _stats_table[_ipsc]['PEERS']

        # if this peer is the master
        if _stats_table[_ipsc]['MASTER'] == False:
            _peer = _config[_ipsc]['MASTER']['RADIO_ID']
            _config_peer_data = _config[_ipsc]['MASTER']
            add_peer(_stats_peers, _peer, _config_peer_data, 'Master')

        # for all peers that are not the master
        for _peer, _config_peer_data in _config[_ipsc]['PEERS'].iteritems():
            if _peer != _config[_ipsc]['LOCAL']['RADIO_ID']:
                add_peer(_stats_peers, _peer, _config_peer_data, 'Peer')


def update_dmrlink_table(_config, _stats_table):

    for _ipsc, _ipsc_data in _config.iteritems():
        _stats_peers = _stats_table[_ipsc]['PEERS']

        # if this peer is the master
        if _stats_table[_ipsc]['MASTER'] == False:
            _peer = _config[_ipsc]['MASTER']['RADIO_ID']
            _config_peer_data = _config[_ipsc]['MASTER']

            _stats_peers[_peer]['RADIO_ID'] = int_id(_peer)
            update_peer(_stats_peers, _peer, _config_peer_data)

        # for all of the peers that are not the master... update or add
        for _peer, _config_peer_data in _config[_ipsc]['PEERS'].iteritems():
            if _peer != _config[_ipsc]['LOCAL']['RADIO_ID']:
                _stats_peers = _stats_table[_ipsc]['PEERS']

                # update the peer if we already have it
                if _peer in _stats_table[_ipsc]['PEERS']:
                    update_peer(_stats_peers, _peer, _config_peer_data)

                # addit if we don't have it
                if _peer not in _stats_table[_ipsc]['PEERS']:
                    add_peer(_stats_peers, _peer, _config_peer_data, 'peer')

        # for peers that need to be removed, never the master. This is complicated
        peers_to_delete = []

        # find any peers missing in the config update
        for _peer, _stats_peer_data in _stats_table[_ipsc]['PEERS'].iteritems():
            if _peer not in _config[_ipsc]['PEERS'] and _peer != _config[_ipsc]['MASTER']['RADIO_ID']:
                peers_to_delete.append(_peer)

        # delte anything identified from the right part of the stats table
        delete_peers(peers_to_delete, _stats_table[_ipsc]['PEERS'])


#
# CONFBRIDGE TABLE FUNCTIONS
#
def build_bridge_table(_bridges):
    _stats_table = {}
    _now = time()
    _cnow = strftime('%Y-%m-%d %H:%M:%S', localtime(_now))

    for _bridge, _bridge_data in _bridges.iteritems():
        _stats_table[_bridge] = {}

        for system in _bridges[_bridge]:
            _stats_table[_bridge][system['SYSTEM']] = {}
            _stats_table[_bridge][system['SYSTEM']]['TS'] = system['TS']
            _stats_table[_bridge][system['SYSTEM']]['TGID'] = int_id(system['TGID'])

            if system['TO_TYPE'] == 'ON' or system['TO_TYPE'] == 'OFF':
                if system['TIMER'] - _now > 0:
                    _stats_table[_bridge][system['SYSTEM']]['EXP_TIME'] = int(system['TIMER'] - _now)
                else:
                    _stats_table[_bridge][system['SYSTEM']]['EXP_TIME'] = 'Expired'
                if system['TO_TYPE'] == 'ON':
                    _stats_table[_bridge][system['SYSTEM']]['TO_ACTION'] = 'Disconnect'
                else:
                    _stats_table[_bridge][system['SYSTEM']]['TO_ACTION'] = 'Connect'
            else:
                _stats_table[_bridge][system['SYSTEM']]['EXP_TIME'] = 'N/A'
                _stats_table[_bridge][system['SYSTEM']]['TO_ACTION'] = 'None'

            if system['ACTIVE'] == True:
                _stats_table[_bridge][system['SYSTEM']]['ACTIVE'] = 'Connected'
                _stats_table[_bridge][system['SYSTEM']]['COLOR'] = GREEN
            elif system['ACTIVE'] == False:
                _stats_table[_bridge][system['SYSTEM']]['ACTIVE'] = 'Disconnected'
                _stats_table[_bridge][system['SYSTEM']]['COLOR'] = RED

            for i in range(len(system['ON'])):
                system['ON'][i] = str(int_id(system['ON'][i]))

            _stats_table[_bridge][system['SYSTEM']]['TRIG_ON'] = ', '.join(system['ON'])

            for i in range(len(system['OFF'])):
                system['OFF'][i] = str(int_id(system['OFF'][i]))

            _stats_table[_bridge][system['SYSTEM']]['TRIG_OFF'] = ', '.join(system['OFF'])

    return _stats_table

#
# BUILD DMRLINK AND CONFBRIDGE TABLES FROM CONFIG/BRIDGES DICTS
#          THIS CURRENTLY IS A TIMED CALL
#
build_time = time()
def build_stats():
    global build_time
    now = time()
    if True: #now > build_time + 1:
        if CONFIG:
            table = 'd' + dtemplate.render(_table=CTABLE)
            dashboard_server.broadcast(table)
        if BRIDGES:
            table = 'b' + btemplate.render(_table=BTABLE['BRIDGES'])
            dashboard_server.broadcast(table)
        build_time = now

def timeout_clients():
    now = time()
    try:
        for client in dashboard_server.clients:
            if dashboard_server.clients[client] + CONFIG['WEBSITE']['CLIENT_TIMEOUT'] < now:
                logger.info('TIMEOUT: disconnecting client %s', dashboard_server.clients[client])
                try:
                    dashboard.sendClose(client)
                except Exception as e:
                    logger.error('Exception caught parsing client timeout %s', e)
    except:
        logger.info('CLIENT TIMEOUT: List does not exist, skipping. If this message persists, contact the developer')

#
# PROCESS INCOMING MESSAGES AND TAKE THE CORRECT ACTION DEPENING ON THE OPCODE
#
def process_message(_message):
    global CONFIG, BRIDGES, CONFIG_RX, BRIDGES_RX
    opcode = _message[:1]
    _now = strftime('%Y-%m-%d %H:%M:%S %Z', localtime(time()))
    logger.debug('got opcode: {}, message: {}'.format(repr(opcode), repr(_message[1:])))

    if opcode == OPCODE['CONFIG_SND']:
        logger.debug('got CONFIG_SND opcode')
        CONFIG = load_dictionary(_message)
        CONFIG_RX = strftime('%Y-%m-%d %H:%M:%S', localtime(time()))
        if CTABLE:
            update_dmrlink_table(CONFIG, CTABLE)
        else:
            build_dmrlink_table(CONFIG, CTABLE)
    elif opcode == OPCODE['BRIDGE_SND']:
        logger.debug('got BRIDGE_SND opcode')
        BRIDGES = load_dictionary(_message)
        BRIDGES_RX = strftime('%Y-%m-%d %H:%M:%S', localtime(time()))
        BTABLE['BRIDGES'] = build_bridge_table(BRIDGES)

    elif opcode == OPCODE['LINK_EVENT']:
        logger.info('LINK_EVENT Received: {}'.format(repr(_message[1:])))
    elif opcode == OPCODE['RCM_SND']:
        process_rcm(_message[1:])
        logger.debug('RCM Message Received: {}'.format(repr(_message[1:])))
        #dashboard_server.broadcast('l' + repr(_message[1:]))
    elif opcode == OPCODE['BRDG_EVENT']:
        logger.info('BRIDGE EVENT: {}'.format(repr(_message[1:])))
        p = _message[1:].split(",")
        if p[0] == 'GROUP VOICE':
            if p[1] == 'END':
                log_message = '{}: {} {}:   IPSC: {:15.15s} PEER: {:8.8s} {:20.20s} SUB: {:8.8s} {:25.25s} TS: {} TGID: {:>5s} {:12.12s} DURATION: {}s'.format(_now, p[0], p[1], p[2], p[4], alias_call(int(p[4]), peer_ids), p[5], alias_short(int(p[5]), subscriber_ids), p[6], p[7], alias_tgid(int(p[7]), talkgroup_ids), p[8])
            elif p[1] == 'START':
                log_message = '{}: {} {}: IPSC: {:15.15s} PEER: {:8.8s} {:20.20s} SUB: {:8.8s} {:25.25s} TS: {} TGID: {:>5s} {:12.12s}'.format(_now, p[0], p[1], p[2], p[4], alias_call(int(p[4]), peer_ids), p[5], alias_short(int(p[5]), subscriber_ids), p[6], p[7], alias_tgid(int(p[7]), talkgroup_ids))
            elif p[1] == 'END WITHOUT MATCHING START':
                log_message = '{}: {} {}: IPSC: {:15.15s} PEER: {:8.8s} {:20.20s} SUB: {:8.8s} {:25.25s} TS: {} TGID: {:>5s} {:12.12s}'.format(_now, p[0], p[1], p[2], p[4], alias_call(int(p[4]), peer_ids), p[5], alias_short(int(p[5]), subscriber_ids), p[6], p[7], alias_tgid(int(p[7]), talkgroup_ids))
            else:
                log_message = '{}: UNKNOWN GROUP VOICE LOG MESSAGE'.format(_now)
        else:
            log_message = '{}: UNKNOWN LOG MESSAGE'.format(_now)

        dashboard_server.broadcast('l' + log_message)
        LOGBUF.append(log_message)
    else:
        logger.debug('got unknown opcode: {}, message: {}'.format(repr(opcode), repr(_message[1:])))


def load_dictionary(_message):
    data = _message[1:]
    return loads(data)
    logger.debug('Successfully decoded dictionary')

#
# COMMUNICATION WITH THE DMRLINK INSTANCE
#
class report(NetstringReceiver):
    def __init__(self):
        pass

    def connectionMade(self):
        pass

    def connectionLost(self, reason):
        pass

    def stringReceived(self, data):
        process_message(data)


class reportClientFactory(ReconnectingClientFactory):
    def __init__(self):
        pass

    def startedConnecting(self, connector):
        logger.info('Initiating Connection to Server.')
        if 'dashboard_server' in locals() or 'dashboard_server' in globals():
            dashboard_server.broadcast('q' + 'Connection to DMRlink Established')

    def buildProtocol(self, addr):
        logger.info('Connected.')
        logger.info('Resetting reconnection delay')
        self.resetDelay()
        return report()

    def clientConnectionLost(self, connector, reason):
        logger.info('Lost connection.  Reason: %s', reason)
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)
        dashboard_server.broadcast('q' + 'Connection to DMRlink Lost')

    def clientConnectionFailed(self, connector, reason):
        logger.info('Connection failed. Reason: %s', reason)
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)


#
# WEBSOCKET COMMUNICATION WITH THE DASHBOARD CLIENT
#
class dashboard(WebSocketServerProtocol):

    def onConnect(self, request):
        logger.info('Client connecting: %s', request.peer)

    def onOpen(self):
        logger.info('WebSocket connection open.')
        self.factory.register(self)
        self.sendMessage('d' + str(dtemplate.render(_table=CTABLE)))
        self.sendMessage('b' + str(btemplate.render(_table=BTABLE['BRIDGES'])))
        for _message in LOGBUF:
            if _message:
                self.sendMessage('l' + _message)

    def onMessage(self, payload, isBinary):
        if isBinary:
            logger.info('Binary message received: %s bytes', len(payload))
        else:
            logger.info('Text message received: %s', payload.decode('utf8'))

    def connectionLost(self, reason):
        WebSocketServerProtocol.connectionLost(self, reason)
        self.factory.unregister(self)

    def onClose(self, wasClean, code, reason):
        logger.info('WebSocket connection closed: %s', reason)


class dashboardFactory(WebSocketServerFactory):

    def __init__(self, url):
        WebSocketServerFactory.__init__(self, url)
        self.clients = []

    def register(self, client):
        if client not in self.clients:
            logger.info('registered client %s', client.peer)
            self.clients.append(client)

    def unregister(self, client):
        if client in self.clients:
            logger.info('unregistered client %s', client.peer)
            self.clients.remove(client)

    def broadcast(self, msg):
        logger.debug('broadcasting message to: %s', self.clients)
        for c in self.clients:
            c.sendMessage(msg.encode('utf8'))
            logger.debug('message sent to %s', c.peer)
# experiment timeout_clients
    def timeout(self, client):
       logger.debug('check timeout message to: %s', self.clients)
       for client in self.clients:
           if self.clients[client] + CONFIG['WEBSITE']['CLIENT_TIMEOUT'] < now:
               logger.info('TIMEOUT: disconnecting client %s', self.clients[client])
               try:
                   dashboard.sendClose(client)
               except Exception as e:
                   logger.error('Exception caught parsing client timeout %s', e)
           else:
               logger.info('time registered client {}'.format(client))
         #  self.clients.remove(client)



#
# STATIC WEBSERVER
#
class web_server(Resource):
    isLeaf = True
    def render_GET(self, request):
        logger.info('static website requested: %s', request)
        if WEBAUTH:
          user = WEBUSER.encode('utf-8')
          password = WEBPASS.encode('utf-8')
          auth = request.getHeader('Authorization')
          if auth and auth.split(' ')[0] == 'Basic':
             decodeddata = base64.b64decode(auth.split(' ')[1])
             if decodeddata.split(b':') == [user, password]:
                 logger.info('Authorization OK')
                 return (index_html).encode('utf-8')
          request.setResponseCode(401)
          request.setHeader('WWW-Authenticate', 'Basic realm="realmname"')
          logger.info('Someone wanted to get access without authorization')
          return "<html<head></hread><body style=\"background-color: #EEEEEE;\"><br><br><br><center> \
                    <fieldset style=\"width:600px;background-color:#e0e0e0e0;text-algin: center; margin-left:15px;margin-right:15px; \
                     font-size:14px;border-top-left-radius: 10px; border-top-right-radius: 10px; \
                     border-bottom-left-radius: 10px; border-bottom-right-radius: 10px;\"> \
                  <p><font size=5><b>Authorization Required</font></p></filed></center></body></html>".encode('utf-8')
        else:
            return (index_html).encode('utf-8')

# ID ALIAS CREATION
# Download
def mk_aliases(_config):
    if _config['ALIASES']['TRY_DOWNLOAD'] == True:
        # Try updating peer aliases file
        result = try_download(_config['ALIASES']['PATH'], _config['ALIASES']['PEER_FILE'], _config['ALIASES']['PEER_URL'], _config['ALIASES']['STALE_TIME'])
        logger.info('[ALIAS]  %s', result)
        # Try updating subscriber aliases file
        result = try_download(_config['ALIASES']['PATH'], _config['ALIASES']['SUBSCRIBER_FILE'], _config['ALIASES']['SUBSCRIBER_URL'], _config['ALIASES']['STALE_TIME'])
        logger.info('[ALIAS]  %s', result)

    # Make Dictionaries
    peer_ids = mk_full_id_dict(_config['ALIASES']['PATH'], _config['ALIASES']['PEER_FILE'],'peer')
    if peer_ids:
        logger.info('[ALIAS] ID ALIAS MAPPER: peer_ids dictionary is available')

    subscriber_ids = mk_full_id_dict(_config['ALIASES']['PATH'], _config['ALIASES']['SUBSCRIBER_FILE'],'subscriber')
    if subscriber_ids:
        logger.info('[ALIAS] ID ALIAS MAPPER: subscriber_ids dictionary is available')

    talkgroup_ids = mk_full_id_dict(_config['ALIASES']['PATH'], _config['ALIASES']['TGID_FILE'],'tgid')
    if talkgroup_ids:
        logger.info('[ALIAS] ID ALIAS MAPPER: talkgroup_ids dictionary is available')

    local_subscriber_ids = mk_full_id_dict(_config['ALIASES']['PATH'], _config['ALIASES']['LOCAL_SUB_FILE'],'subscriber')
    if local_subscriber_ids:
        logger.info('[ALIAS] ID ALIAS MAPPER: local_subscriber_ids added to subscriber_ids dictionary')
        subscriber_ids.update(local_subscriber_ids)

    local_peer_ids = mk_full_id_dict(_config['ALIASES']['PATH'], _config['ALIASES']['LOCAL_PEER_FILE'],'peer')
    if local_peer_ids:
        logger.info('[ALIAS] ID ALIAS MAPPER: local_peer_ids added peer_ids dictionary')
        peer_ids.update(local_peer_ids)

    return peer_ids, subscriber_ids, talkgroup_ids

if __name__ == '__main__':
    import argparse
    #import system
    import os
    import signal

    # Change the current directory to the location of the application
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))

    # CLI argument parser - handles picking up the config file from the command line, and sending a "help" message
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='store', dest='CONFIG_FILE', help='/full/path/to/config.file (usually dmrmonitor.cfg)')
    parser.add_argument('-l', '--logging', action='store', dest='LOG_LEVEL', help='Override config file logging level.')
    cli_args = parser.parse_args()

    # Ensure we have a path for the config file, if one wasn't specified, then use the execution directory
    if not cli_args.CONFIG_FILE:
        cli_args.CONFIG_FILE = os.path.dirname(os.path.abspath(__file__))+'/dmrmonitor.cfg'

    # Call the external routine to build the configuration dictionary
    CONFIG = config.build_config(cli_args.CONFIG_FILE)

    # Call the external routing to start the system logger
    if cli_args.LOG_LEVEL:
        CONFIG['LOGGER']['LOG_LEVEL'] = cli_args.LOG_LEVEL
    logger = log.config_logging(CONFIG['LOGGER'])
    logger.info('\n\nCopyright (c) 2013, 2014, 2015, 2016, 2018, 2019\n\tThe Regents of the K0USY Group. All rights reserved.\n')
    logger.debug('(GLOBAL) Logging system started, anything from here on gets logged')

    WEBSERVICE_STR = ":{0}".format(CONFIG['WEBSITE']['WEBSERVICE_PORT'])
    logger.debug('(GLOBAL) WEBSERVICE_STR %s', WEBSERVICE_STR)
    SYSTEMNAME_STR = "{0}".format(CONFIG['GLOBAL']['REPORT_NAME'])
    logger.debug('(GLOBAL) SYSTEMNAME_STR %s', SYSTEMNAME_STR)
    logger.info('Config: {} {}'.format(CONFIG['WEBSITE']['WEB_AUTH'], CONFIG['WEBSITE']['WEB_USER']))
    LASTHEARD = CONFIG['LOGGER']['LOG_LASTHEARD']
    WEBAUTH = CONFIG['WEBSITE']['WEB_AUTH']
    WEBUSER = CONFIG['WEBSITE']['WEB_USER']
    WEBPASS = CONFIG['WEBSITE']['WEB_PASS']
    LOG_PATH = CONFIG['LOGGER']['LOG_PATH']
    environ['TZ'] = CONFIG['WEBSITE']['WEB_TZ']

    # Set up the signal handler
    def sig_handler(_signal, _frame):
        logger.info('(GLOBAL) SHUTDOWN: dmrmonitor IS TERMINATING WITH SIGNAL %s', str(_signal))
        dmrmonitor_handler(_signal, _frame)
        logger.info('(GLOBAL) SHUTDOWN: ALL SYSTEM HANDLERS EXECUTED - STOPPING REACTOR')
        reactor.stop()

    # Set signal handers so that we can gracefully exit if need be
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, sig_handler)

    peer_ids, subscriber_ids, talkgroup_ids = mk_aliases(CONFIG)

    logger.info('(GLOBAL) DMRmonitor \'dmrmonitor.py\' -- SYSTEM STARTING...')

    # Jinja2 Stuff
    env = Environment(
        loader=PackageLoader('dmrmonitor', 'templates'),
        autoescape=select_autoescape(['html', 'xml'])
    )

    dtemplate = env.get_template('dmrlink_table.html')
    btemplate = env.get_template('bridge_table.html')

    # Create Static Website index file
    index_html = get_template(CONFIG['WEBSITE']['PATH'] + 'index_template.html')
    index_html = index_html.replace('<<<system_name>>>', SYSTEMNAME_STR)
    index_html = index_html.replace('<<<webservice_port>>>', WEBSERVICE_STR)
    favicon_ico = get_template(CONFIG['WEBSITE']['PATH'] + 'favicon.ico')
    if CONFIG['WEBSITE']['CLIENT_TIMEOUT'] > 0:
        index_html = index_html.replace('<<<timeout_warning>>>', 'Continuous connections not allowed. Connections time out in {} seconds'.format(CONFIG['WEBSITE']['CLIENT_TIMEOUT']))
    else:
        index_html = index_html.replace('<<<timeout_warning>>>', '')

    # Connect to DMRlink
    reactor.connectTCP(CONFIG['GLOBAL']['DMRLINK_IP'], CONFIG['GLOBAL']['DMRLINK_PORT'], reportClientFactory())

    # Create websocket server to push content to clients
    dashboard_server = dashboardFactory('ws://*'+WEBSERVICE_STR)
    dashboard_server.protocol = dashboard
    reactor.listenTCP(CONFIG['WEBSITE']['WEBSERVICE_PORT'], dashboard_server)

    # Start update loop
    update_stats = task.LoopingCall(build_stats)
    update_stats.start(CONFIG['GLOBAL']['FREQUENCY'])
    # Start a timout loop
    if CONFIG['WEBSITE']['CLIENT_TIMEOUT'] > 0:
        timeout = task.LoopingCall(timeout_clients)
        timeout.start(10)

    # Create static web server to push initial index.html
    website = Site(web_server())
    reactor.listenTCP(CONFIG['WEBSITE']['WEB_SERVER_PORT'], website)

    reactor.run()
