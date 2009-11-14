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

import basicparse
import armoryutils

from sqliteutils import conn_execute

def usage(sys_argv):
    op = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
    usage_setup(op)
    basicparse.usage_setup(op)
    return op.parse_args(sys_argv)

def usage_setup(op, **kwargs):
    pass
    #if kwargs.get('prune', True):
    #    op.add_option("--prune"
    #            , help="Prune the resulting combat encounters to only include those where the named actors were present (ex: 'Sartharion,Tenebron,Shadron,Vesperon').  Defaults to all T7-T9 raid bosses."
    #            , metavar="ACTOR"
    #            , dest="prune_str"
    #            , action="store"
    #            , type="str"
    #            , default="Sartharion,Malygos,Anub'Rekhan,Grand Widow Faerlina,Maexxna,Noth the Plaguebringer,Heigan the Unclean,Loatheb," +\
    #                      "Instructor Razuvious,Gothik the Harvester,Patchwerk,Grobbulus,Gluth,Thaddius,Sapphiron,Kel'Thuzad," +\
    #                      "Ignis the Furnace Master,Razorscale,XT-002 Deconstructor,Steelbreaker,Kologarn,Auriya,Aerial Command Unit,Leviathan Mk II,VX-001,Thorim,Hodir,Freya," +\
    #                      "General Vezax,Guardian of Yogg Saron,Crusher Tentacle,Corrupter Tentacle,Constrictor Tentacle,Yogg Saron" +\
    #                      "Gormok the Impaler,Acidmaw,Dreadscale,Icehowl,Lord Jaraxxus,Eydis Darkbane,Fjola Lightbane,Anub'arak,Nerubian Burrower,Onyxia" +\
    #                      "Gorgrim Shadowcleave,Birana Stormhoof,Erin Misthoof,Ruj'kah,Ginselle Blightslinger,Liandra Suncaller,Malithas Brightblade,Caiphus the Stern,Vivienne Blackwhisper,Maz'dinah,Broln Stouthorn,Thrakgar,Harkzog,Narrhok Steelbreaker",
    #        )
def usage_defaults(options):
    pass


class LogSegment(object):
    #aggregateKey_tup = ('amount', 'extra', 'resisted', 'blocked', 'absorbed')

    def __init__(self, event, closeDelay=5):
        global segment_counter
        
        self.event_list = [event]
        self.closeDelay = closeDelay
        self.closeEvent = None
        self.npcEvent = None
        self.releaseEvent = None
        #self.aggregate_dict = {}
        self.actor_set = set()
        self.db_id = 0
        
        #self.seenCombat_bool = False

    def addEvent(self, event):
        #if prefix_dict[event['prefix']][0] and suffix_dict[event['suffix']][0]:
        if event['eventType'] == 'SPELL_AURA_APPLIED' and event['spellName'] == 'Swift Spectral Gryphon':
            self.releaseEvent = event
        else:
            self.event_list.append(event)

            if not self.npcEvent:
                if event['sourceType'] == 'NPC' and event['destType'] == 'PC' and event['suffix'] == '_DAMAGE':
                    self.npcEvent = event
                elif event['sourceType'] == 'PC' and event['destType'] == 'NPC' and event['suffix'] == '_DAMAGE':
                    self.npcEvent = event

            if event['eventType'] == 'UNIT_DIED' and event['destType'] == 'PC' and event['fakeDeath'] != 1:
                self.closeEvent = event
            elif event['suffix'] in ('_SUMMON', '_RESURRECT') and event['sourceType'] == 'PC':
                self.closeEvent = event

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

        self.db_id = conn_execute(conn, '''insert into segment (start_event_id, close_event_id, end_event_id, combat_id) values (?, ?, ?, ?)''', \
                (self.event_list[0]['id'], self.closeEvent['id'], self.event_list[-1]['id'], combat_id)).lastrowid
        
        #for event in self.event_list:
        #    conn_execute(conn, '''update event set combat_id = ?, segment_id = ? where id = ?''', (combat_id, self.db_id, event['id']))
            
        conn_execute(conn, '''update event set combat_id = ?, segment_id = ? where time >= ? and time <= ?''', (combat_id, self.db_id, self.event_list[0]['time'], self.event_list[-1]['time']))
        
        #conn.commit()

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

        #if not self.isOpen():
        #    self.finalizeClose(conn, require_set)

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
        #self.segment_list = [x for x in self.segment_list if x.prune(require_set)]
        #
        ##self.prune_set = set()
        #for x in self.segment_list:
        #    self.prune_set.update(x.prune(require_set))
        #
        ##print self.segment_list, self.prune_set
        return self.segment_list

    def finalizeClose(self, conn, require_set):
        self.db_id = conn_execute(conn, '''insert into combat (start_event_id, close_event_id, end_event_id, instance, encounter) values (?, ?, ?, ?, ?)''', \
                (self.segment_list[0].event_list[0]['id'], self.closeEvent['id'], self.segment_list[-1].event_list[-1]['id'], self.instance_str, self.encounter_str)).lastrowid
        
        actor_dict = dict([((x['actorType'], x['actorName']), x['id']) for x in conn_execute(conn, '''select id, actorType, actorName from actor''')])
        
        for segment in self.segment_list:
            segment.finalizeClose(conn, self.db_id)
            
        #conn.commit()
            
        wound_dict = {} #collections.defaultdict(int)
        active_dict = {}
        aura_dict = {}
        for event in self.eventIter():
            if event['destType'] == 'PC':
                wound_dict.setdefault(event['destName'], 0)
                
                if event['suffix'] == '_DAMAGE':
                    wound_dict[event['destName']] += event['amount'] - event['extra']
                elif event['suffix'] == '_HEAL':
                    wound_dict[event['destName']] -= event['amount'] - event['extra']
                    if event['extra'] > 0:
                        wound_dict[event['destName']] = -event['extra']

                if event['suffix'] == '_DIED' or wound_dict[event['destName']] <= 0:
                    del wound_dict[event['destName']]

            if event['sourceType'] == 'PC':
                if event['suffix'] == '_CAST_START':
                    active_dict[event['sourceName']] = event['spellName']
                elif 'sourceName' in active_dict and (event['suffix'] == '_CAST_SUCCESS' or event['suffix'] == '_CAST_FAILED'):
                    del active_dict[event['sourceName']]
                    
            # FIXME: This could probably be optimized with some clever time >= ? and time < ? stuff
            conn_execute(conn, '''update event set active_dict = ?, wound_dict = ? where id = ?''', (active_dict, wound_dict, event['id']))
            
            if event['sourceName'] and (event['sourceType'], event['sourceName']) not in actor_dict:
                actor_dict[(event['sourceType'], event['sourceName'])] = conn_execute(conn, '''insert into actor (actorType, actorName) values (?, ?)''', (event['sourceType'], event['sourceName'])).lastrowid
            if event['destName'] and (event['destType'], event['destName']) not in actor_dict:
                actor_dict[(event['destType'], event['destName'])] = conn_execute(conn, '''insert into actor (actorType, actorName) values (?, ?)''', (event['destType'], event['destName'])).lastrowid
                
            if event['eventType'] == 'SPELL_AURA_REMOVED':
                key = (event['destType'], event['destName'], event['spellName'], event['spellId'])
                
                if key in aura_dict:
                    conn_execute(conn, '''update aura set end_event_id = ?, end_time = ? where start_event_id = ?''', (event['id'], event['time'], aura_dict[key]['id']))
    
                    del aura_dict[key]

            elif event['eventType'] == 'SPELL_AURA_APPLIED':
                key = (event['destType'], event['destName'], event['spellName'], event['spellId'])
                
                #aura_dict[key].append((event['spellName'], event['id'], event['time'], event['destType'], event['destName']))
                
                #print repr(aura_dict[key][-1])
                conn_execute(conn, '''insert into aura (start_event_id, start_time, end_event_id, end_time, sourceType, sourceName, destType, destName, spellName, spellId) values (?,?,?,?,?,?,?,?,?,?)''',
                             (event['id'], event['time'], self.closeEvent['id'], self.closeEvent['time'], event['sourceType'], event['sourceName'], event['destType'], event['destName'], event['spellName'], event['spellId']))
                
                if key in aura_dict:
                    conn_execute(conn, '''update aura set end_event_id = ?, end_time = ? where start_event_id = ?''', (event['id'], event['time'], aura_dict[key]['id']))
    
                    del aura_dict[key]
                    
                aura_dict[key] = event
                

            
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
        
        healersDead_set = set()
        tanksDead_set = set()
        dpsDead_set = set()
        for event in self.eventIter():
            if event['eventType'] == 'UNIT_DIED' and event['destType'] == 'PC' and event['fakeDeath'] != 1:
                if event['destName'] in healer_set:
                    healersDead_set.add(event['destName'])
                elif event['destName'] in tank_set:
                    tanksDead_set.add(event['destName'])
                elif event['destName'] in dps_set:
                    dpsDead_set.add(event['destName'])
                    
                conn_execute(conn, '''update event set healersDead = ?, tanksDead = ?, dpsDead = ? where combat_id = ? and time >= ?''', (len(healersDead_set), len(tanksDead_set), len(dpsDead_set), self.db_id, event['time']))
            elif event['eventType'] == 'SPELL_RESURRECT' and event['destType'] == 'PC':
                #print "rez event:", event
                if event['destName'] in healersDead_set:
                    healersDead_set.remove(event['destName'])
                elif event['destName'] in tanksDead_set:
                    tanksDead_set.remove(event['destName'])
                elif event['destName'] in dpsDead_set:
                    dpsDead_set.remove(event['destName'])
                else:
                    print datetime.datetime.now(), "Unknown rez event:", event
                    
                conn_execute(conn, '''update event set healersDead = ?, tanksDead = ?, dpsDead = ? where combat_id = ? and time >= ?''', (len(healersDead_set), len(tanksDead_set), len(dpsDead_set), self.db_id, event['time']))
        conn.commit()
        
        healersHealing_set = set()
        update_list = []
        for event in basicparse.getEventData(conn, orderBy='time desc', combat_id=self.db_id, eventType='SPELL_HEAL', sourceType='PC', sourceName=tuple(healer_set)):
            
            if event['sourceName'] not in healersHealing_set:
                healersHealing_set.add(event['sourceName'])
                update_list.append(('''update event set healersHealing = ? where time <= ? and combat_id = ?''', (len(healersHealing_set), event['time'], self.db_id)))
            
            if healersHealing_set == healer_set:
                break
        
        for sql_str, values_tup in update_list:
            conn_execute(conn, sql_str, values_tup)
        conn.commit()
        
        dead_int = len(healersDead_set) + len(tanksDead_set) + len(dpsDead_set)
        
        # Do we need to bother?  If half of the raid is alive at the end, no.
        if raidSize_int and float(dead_int) / raidSize_int > 0.5:
            update_list = []
            for event in basicparse.getEventData(conn, orderBy='time', combat_id=self.db_id, healersDead=len(healer_set)):
                update_list.append(('''update event set wipe = 1 where time >= ? and combat_id = ?''', (event['time'], self.db_id)))
                break
                
            for event in basicparse.getEventData(conn, orderBy='time', combat_id=self.db_id, tanksDead=len(tank_set)):
                update_list.append(('''update event set wipe = 1 where time >= ? and combat_id = ?''', (event['time'], self.db_id)))
                break
                
            for event in basicparse.getEventData(conn, orderBy='time', combat_id=self.db_id, healersHealing=0):
                update_list.append(('''update event set wipe = 1 where time >= ? and combat_id = ?''', (event['time'], self.db_id)))
                break
                
            for sql_str, values_tup in update_list:
                conn_execute(conn, sql_str, values_tup)
            conn.commit()
            
            
            
            


    def eventIter(self):
        return itertools.chain.from_iterable([x.event_list for x in self.segment_list])

    def reversedIter(self):
        return itertools.chain.from_iterable(reversed([x.event_list for x in reversed(self.segment_list)]))

    def __repr__(self):
        return "<LogCombat %s> %d segments\n%s" % (self.db_id, len(self.segment_list), "\n".join(["\t\t%d: %s" % (i, repr(x)) for i, x in enumerate(self.segment_list)]))


def main(sys_argv, options, arguments):
    basicparse.main(sys_argv, options, arguments)
    conn = basicparse.sqlite_connection(options)
    
    if not options.force:
        try:
            if conn_execute(conn, '''select * from combat limit 1''').fetchone():
                print datetime.datetime.now(), "Skipping combat generation..."
                return
        except:
            pass

    try:
        basicparse.sqlite_insureColumns(conn, 'event', [('segment_id', 'int'), ('combat_id', 'int'),
                ('wound_dict', 'json'), ('active_dict', 'json'),
                ('absorbType', 'str'), ('absorbName', 'str'),
                ('healersHealing', 'int default 0'), ('healersDead', 'int default 0'), ('tanksDead', 'int default 0'), ('dpsDead', 'int default 0'), ('wipe', 'int default 0'),
            ])
        
        conn_execute(conn, '''drop index if exists ndx_event_combat_time''')
        conn_execute(conn, '''update event set segment_id = ?, combat_id = ?, wound_dict = ?, active_dict = ?''', (0, 0, {}, {}))
        conn_execute(conn, '''create index ndx_event_combat_time on event (combat_id, time)''')
        conn_execute(conn, '''create index ndx_event_combat_source_time on event (combat_id, sourceType, sourceName, time)''')
        
        conn_execute(conn, '''drop table if exists combat''')
        conn_execute(conn, '''create table combat (id integer primary key, start_event_id, close_event_id, end_event_id, size int, instance, encounter, dps_list json, healer_list json, tank_list json)''')
    
        conn_execute(conn, '''drop table if exists segment''')
        conn_execute(conn, '''create table segment (id integer primary key, start_event_id, close_event_id, end_event_id, combat_id)''')
    
        conn_execute(conn, '''drop table if exists actor''')
        conn_execute(conn, '''create table actor (id integer primary key, actorType, actorName, class)''')
    
        conn_execute(conn, '''drop table if exists auralist''')
        conn_execute(conn, '''drop table if exists aura''')
        conn_execute(conn, '''create table aura (id integer primary key, start_event_id int, end_event_id int, start_time timestamp, end_time timestamp, sourceType str, sourceName str, destType str, destName str, spellName str, spellId int)''')
        conn_execute(conn, '''create index ndx_aura_time on aura (start_time, end_time, spellName, destName)''')
        conn_execute(conn, '''create index ndx_aura_name_time on aura (spellName, start_time, end_time, destName)''')
        conn_execute(conn, '''create index ndx_aura_dest on aura (destType, destName, spellName, start_time, end_time)''')
        conn_execute(conn, '''create index ndx_aura_id on aura (start_event_id)''')
        conn.commit()
        
        
        print datetime.datetime.now(), "Building combats..."
        require_set = set()
        for name_str in armoryutils.getAllMobs():
            require_set.add('NPC/' + name_str)
            require_set.add('Mount/' + name_str)
            
        combat_list = []
        combat = None
        
        cur = conn.cursor()
        cur.execute('''select * from event order by time''')
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
                    combat.finalizeClose(conn, require_set)
                    conn.commit()
                    
                del combat
                combat = None
                    
                cur = conn.cursor()
                cur.execute('''select * from event where time >= ? order by time''', (event['time'],))
                event_list = []
                
            if not event_list:
                event_list = cur.fetchmany()
                
        del cur

    except:
        #try:
        #    conn_execute(conn, '''drop table if exists combat''')
        #except:
        #    pass
        raise


if __name__ == "__main__":
    options, arguments = usage(sys.argv[1:])
    sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof
