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

import basicparse
import armoryutils

#from sqliteutils import conn_execute, DurationManager
from sqliteutils import *

#def usage(sys_argv):
#    #op = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
#    #usage_setup(op)
#    #basicparse.usage_setup(op)
#    #return op.parse_args(sys_argv)
#
#    parser = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
#    module_list = ['basicparse']
#
#    usage_setup(parser)
#    for module in module_list:
#        globals()[module].usage_setup(parser)
#    
#    options, arguments = parser.parse_args(sys_argv)
#    
#    for module in module_list:
#        globals()[module].usage_defaults(options)
#    usage_defaults(options)
#
#    return options, arguments
#
#
#def usage_setup(op, **kwargs):
#    pass
#
#def usage_defaults(options):
#    pass


class LogSegment(object):
    def __init__(self, event, closeDelay=5):
        self.event_list = [event]
        self.closeDelay = closeDelay
        self.closeEvent = None
        self.npcEvent = None
        self.releaseEvent = None
        self.actor_set = set()
        self.db_id = 0

    def addEvent(self, event):
        if event['eventType'] == 'SPELL_AURA_APPLIED' and event['spellName'] == 'Swift Spectral Gryphon':
            self.releaseEvent = event
        else:
            self.event_list.append(event)

            if not self.npcEvent:
                if event['sourceType'] == 'NPC' and event['destType'] == 'PC' and event['suffix'] == '_DAMAGE':
                    self.npcEvent = event
                elif event['sourceType'] == 'PC' and event['destType'] == 'NPC' and event['suffix'] == '_DAMAGE':
                    self.npcEvent = event

            try:
                if event['eventType'] == 'UNIT_DIED' and event['destType'] == 'PC' and event['fakeDeath'] != 1:
                    self.closeEvent = event
                elif event['suffix'] in ('_SUMMON', '_RESURRECT') and event['sourceType'] == 'PC':
                    self.closeEvent = event
            except Exception, e:
                print e
                print event.keys()
                print event

            if event['suffix'] == '_DAMAGE' or event['suffix'] == '_HEAL':
                try:
                    self.actor_set.add(event['sourceType'] + "/" + event['sourceName'])
                except:
                    pass
                try:
                    self.actor_set.add(event['destType'] + "/" + event['destName'])
                except:
                    pass

    def finalizeClose(self, conn, combat_id):
        if not self.closeEvent:
            self.closeEvent = self.event_list[-1]

    def isOpen(self):
        if self.releaseEvent:
            return False
        
        if not self.npcEvent and self.event_list[-1]['time'] - self.event_list[0]['time'] > datetime.timedelta(seconds=self.closeDelay):
            return False

        if not self.closeEvent:
            return True

        return datetime.timedelta(seconds=self.closeDelay) > self.event_list[-1]['time'] - self.closeEvent['time']

    #def lastEvent(self):
    #    return self.event_list[-1]

    def prune(self, require_set):
        #print require_set.intersection(self.actor_set)
        
        if self.npcEvent:
            return require_set.intersection(self.actor_set)
        else:
            return set()

    def __repr__(self):
        return "<LogSegment %s> %s - %s" % (self.db_id, self.event_list[0]['time'], self.event_list[-1]['time'])


class LogCombat(object):
    def __init__(self, event, closeDelay=60):
        global combat_counter
        
        self.segment_list = [LogSegment(event)]
        self.closeDelay = closeDelay
        self.closeEvent = None
        self.openEvent = None
        self.instance_str = None
        self.encounter_str = None

    def addEvent(self, event):
        if self.segment_list[-1].isOpen():
            self.segment_list[-1].addEvent(event)
        else:
            self.segment_list.append(LogSegment(event))

        if event['eventType'] == 'SWING_DAMAGE' or event['eventType'] == 'SPELL_DAMAGE':
            self.closeEvent = event

            if not self.openEvent and event['destType'] == 'NPC':
                self.openEvent = event

    def isOpen(self):
        if not self.closeEvent:
            return True

        return datetime.timedelta(seconds=self.closeDelay) > self.segment_list[-1].event_list[-1]['time'] - self.closeEvent['time']

    def prune(self, require_set):
        tmp_list = list(self.segment_list)
        
        self.segment_list = []
        for segment in tmp_list:
            actor_set = segment.prune(require_set)
            
            if actor_set:
                self.segment_list.append(segment)
                
                for actor_str in actor_set:
                    actor_str = actor_str.split('/', 1)[-1]
                    if not self.instance_str:
                        self.instance_str = armoryutils.instanceByMob(actor_str)
                    if not self.encounter_str:
                        self.encounter_str = armoryutils.encounterByMob(actor_str)
                        
        while self.segment_list and self.segment_list[-1].npcEvent is None:
            self.segment_list.pop()

        return self.segment_list


    def finalizeClose(self, conn, require_set):
        self.db_id = conn_execute(conn, '''insert into combat (start_event_id, close_event_id, end_event_id, instance, encounter) values (?, ?, ?, ?, ?)''', \
                (self.segment_list[0].event_list[0]['id'], self.closeEvent['id'], self.segment_list[-1].event_list[-1]['id'], self.instance_str, self.encounter_str)).lastrowid
        
        for segment in self.segment_list:
            segment.finalizeClose(conn, self.db_id)
            
        conn_execute(conn, '''update event set combat_id = ? where id >= ? and id <= ?''', (self.db_id, self.segment_list[0].event_list[0]['id'], self.segment_list[-1].event_list[-1]['id']))

        role_sql = '''select name, sum(d) damage, sum(h) healing, sum(v) overhealed from (
            select sourceName name, sum(amount) - sum(extra) d, 0 h, 0 v from event where sourceType='PC' and suffix='_DAMAGE' and combat_id=? group by sourceName
            union
            select sourceName name, 0 d, sum(amount) - sum(extra) h, 0 v from event where sourceType='PC' and suffix='_HEAL' and combat_id=? group by sourceName
            union
            select destName name,   0 d, 0 h, sum(amount) v from event where destType='PC' and suffix='_HEAL' and combat_id=? group by destName
            ) group by name order by damage desc;'''

        dps_list = []
        healer_list = []
        tank_list = []
        for row in conn_execute(conn, role_sql, tuple([self.db_id, self.db_id, self.db_id])):
            if row['healing'] > row['damage']:
                healer_list.append((row['name'], row['healing']))
            elif row['damage'] > row['overhealed']:
                dps_list.append((row['name'], row['damage']))
            else: #if row['overhealed'] > row['healing'] and row['overhealed'] > row['damage']:
                tank_list.append((row['name'], row['overhealed']))
                    
                    
        # Time for wipe detection!
        healer_set = set([x[0] for x in healer_list])
        tank_set = set([x[0] for x in tank_list])
        dps_set = set([x[0] for x in dps_list])
        
        raidSize_int = len(healer_set) + len(tank_set) + len(dps_set)
        conn_execute(conn, '''update combat set size = ?, dps_list = ?, healer_list = ?, tank_list = ? where id = ?''', (raidSize_int, dps_list, healer_list, tank_list, self.db_id))
        conn.commit()


    def eventIter(self):
        return itertools.chain.from_iterable([x.event_list for x in self.segment_list])

    def reversedIter(self):
        return itertools.chain.from_iterable(reversed([x.event_list for x in reversed(self.segment_list)]))

    def __repr__(self):
        return "<LogCombat %s> %d segments\n%s" % (self.db_id, len(self.segment_list), "\n".join(["\t\t%d: %s" % (i, repr(x)) for i, x in enumerate(self.segment_list)]))


class CombatRun(DataRun):
    def __init__(self):
        DataRun.__init__(self, ['ParseRun', 'FakeDeathRun'], ['combat'])
        self.version = datetime.datetime.now()
        
    def impl(self, options):
        basicparse.sqlite_insureColumns(self.conn, 'event', [('combat_id', 'int'), #('segment_id', 'int'), 
                #('wound_dict', 'json'), ('active_dict', 'json'),
                ('absorbType', 'str'), ('absorbName', 'str'),
                #('healersHealing', 'int default 0'), ('healersDead', 'int default 0'), ('tanksDead', 'int default 0'), ('dpsDead', 'int default 0'), ('wipe', 'int default 0'),
            ])
        
        conn_execute(self.conn, '''drop index if exists ndx_event_combat_time''')
        conn_execute(self.conn, '''drop index if exists ndx_event_combat_source_time''')
        conn_execute(self.conn, '''update event set combat_id = ?''', (0,))
        conn_execute(self.conn, '''create index ndx_event_combat_time on event (combat_id, time)''')
        conn_execute(self.conn, '''create index ndx_event_combat_source_time on event (combat_id, sourceType, sourceName, time)''')
        conn_execute(self.conn, '''create index ndx_event_combat_suffix_spell on event (combat_id, suffix, sourceName)''')
        
        #conn_execute(self.conn, '''drop table if exists combat''')
        conn_execute(self.conn, '''create table combat (id integer primary key, start_event_id, close_event_id, end_event_id, size int, instance, encounter, dps_list json, healer_list json, tank_list json)''')
    
        #conn_execute(self.conn, '''drop table if exists segment''')
        #conn_execute(self.conn, '''create table segment (id integer primary key, start_event_id, close_event_id, end_event_id, combat_id)''')
    
        #conn_execute(self.conn, '''drop table if exists actor''')
        #conn_execute(self.conn, '''create table actor (id integer primary key, actorType, actorName, class)''')
    
        #conn_execute(self.conn, '''drop table if exists auralist''')
        #conn_execute(self.conn, '''drop table if exists aura''')
        #conn_execute(self.conn, '''create table aura (id integer primary key, start_event_id int, end_event_id int, start_time timestamp, end_time timestamp, sourceType str, sourceName str, destType str, destName str, spellName str, spellId int)''')
        #conn_execute(self.conn, '''create index ndx_aura_time on aura (start_time, end_time, spellName, destName)''')
        #conn_execute(self.conn, '''create index ndx_aura_name_time on aura (spellName, start_time, end_time, destName)''')
        #conn_execute(self.conn, '''create index ndx_aura_dest on aura (destType, destName, spellName, start_time, end_time)''')
        #conn_execute(self.conn, '''create index ndx_aura_id on aura (start_event_id)''')
        self.conn.commit()
        
        
        print datetime.datetime.now(), "Building combats..."
        require_set = set()
        for name_str in armoryutils.getAllMobs():
            require_set.add('NPC/' + name_str)
            require_set.add('Mount/' + name_str)
            
        combat_list = []
        combat = None
        
        cur = self.conn.cursor()
        cur.execute('''select * from event order by id''')
        event_list = cur.fetchmany()
        
        # This loop is structured oddly so that we don't have to pull in all
        # of the event list into memory at once.  Otherwise, four hours of
        # tens raiding would consume about 400MB of RAM, and that won't work
        # for hosted solutions.
        # Note that combat.finalizeClose has to mess with the DB, so we can't
        # have statements in progress while we fiddle with it.
        while event_list:
            event = event_list.pop(0)
        
            if not combat:
                combat = LogCombat(event)
            elif combat.isOpen():
                combat.addEvent(event)
            else:
                del cur
                
                if combat.prune(require_set):
                    combat.finalizeClose(self.conn, require_set)
                    self.conn.commit()
                    
                del combat
                combat = None
                    
                cur = self.conn.cursor()
                cur.execute('''select * from event where id >= ? order by id''', (event['id'],))
                event_list = []
                
            if not event_list:
                event_list = cur.fetchmany()
                
        del cur
        

    def usage_setup(self, parser, **kwargs):
        if kwargs.get('armorydb', True):
            parser.add_option("--armorydb"
                    , help="Desired sqlite database output file name."
                    , metavar="DB"
                    , dest="armorydb_path"
                    , action="store"
                    , type="str"
                    , default="armory.db"
                )
    
        if kwargs.get('realm', True):
            parser.add_option("--realm"
                    , help="Realm to use for armory data queries."
                    , metavar="REALM"
                    , dest="realm_str"
                    , action="store"
                    , type="str"
                    , default="Proudmoore"
                )
        
        if kwargs.get('region', True):
            parser.add_option("--region"
                    , help="Region to use for armory data queries (www, eu, kr, cn, tw)."
                    , metavar="REGION"
                    , dest="region_str"
                    , action="store"
                    , type="str"
                    , default="www"
                )        
CombatRun() # This sets up the dict of runners so that we don't have to call them in __init__


class FakeDeathRun(DataRun):
    def __init__(self):
        DataRun.__init__(self, ['ParseRun'], [])
        
    def impl(self, options):
        print datetime.datetime.now(), "Flagging fake deaths..."
        #flagFakeDeaths(self.conn)
        
        sqlite_insureColumns(self.conn, 'event', [('fakeDeath', 'int default 0')])
        
        update_list = []
        
        for event in basicparse.getEventData(self.conn, orderBy='time', eventType='UNIT_DIED', destType='PC'):
            where_list = []
            where_list.append(('time >= ?', event['time'] - datetime.timedelta(seconds=0.5)))
            where_list.append(('time <= ?', event['time'] + datetime.timedelta(seconds=0.5)))
            
            buffsLost_int = basicparse.getEventData(self.conn, 'count(*)', where_list, destType='PC', destName=event['destName'], eventType='SPELL_AURA_REMOVED').fetchone()[0]
            
            if buffsLost_int < 10:
                update_list.append(('''update event set fakeDeath = 1 where id = ?''', (event['id'],)))
                
        for sql_str, values_tup in update_list:
            conn_execute(self.conn, sql_str, values_tup)
        self.conn.commit()
FakeDeathRun() # This sets up the dict of runners so that we don't have to call them in __init__
        

#def main(sys_argv, options, arguments):
#    try:
#        conn = sqlite_connection(options)
#        
#        WipeRun(conn).execute(options, options.force)
#        #FakeDeathRun(conn).execute(options, options.force)
#
#    finally:
#        sqlite_print_perf(options.verbose)
#        pass



if __name__ == "__main__":
    CombatRun().main(sys.argv[1:])
    #options, arguments = usage(sys.argv[1:])
    #sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof
