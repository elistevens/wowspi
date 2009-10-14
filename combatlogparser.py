#!/usr/bin/env python

import cgi
import collections
import copy
import csv
import datetime
import itertools
import json
import optparse
import random
import re
import sqlite3
import sys
import time
import urllib
import urllib2



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
    op = optparse.OptionParser()
    usage_setup(op)
    return op.parse_args(sys_argv)

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
        
    


fixed_list = ['sourceGUID', 'sourceName', 'sourceFlags', 'destGUID', 'destName', 'destFlags']

# Note: order is important here, because 'SPELL' is a prefix for 'SPELL_XXX', the rest are in rough priority order
prefix_list = [
        ('SPELL_PERIODIC',      ['spellId', 'spellName', 'spellSchool']),
        ('SPELL_BUILDING',      ['spellId', 'spellName', 'spellSchool']),
        ('SPELL',               ['spellId', 'spellName', 'spellSchool']),
        ('SWING',               []),
        ('DAMAGE',              ['spellId', 'spellName', 'spellSchool']),
        ('RANGE',               ['spellId', 'spellName', 'spellSchool']),
        ('ENVIRONMENTAL',       ['environmentalType']),
        ('ENCHANT',             ['spellName', 'itemID', 'itemName']),
        ('UNIT',                []),
        ('PARTY',               []),
    ]
prefix_dict = dict(prefix_list)

# See: _DAMAGE vs. _DURABILITY_DAMAGE
suffix_list = [
        ('_DAMAGE',             ['amount', 'extra', 'school', 'resisted', 'blocked', 'absorbed', 'critical', 'glancing', 'crushing']),
        ('_MISSED',             ['missType', '?amount']),
        ('_HEAL',               ['amount', 'extra', 'absorbed', 'critical']),
        ('_ENERGIZE',           ['amount', 'powerType']),
        ('_DRAIN',              ['amount', 'powerType', 'extra']),
        ('_LEECH',              ['amount', 'powerType', 'extra']),
        ('_INTERRUPT',          ['extraSpellID', 'extraSpellName', 'extraSchool']),
        ('_DISPEL',             ['extraSpellID', 'extraSpellName', 'extraSchool', 'auraType']),
        ('_DISPEL_FAILED',      ['extraSpellID', 'extraSpellName', 'extraSchool']),
        ('_STOLEN',             ['extraSpellID', 'extraSpellName', 'extraSchool', 'auraType']),
        ('_EXTRA_ATTACKS',      ['amount']),
        ('_AURA_APPLIED',       ['auraType']),
        ('_AURA_REMOVED',       ['auraType']),
        ('_AURA_APPLIED_DOSE',  ['auraType', 'amount']),
        ('_AURA_REMOVED_DOSE',  ['auraType', 'amount']),
        ('_AURA_REFRESH',       ['auraType']),
        ('_AURA_BROKEN',        ['auraType']),
        ('_AURA_BROKEN_SPELL',  ['extraSpellID', 'extraSpellName', 'extraSchool', 'auraType']),
        ('_CAST_START',         []),
        ('_CAST_SUCCESS',       []),
        ('_CAST_FAILED',        ['failedType']),
        ('_INSTAKILL',          []),
        ('_DURABILITY_DAMAGE',  []),
        ('_DURABILITY_DAMAGE_ALL',  []),
        ('_CREATE',             []),
        ('_SUMMON',             []),
        ('_RESURRECT',          []),
        ('_SPLIT',              ['amount', 'extra', 'school', 'resisted', 'blocked', 'absorbed', 'critical', 'glancing', 'crushing']),
        ('_SHIELD',             ['amount', 'extra', 'school', 'resisted', 'blocked', 'absorbed', 'critical', 'glancing', 'crushing']),
        ('_SHIELD_MISSED',      ['missType', '?amount']),
        ('_REMOVED',            []),
        ('_APPLIED',            []),
        ('_DIED',               []),
        ('_DESTROYED',          []),
        ('_KILL',               []),
    ]
suffix_dict = dict(suffix_list)



actor_dict = {
        0x0000000000000000: 'PC',
        0x0010000000000000: 'Obj',
        0x0030000000000000: 'NPC',
        0x0040000000000000: 'Pet',
        0x0050000000000000: 'Mount',
        #0x0010000000000000: '1???',
        #0x0050000000000000: '5???'
    }

def actorType(guid):
    return actor_dict.get(0x00F0000000000000 & guid, 'unknown:' + hex(0x00F0000000000000 & guid))

eventSeen_dict = {}
spellSeen_dict = {}
actorSeen_dict = {}

time_re = re.compile('(\\d+)/(\\d+) (\\d+):(\\d+):(\\d+).(\\d+)')



def parseRow(row):
    """
    10/21 20:59:04.831  SWING_DAMAGE,0x0000000002B0C69C,"Biggdog",0x514,0xF130005967003326,"High Warlord Naj'entus",0xa48,171,0,1,0,0,0,nil,1,nil
    10/21 20:59:04.873  SPELL_DAMAGE,0x000000000142C9BE,"Autogun",0x514,0xF130005967003326,"High Warlord Naj'entus",0xa48,27209,"Shadow Bolt",0x20,2233,0,32,220,0,0,nil,nil,nil
    """
    #print row

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

        for actor_str in ('source', 'dest'):
            if event[actor_str + 'GUID']:
                actorType_str = actorType(event[actor_str + 'GUID'])
                event[actor_str + 'Type'] = actorType_str
                event[actor_str + actorType_str] = True

        return event
    except:
        #print rowCopy
        raise



def sqlite_parseLog(conn, log_path, force=False):
    if not force:
        #print "trying to skip..."
        try:
            #print conn.execute('''select count(*) from event where path = ?''', (db_path,)).fetchone(), conn.execute('''select count(*) from event''').fetchone()
            if conn.execute('''select count(*) from event where path = ?''', (log_path,)).fetchone()[0] > 0:
            #if conn.execute('''select count(*) from event''').fetchone()[0] > 0:
                #print "skipping..."
                return
        except Exception, e:
            #print e
            pass

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
                
    col_list = ['time', 'eventType', 'prefix', 'suffix', 'sourceType', 'destType'] + list(fixed_list) + col_list


    #print col_list

    col_str = ', '.join(col_list)
    qmk_str = ', '.join(['?' for x in col_list])
    insert_str = '''insert into event (path, %s) values (?, %s)''' % (col_str, qmk_str)

    conn.execute('''drop table if exists event''')
    
    #print ('''create table event (id integer primary key, path, %s, fragment_id int, combat_id int, wound_dict json, active_dict json)''' % col_str).replace('time,', 'time timestamp,',)
    
    conn.execute(('''create table event (id integer primary key, path, %s)''' % col_str).replace('time,', 'time timestamp,',))
    conn.execute('''create index ndx_time on event (time)''')

    # FIXME: 'file' should be some flavor of 'codecs.open' for int'l regions
    for row in csv.reader(file(log_path)):
        event = parseRow(row)
        conn.execute(insert_str, tuple([log_path] + [event.get(x, None) for x in col_list]))
        
    conn.commit()

def sqlite_connection(options):
    conn = sqlite3.connect(options.db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    
    return conn
    
def sqlite_insureColumns(conn, table_str, column_list):
    col_set = set(conn.execute('''select * from %s limit 1''' % table_str).fetchone().keys())
    
    for col_str, def_str in column_list:
        if col_str not in col_set:
            conn.execute('''alter table %s add column %s %s''' % (table_str, col_str, def_str))
            

def main(sys_argv, options, arguments):
    #if not options.db_path:
    #    db_path = options.log_path + ".db"
    #else:
    #    db_path = options.db_path

    print datetime.datetime.now(), "Parsing %s --> %s" % (options.log_path, options.db_path)
    conn = sqlite_connection(options)
    sqlite_parseLog(conn, options.log_path, options.force)





if __name__ == "__main__":
    options, arguments = usage(sys_argv)
    sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof
