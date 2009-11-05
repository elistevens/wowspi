#!/usr/bin/env python

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



def usage(sys_argv):
    op = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
    usage_setup(op)
    
    options, arguments = op.parse_args(sys_argv)
    
    usage_defaults(options)
    
    return options, arguments

def usage_setup(op, **kwargs):
    if kwargs.get('force', True):
        op.add_option("--force"
                , help="Force reparsing from scratch."
                #, metavar="OUTPUT"
                , dest="force"
                , action="store_true"
                #, type="str"
                #, default="output"
            )

    if kwargs.get('date', True):
        op.add_option("--date"
                , help="Use DATE for standard log files and db names.  Overrides --db and --log."
                , metavar="DATE"
                , dest="date_str"
                , action="store"
                , type="str"
                #, default="output"
            )

    if kwargs.get('db', True):
        op.add_option("--db"
                , help="Desired sqlite database output file name."
                , metavar="OUTPUT"
                , dest="db_path"
                , action="store"
                , type="str"
                #, default="output"
            )

    if kwargs.get('log', True):
        op.add_option("--log"
                , help="Path to the WoWCombatLog.txt file."
                , metavar="LOGFILE"
                , dest="log_path"
                , action="store"
                , type="str"
                #, default="output"
            )
        
    if kwargs.get('verbose', True):
        op.add_option("-v", "--verbose"
                , help="Print more output; may include debugging information not intended for end-users."
                #, metavar="OUTPUT"
                , dest="verbose"
                , action="store_true"
                #, type="str"
                , default=False
            )


def usage_defaults(options):
    #print "before", options
    if options.date_str:
        #print "in date_str", options.date_str
        
        options.log_path = glob.glob(os.path.join(config.wowspi_path, 'data', 'logs', '*' + options.date_str + '*'))[0]
        options.db_path = os.path.join(config.wowspi_path, 'data', 'parses', options.date_str + '.db')
        
        #print options
    else:
        if hasattr(options, 'log_path') and re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', options.log_path):
            try:
                options.log_path = (glob.glob(options.log_path) + glob.glob(os.path.join(config.wowspi_path, 'data', 'logs', '*' + options.log_path + '*')))[0]
            except:
                pass
            
        if hasattr(options, 'db_path') and re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', options.db_path):
            options.db_path = os.path.join(config.wowspi_path, 'data', 'parses', options.db_path + '.db')

    #return options, arguments
    


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



flags_dict = {
        ('Type', 0x0000FC00): {
            0x00004000: 'Object',
            0x00002000: 'Guardian',
            0x00001000: 'Pet',
            0x00000800: 'NPC',
            0x00000400: 'PC',
        },
        ('Controller', 0x00000300): {
            0x00000200: 'NPC',
            0x00000100: 'PC',
        },
        ('Reaction', 0x000000F0): {
            0x00000040: 'Hostile',
            0x00000020: 'Neutral',
            0x00000010: 'Friendly',
        },
    }

def parseFlags(pre_str, event):
    for post_str, mask in flags_dict:
        bits = event[pre_str + 'Flags'] & mask
        
        event[pre_str + post_str] = flags_dict[(post_str, mask)].get(bits, 'Unknown:%x' % bits)



time_re = re.compile('(\\d+)/(\\d+) (\\d+):(\\d+):(\\d+).(\\d+)')

def parseRow(row):
    """
    10/21 20:59:04.831  SWING_DAMAGE,0x0000000002B0C69C,"Biggdog",0x514,0xF130005967003326,"High Warlord Naj'entus",0xa48,171,0,1,0,0,0,nil,1,nil
    10/21 20:59:04.873  SPELL_DAMAGE,0x000000000142C9BE,"Autogun",0x514,0xF130005967003326,"High Warlord Naj'entus",0xa48,27209,"Shadow Bolt",0x20,2233,0,32,220,0,0,nil,nil,nil
    """
    #print row
    
    #tmp = []
    #for x in row:
    #    if isinstance(x, str):
    #        tmp.append(unicode(x, 'utf8'))
    #    else:
    #        tmp.append(x)
    #row = tmp

    rowCopy = list(row)
    event = {}

    try:
        date_str, time_str, eventType_str = row.pop(0).split()

        event['eventType'] = eventType_str

        tmp_list = time_str.split(".")
        time_list = [int(x) for x in date_str.split('/') + tmp_list[0].split(':') + [tmp_list[1]]]

        event['time'] = datetime.datetime(datetime.datetime.now().year, time_list[0], time_list[1], time_list[2], time_list[3], time_list[4], time_list[5] * 1000)
        if event['time'] > datetime.datetime.now():
            event['time'] = datetime.datetime(datetime.datetime.now().year - 1, time_list[0], time_list[1], time_list[2], time_list[3], time_list[4], time_list[5] * 1000)

        for col in fixed_list:
            event[col] = row.pop(0)

        event['prefix'] = ''
        for prefix_tup in prefix_list:
            if eventType_str.startswith(prefix_tup[0]):
                event['prefix'] = prefix_tup[0]
                for col in prefix_tup[1]:
                    event[col] = row.pop(0)
                break

        event['suffix'] = event['eventType'][len(event['prefix']):]
        for col in suffix_dict[event['suffix']]:
            if col.startswith('?'):
                col = col[1:]
                if row:
                    event[col] = row.pop(0)
            else:
                event[col] = row.pop(0)

        assert len(row) == 0, (row, rowCopy)

        tmp = {}
        tmp.update(event)
        for key, value in tmp.items():
            if value == 'nil':
                event[key] = None
            elif isinstance(value, str):
                if value.startswith('0x'):
                    event[key] = int(value[2:], 16)
                elif re.match(r"^-?\d+$", value):
                    event[key] = int(value)
                else:
                    event[key] = unicode(value, 'utf8')
            #else:
            #    print repr(key), repr(value)

        for actor_str in ('source', 'dest'):
            parseFlags(actor_str, event)
            
            #if event[actor_str + 'GUID']:
            #    actorType_str = actorType(event[actor_str + 'GUID'])
            #    event[actor_str + 'Type'] = actorType_str
            #    event[actor_str + actorType_str] = True

        return event
    except:
        #print rowCopy
        raise



def parseLog(conn, log_path, force=False):
    if not force:
        #print "trying to skip..."
        try:
            #print conn_execute(conn, '''select count(*) from event where path = ?''', (db_path,)).fetchone(), conn_execute(conn, '''select count(*) from event''').fetchone()
            if conn_execute(conn, '''select 1 from event where path = ? limit 1''', (log_path,)).fetchone()[0] > 0:
            #if conn_execute(conn, '''select count(*) from event''').fetchone()[0] > 0:
                #print "skipping..."
                return
        except Exception, e:
            #print e
            pass
    else:
        print datetime.datetime.now(), "With --force, parsing events"

    #col_list = ['time', 'eventType', 'prefix', 'suffix'] + list(fixed_list)
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
                
    col_list.sort()
                
    col_list = ['time', 'eventType', 'prefix', 'suffix', 'sourceType', 'sourceController', 'sourceReaction', 'destType', 'destController', 'destReaction'] + list(fixed_list) + col_list


    #print col_list

    col_str = ', '.join(col_list)
    qmk_str = ', '.join(['?' for x in col_list])
    insert_str = '''insert into event (path, %s) values (?, %s)''' % (col_str, qmk_str)

    conn_execute(conn, '''drop table if exists event''')
    
    #print ('''create table event (id integer primary key, path, %s, fragment_id int, combat_id int, wound_dict json, active_dict json)''' % col_str).replace('time,', 'time timestamp,',)
    
    conn_execute(conn, ('''create table event (id integer primary key, path, %s)''' % col_str).replace('time,', 'time timestamp,',))
    conn_execute(conn, '''create index ndx_event_time_sourceName on event (time, sourceName)''')

    # FIXME: 'file' should be some flavor of 'codecs.open' for int'l regions
    for row in csv.reader(file(log_path)):
        event = parseRow(row)
        conn_execute(conn, insert_str, tuple([log_path] + [event.get(x, None) for x in col_list]))
        
    conn.commit()
    
def flagFakeDeaths(conn):
    sqlite_insureColumns(conn, 'event', [('fakeDeath', 'int default 0')])
    
    update_list = []
    
    for event in getEventData(conn, orderBy='time', eventType='UNIT_DIED', destType='PC'):
        where_list = []
        where_list.append(('time >= ?', event['time'] - datetime.timedelta(seconds=0.5)))
        where_list.append(('time <= ?', event['time'] + datetime.timedelta(seconds=0.5)))
        
        buffsLost_int = getEventData(conn, 'count(*)', where_list, destType='PC', destName=event['destName'], eventType='SPELL_AURA_REMOVED').fetchone()[0]
        
        if buffsLost_int < 10:
            update_list.append(('''update event set fakeDeath = 1 where id = ?''', (event['id'],)))
            
    for sql_str, values_tup in update_list:
        conn_execute(conn, sql_str, values_tup)
    conn.commit()


def getEventData(conn, select_str='*', where_list=None, orderBy=None, **kwargs):
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
    
    #where_list.append(('''time >= ?''', self.start_dt + (self.width_td * index)))
    #where_list.append(('''time < ?''',  self.start_dt + (self.width_td * (index+1))))

    sql_list = []
    arg_list = []
    for tup in where_list:
        #print "tup:", tup
        sql_list.append(tup[0])
        if len(tup) > 1:
            arg_list.append(tup[1])
        
    for k, v in sorted(kwargs.items()):
        if isinstance(v, tuple):
            sql_list.append('''%s in (%s)''' % (k, ','.join(['?' for x in v])))
            arg_list.extend(v)
        elif isinstance(v, list):
            sql_list.append('''%s in (%s)''' % (k, ','.join(['?' for x in v])))
            arg_list.extend(tuple(v))
        else:
            sql_list.append('''%s = ?''' % k)
            arg_list.append(v)
            
    if orderBy:
        orderBy = ' order by ' + orderBy
    else:
        orderBy = ''
        
    #print sql_list
    #print arg_list
    #
    #print ('''select %s from event where ''' % select_str) + ' and '.join(sql_list) + orderBy, tuple(arg_list)
    return conn_execute(conn, ('''select %s from event where ''' % select_str) + ' and '.join(sql_list) + orderBy, tuple(arg_list))


def main(sys_argv, options, arguments):
    #if not options.db_path:
    #    db_path = options.log_path + ".db"
    #else:
    #    db_path = options.db_path
    
    
    #print options

    print datetime.datetime.now(), "Parsing %s --> %s" % (options.log_path, options.db_path)
    conn = sqlite_connection(options)
    parseLog(conn, options.log_path, options.force)
    flagFakeDeaths(conn)





if __name__ == "__main__":
    options, arguments = usage(sys.argv[1:])
    sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof
