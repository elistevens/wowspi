#!/usr/bin/env python

#Copyright (c) 2009, Eli Stevens
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

import cgi
import collections
import copy
import csv
import datetime
import glob
import itertools
import json
import optparse
import os
import random
import re
import sqlite3
import sys
import time
import urllib
import urllib2

import config

from sqliteutils import *


def adapt_json(d):
    import json
    return json.dumps(d, separators=(',',':'))

def convert_json(s):
    import json
    return json.loads(s)

# Register the adapter
sqlite3.register_adapter(dict, adapt_json)
sqlite3.register_adapter(list, adapt_json)

# Register the converter
sqlite3.register_converter("json", convert_json)



#def usage(sys_argv):
#    op = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
#    usage_setup(op)
#    
#    options, arguments = op.parse_args(sys_argv)
#    
#    usage_defaults(options)
#    
#    return options, arguments

#def usage_setup(op, **kwargs):
#    if kwargs.get('force', True):
#        op.add_option("--force"
#                , help="Force reparsing from scratch."
#                #, metavar="OUTPUT"
#                , dest="force"
#                , action="store_true"
#                #, type="str"
#                #, default="output"
#            )
#
#    if kwargs.get('date', True):
#        op.add_option("--date"
#                , help="Use DATE for standard log files and db names.  Overrides --db and --log."
#                , metavar="DATE"
#                , dest="date_str"
#                , action="store"
#                , type="str"
#                #, default="output"
#            )
#
#    if kwargs.get('db', True):
#        op.add_option("--db"
#                , help="Desired sqlite database output file name."
#                , metavar="OUTPUT"
#                , dest="db_path"
#                , action="store"
#                , type="str"
#                #, default="output"
#            )
#
#    if kwargs.get('log', True):
#        op.add_option("--log"
#                , help="Path to the WoWCombatLog.txt file."
#                , metavar="LOGFILE"
#                , dest="log_path"
#                , action="store"
#                , type="str"
#                #, default="output"
#            )
#        
#    if kwargs.get('verbose', True):
#        op.add_option("-v", "--verbose"
#                , help="Print more output; may include debugging information not intended for end-users."
#                #, metavar="OUTPUT"
#                , dest="verbose"
#                , action="store_true"
#                #, type="str"
#                , default=False
#            )
#
#
#def usage_defaults(options):
#    #print "before", options
#    if options.date_str:
#        #print "in date_str", options.date_str
#        
#        options.log_path = glob.glob(os.path.join(config.wowspi_path, 'data', 'logs', '*' + options.date_str + '*'))[0]
#        options.db_path = os.path.join(config.wowspi_path, 'data', 'parses', options.date_str + '.db')
#        
#        #print options
#    else:
#        if hasattr(options, 'log_path') and re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', options.log_path):
#            try:
#                options.log_path = (glob.glob(options.log_path) + glob.glob(os.path.join(config.wowspi_path, 'data', 'logs', '*' + options.log_path + '*')))[0]
#            except:
#                pass
#            
#        if hasattr(options, 'db_path') and re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', options.db_path):
#            options.db_path = os.path.join(config.wowspi_path, 'data', 'parses', options.db_path + '.db')
#
#    #return options, arguments
#    


fixed_list = ['sourceGUID', 'sourceName', 'sourceFlags', 'destGUID', 'destName', 'destFlags']

# Note: order is important here, because 'SPELL' is a prefix for 'SPELL_XXX', the rest are in rough priority order
prefix_list = [
        ('SPELL_PERIODIC',      ['spellId', 'spellName', 'spellSchool']),
        ('SPELL_BUILDING',      ['spellId', 'spellName', 'spellSchool']),
        ('SPELL',               ['spellId', 'spellName', 'spellSchool']),
        ('SWING',               []),
        ('DAMAGE',              ['spellId', 'spellName', 'spellSchool']),
        ('RANGE',               ['spellId', 'spellName', 'spellSchool']),
        ('ENVIRONMENTAL',       ['environmental']),
        ('ENCHANT',             ['spellName', 'itemID', 'itemName']),
        ('UNIT',                []),
        ('PARTY',               []),
    ]
prefix_dict = dict(prefix_list)

# See: _DAMAGE vs. _DURABILITY_DAMAGE
suffix_list = [
        ('_DAMAGE',             ['amount', 'extra', 'school', 'resisted', 'blocked', 'absorbed', 'critical', 'glancing', 'crushing']),
        ('_MISSED',             ['miss', '?amount']),
        ('_HEAL',               ['amount', 'extra', 'absorbed', 'critical']),
        ('_ENERGIZE',           ['amount', 'power']),
        ('_DRAIN',              ['amount', 'power', 'extra']),
        ('_LEECH',              ['amount', 'power', 'extra']),
        ('_INTERRUPT',          ['extraSpellID', 'extraSpellName', 'extraSchool']),
        ('_DISPEL',             ['extraSpellID', 'extraSpellName', 'extraSchool', 'aura']),
        ('_DISPEL_FAILED',      ['extraSpellID', 'extraSpellName', 'extraSchool']),
        ('_STOLEN',             ['extraSpellID', 'extraSpellName', 'extraSchool', 'aura']),
        ('_EXTRA_ATTACKS',      ['amount']),
        ('_AURA_APPLIED',       ['aura']),
        ('_AURA_REMOVED',       ['aura']),
        ('_AURA_APPLIED_DOSE',  ['aura', 'amount']),
        ('_AURA_REMOVED_DOSE',  ['aura', 'amount']),
        ('_AURA_REFRESH',       ['aura']),
        ('_AURA_BROKEN',        ['aura']),
        ('_AURA_BROKEN_SPELL',  ['extraSpellID', 'extraSpellName', 'extraSchool', 'aura']),
        ('_CAST_START',         []),
        ('_CAST_SUCCESS',       []),
        ('_CAST_FAILED',        ['failed']),
        ('_INSTAKILL',          []),
        ('_DURABILITY_DAMAGE',  []),
        ('_DURABILITY_DAMAGE_ALL',  []),
        ('_CREATE',             []),
        ('_SUMMON',             []),
        ('_RESURRECT',          []),
        ('_SPLIT',              ['amount', 'extra', 'school', 'resisted', 'blocked', 'absorbed', 'critical', 'glancing', 'crushing']),
        ('_SHIELD',             ['amount', 'extra', 'school', 'resisted', 'blocked', 'absorbed', 'critical', 'glancing', 'crushing']),
        ('_SHIELD_MISSED',      ['miss', '?amount']),
        ('_REMOVED',            []),
        ('_APPLIED',            []),
        ('_DIED',               []),
        ('_DESTROYED',          []),
        ('_KILL',               []),
    ]
suffix_dict = dict(suffix_list)



flags_list = [
        (('Type', 0x0000FC00), {
            0x00004000: 'Object',
            0x00002000: 'Guardian',
            0x00001000: 'Pet',
            0x00000800: 'NPC',
            0x00000400: 'PC',
        }),
        (('Controller', 0x00000300), {
            0x00000200: 'NPC',
            0x00000100: 'PC',
        }),
        (('Reaction', 0x000000F0), {
            0x00000040: 'Hostile',
            0x00000020: 'Neutral',
            0x00000010: 'Friendly',
        }),
    ]

flagsCache_dict = {}
def parseFlags(pre_str, flags):
    #flags = event[pre_str + 'Flags']
    cache_key = (pre_str, flags)
    if cache_key in flagsCache_dict:
        return flagsCache_dict[cache_key]
    
    d = []
    for key, value_dict in flags_list:
        post_str, mask = key
        bits = flags & mask
        
        d.append(value_dict.get(bits, 'Unknown:%x' % bits))
    
    flagsCache_dict[cache_key] = d
    #print flags, cache_dict[cache_key]
    return d


number_re = re.compile(r"^-?\d+$")
convertCache_dict = {}
def convert(value):
    if value in convertCache_dict:
        return convertCache_dict[value]

    newValue = value
    if value == 'nil':
        newValue = None
    elif isinstance(value, str):
        if value.startswith('0x') and len(value) <= 10:
            newValue = int(value[2:], 16)
        elif number_re.match(value):
            newValue = int(value)
        else:
            newValue = unicode(value, 'utf8')
            
    convertCache_dict[value] = newValue
    return newValue
    


time_re = re.compile('(\\d+)/(\\d+) (\\d+):(\\d+):(\\d+).(\\d+)')
colCache_dict = {}
sqlCache_dict = {}
def parseRow(row, now):
    """
    10/21 20:59:04.831  SWING_DAMAGE,0x0000000002B0C69C,"Biggdog",0x514,0xF130005967003326,"High Warlord Naj'entus",0xa48,171,0,1,0,0,0,nil,1,nil
    10/21 20:59:04.873  SPELL_DAMAGE,0x000000000142C9BE,"Autogun",0x514,0xF130005967003326,"High Warlord Naj'entus",0xa48,27209,"Shadow Bolt",0x20,2233,0,32,220,0,0,nil,nil,nil
    """

    #event = {}
    event_list = []

    try:
        date_str, time_str, eventType_str = row.pop(0).split()

        #event['eventType'] = eventType_str

        tmp_list = time_str.split(".")
        time_list = [int(x) for x in date_str.split('/') + tmp_list[0].split(':') + [tmp_list[1]]]

        event_dt = datetime.datetime(now.year, time_list[0], time_list[1], time_list[2], time_list[3], time_list[4], time_list[5] * 1000)
        if event_dt > now:
            event_dt = datetime.datetime(now.year - 1, time_list[0], time_list[1], time_list[2], time_list[3], time_list[4], time_list[5] * 1000)
        event_list.append(event_dt)
        event_list.append(eventType_str)

        eventType_list = eventType_str.split('_')
        if eventType_list[1] in ('PERIODIC', 'BUILDING'):
            prefix_str = eventType_list[0] + '_' + eventType_list[1]
        else:
            prefix_str = eventType_list[0]
        suffix_str = eventType_str[len(prefix_str):]
        event_list.append(prefix_str)
        event_list.append(suffix_str)
        

        #for key, value in itertools.izip_longest(col_list, row):
        #    assert key is not None, repr(col_list) + '\t' + repr(row)
        #    assert value is not None or key[0] == '?', repr(col_list) + '\t' + repr(row)
        #    
        #    if value is not None:
        #        if value == 'nil':
        #            event[key] = None
        #        elif isinstance(value, str):
        #            if value.startswith('0x'):
        #                event[key] = int(value[2:], 16)
        #            elif number_re.match(value):
        #                event[key] = int(value)
        #            else:
        #                event[key] = unicode(value, 'utf8')

        event_list.extend(parseFlags('source', convert(row[2])))
        event_list.extend(parseFlags('dest', convert(row[5])))

        if eventType_str not in colCache_dict:
            col_list = fixed_list + prefix_dict[prefix_str] + [x.lstrip('?') for x in suffix_dict[suffix_str]]
            full_list = ['time', 'eventType', 'prefix', 'suffix',
                    'sourceType', 'sourceController', 'sourceReaction',
                    'destType', 'destController', 'destReaction'] + col_list
            
            sqlCache_dict[eventType_str] = (','.join(full_list), ','.join(['?' for x in full_list]))
            colCache_dict[eventType_str] = (','.join(full_list), ','.join(['?' for x in full_list]), col_list)
        else:
            col_list = colCache_dict[eventType_str][-1]
        event_list.extend([convert(value) for key, value in itertools.izip_longest(col_list, row)])
            
        return sqlCache_dict[eventType_str], tuple(event_list)
    except:
        raise



def parseLog(conn, log_path):
    col_list = []
    for prefix_tup in prefix_list:
        for col in prefix_tup[1]:
            if col not in col_list:
                col_list.append(col)
    for suffix_tup in suffix_list:
        for col in suffix_tup[1]:
            col = col.lstrip('?')
            if col not in col_list:
                col_list.append(col)
                
    #col_list.sort()
                
    col_list = ['time', 'eventType', 'prefix', 'suffix', 'sourceType', 'sourceController', 'sourceReaction', 'destType', 'destController', 'destReaction'] + list(fixed_list) + col_list


    #print col_list

    col_str = ', '.join(col_list)
    #qmk_str = ', '.join(['?' for x in col_list])
    insert_str = '''insert into event (%s) values (%s)'''
    #values_str = '''(?, %s)''' % qmk_str

    conn_execute(conn, '''drop table if exists event''')
    
    #print ('''create table event (id integer primary key, path, %s, fragment_id int, combat_id int, wound_dict json, active_dict json)''' % col_str).replace('time,', 'time timestamp,',)
    
    conn_execute(conn, ('''create table event (id integer primary key, path, %s)''' % col_str).replace('time,', 'time timestamp,',))
    conn_execute(conn, '''create index ndx_event_time on event (time)''')
    conn_execute(conn, '''create index ndx_event_time_sourceName on event (sourceName, suffix, time)''')
    conn_execute(conn, '''create index ndx_event_source_dest_type on event (sourceType, destType, suffix, time, sourceName, destName)''')

    now = datetime.datetime.now()
    event_list = []
    
    # All of the event_list[:1000] and the sorting is to insure that events
    # are inserted into the database in time order.  This way we know that
    # picking an event range by time and by id will always return the same set
    # of events.
    for row in csv.reader(file(log_path)):
        event_list.append(parseRow(row, now))
        
        if len(event_list) > 2000:
            event_list.sort(key=lambda x: x[1][0])
            for event in event_list[:1000]:
                #conn.execute(insert_str % event[0], event[1])
                conn_execute(conn, insert_str % event[0], event[1])
            event_list = event_list[1000:]

    event_list.sort(key=lambda x: x[1][0])
    for event in event_list:
        #conn.execute(insert_str % event[0], event[1])
        conn_execute(conn, insert_str % event[0], event[1])
    conn.commit()


def getEventData(conn, select_str='*', where_list=None, orderBy=None, fetchall=False, **kwargs):
    """
    Examples of use:
        Total healing done to PCs:
        lambda timeline, index: timeline.getEventData(index, 'sum(amount) - sum(extra)', suffix='_HEAL', destType='PC').fetchone()[0]

        Total healing done to Bosses (like at Vezax):
        lambda timeline, index: timeline.getEventData(index, 'sum(amount) - sum(extra)', suffix='_HEAL', destType='NPC').fetchone()[0]
        
        If a given player cast something:
        lambda timeline, index: timeline.getEventData(index, 'count(*)', suffix=('_CAST_START', '_CAST_SUCCESS'), sourceName='Tantryst').fetchone()[0] != 0
    """
    if where_list is None:
        where_list = []

    sql_list = []
    arg_list = []
    for tup in where_list:
        #print "tup:", tup
        sql_list.append(tup[0])
        if len(tup) > 1:
            arg_list.append(tup[1])
        
    for k, v in sorted(kwargs.items()):
        if isinstance(v, tuple) or isinstance(v, list):
            if len(v) > 1:
                sql_list.append('''%s in (%s)''' % (k, ','.join(['?' for x in v])))
                arg_list.extend(tuple(v))
            else:
                sql_list.append('''%s = ?''' % k)
                arg_list.append(v[0])
        else:
            sql_list.append('''%s = ?''' % k)
            arg_list.append(v)
            
    if orderBy:
        orderBy = ' order by ' + orderBy
    else:
        orderBy = ''
    
    if fetchall:
        return conn_execute_fetchall(conn, ('''select %s from event where ''' % select_str) + ' and '.join(sql_list) + orderBy, tuple(arg_list))
    else:
        return conn_execute(conn, ('''select %s from event where ''' % select_str) + ' and '.join(sql_list) + orderBy, tuple(arg_list))


class ParseRun(DataRun):
    def __init__(self):
        DataRun.__init__(self, [], ['event'])


    def usage_setup(self, parser, **kwargs):
        if kwargs.get('date', True):
            parser.add_option("--date"
                    , help="Use DATE for standard log files and db names.  Overrides --db and --log."
                    , metavar="DATE"
                    , dest="date_str"
                    , action="store"
                    , type="str"
                    #, default="output"
                )
    
        if kwargs.get('log', True):
            parser.add_option("--log"
                    , help="Path to the WoWCombatLog.txt file."
                    , metavar="LOGFILE"
                    , dest="log_path"
                    , action="store"
                    , type="str"
                    #, default="output"
                )
    
    def usage_defaults(self, options):
        if options.date_str:
            options.log_path = glob.glob(os.path.join(config.wowspi_path, 'data', 'logs', '*' + options.date_str + '*'))[0]
            options.db_path = os.path.join(config.wowspi_path, 'data', 'parses', options.date_str + '.db')

        else:
            if hasattr(options, 'log_path') and re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', options.log_path):
                try:
                    options.log_path = (glob.glob(options.log_path) + glob.glob(os.path.join(config.wowspi_path, 'data', 'logs', '*' + options.log_path + '*')))[0]
                except:
                    pass
                
            if hasattr(options, 'db_path') and re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', options.db_path):
                options.db_path = os.path.join(config.wowspi_path, 'data', 'parses', options.db_path + '.db')


    def impl(self, options):
        print datetime.datetime.now(), "Parsing %s --> %s" % (options.log_path, options.db_path)
        parseLog(self.conn, options.log_path)
ParseRun() # This sets up the dict of runners so that we don't have to call them in __init__


if __name__ == "__main__":
    ParseRun().main(sys.argv[1:])
    #options, arguments = usage(sys.argv[1:])
    #sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof
