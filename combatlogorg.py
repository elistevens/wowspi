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

import combatlogparser


def usage(sys_argv):
    op = optparse.OptionParser()
    usage_setup(op)
    combatlogparser.usage_setup(op)
    return op.parse_args(sys_argv)

def usage_setup(op, **kwargs):
    if kwargs.get('prune', True):
        op.add_option("--prune"
                , help="Prune the resulting combat encounters to only include those where the named actors were present (ex: 'Sartharion,Tenebron,Shadron,Vesperon').  Defaults to all T7-T9 raid bosses."
                , metavar="ACTOR"
                , dest="prune_str"
                , action="store"
                , type="str"
                , default="Sartharion,Malygos,Anub'Rekhan,Grand Widow Faerlina,Maexxna,Noth the Plaguebringer,Heigan the Unclean,Loatheb," +\
                          "Instructor Razuvious,Gothik the Harvester,Patchwerk,Grobbulus,Gluth,Thaddius,Sapphiron,Kel'Thuzad," +\
                          "Ignis the Furnace Master,Razorscale,XT-002 Deconstructor,Steelbreaker,Kologarn,Auriya,Aerial Command Unit,Leviathan Mk II,VX-001,Thorim,Hodir,Freya," +\
                          "General Vezax,Guardian of Yogg Saron,Crusher Tentacle,Corrupter Tentacle,Constrictor Tentacle,Yogg Saron" +\
                          "Gormok the Impaler,Acidmaw,Dreadscale,Icehowl,Lord Jaraxxus,Eydis Darkbane,Fjola Lightbane,Anub'arak,Nerubian Burrower,Onyxia" +\
                          "Gorgrim Shadowcleave,Birana Stormhoof,Erin Misthoof,Ruj'kah,Ginselle Blightslinger,Liandra Suncaller,Malithas Brightblade,Caiphus the Stern,Vivienne Blackwhisper,Maz'dinah,Broln Stouthorn,Thrakgar,Harkzog,Narrhok Steelbreaker",
            )


class LogSegment(object):
    #aggregateKey_tup = ('amount', 'extra', 'resisted', 'blocked', 'absorbed')

    def __init__(self, event, closeDelay=10):
        global segment_counter
        
        self.event_list = [event]
        self.closeDelay = closeDelay
        self.closeEvent = None
        self.npcEvent = None
        #self.aggregate_dict = {}
        self.actor_set = set()
        self.db_id = 0

    def addEvent(self, event):
        #if prefix_dict[event['prefix']][0] and suffix_dict[event['suffix']][0]:
            self.event_list.append(event)

            if not self.npcEvent and event['sourceType'] == 'NPC':
                self.npcEvent = event

            if event['eventType'] == 'UNIT_DIED' and event['destType'] == 'PC':
                self.closeEvent = event
            elif event['suffix'] in ('_SUMMON', '_RESURRECT') and event['sourceType'] == 'PC':
                self.closeEvent = event

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

        self.db_id = conn.execute('''insert into segment (start_event_id, close_event_id, end_event_id, combat_id) values (?, ?, ?, ?)''', \
                (self.event_list[0]['id'], self.closeEvent['id'], self.event_list[-1]['id'], combat_id)).lastrowid
        
        for event in self.event_list:
            conn.execute('''update event set combat_id = ?, segment_id = ? where id = ?''', (combat_id, self.db_id, event['id']))
        #conn.commit()

    def isOpen(self):
        if not self.npcEvent and self.event_list[-1]['time'] - self.event_list[0]['time'] > datetime.timedelta(seconds=self.closeDelay):
            return False

        if not self.closeEvent:
            return True

        return datetime.timedelta(seconds=self.closeDelay) > self.event_list[-1]['time'] - self.closeEvent['time']

    #def lastEvent(self):
    #    return self.event_list[-1]

    def prune(self, require_set):
        #print [x for x in sorted(self.actor_set) if not x.startswith('PC/')]
        return require_set.intersection(self.actor_set)

    def __repr__(self):
        return "<LogSegment %s> %s - %s" % (self.db_id, self.event_list[0]['time'], self.event_list[-1]['time'])


class LogCombat(object):
    def __init__(self, event, closeDelay=60):
        global combat_counter
        
        self.segment_list = [LogSegment(event)]
        self.closeDelay = closeDelay
        self.closeEvent = None
        self.openEvent = None

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
        self.segment_list = [x for x in self.segment_list if x.prune(require_set)]

        self.prune_set = set()
        for x in self.segment_list:
            self.prune_set.update(x.prune(require_set))

        return self.segment_list

    def finalizeClose(self, conn, require_set):
        #if self.prune(require_set):
        
            self.db_id = conn.execute('''insert into combat (start_event_id, close_event_id, end_event_id) values (?, ?, ?)''', \
                    (self.segment_list[0].event_list[0]['id'], self.closeEvent['id'], self.segment_list[-1].event_list[-1]['id'])).lastrowid
            
            for segment in self.segment_list:
                segment.finalizeClose(conn, self.db_id)
                
            #conn.commit()
                
            wound_dict = {} #collections.defaultdict(int)
            active_dict = {}
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

                conn.execute('''update event set active_dict = ?, wound_dict = ? where id = ?''', (active_dict, wound_dict, event['id']))
                #conn.commit()


    def eventIter(self):
        return itertools.chain.from_iterable([x.event_list for x in self.segment_list])

    def __repr__(self):
        return "<LogCombat %s> %d segments\n%s" % (self.db_id, len(self.segment_list), "\n".join(["\t\t%d: %s" % (i, repr(x)) for i, x in enumerate(self.segment_list)]))

def main(sys_argv, options, arguments):
    combatlogparser.main(sys_argv, options, arguments)
    conn = combatlogparser.sqlite_connection(options)
    
    if not options.force:
        try:
            if conn.execute('''select count(*) from combat''').fetchone()[0] > 0:
                print datetime.datetime.now(), "Skipping combat generation..."
                return
        except:
            pass

    
    combatlogparser.sqlite_insureColumns(conn, 'event', [('segment_id', 'int'), ('combat_id', 'int'), ('wound_dict', 'json'), ('active_dict', 'json')])
    
    conn.execute('''update event set segment_id = ?, combat_id = ?, wound_dict = ?, active_dict = ?''', (0, 0, {}, {}))
    
    conn.execute('''drop table if exists combat''')
    conn.execute('''create table combat (id integer primary key, start_event_id, close_event_id, end_event_id)''')

    conn.execute('''drop table if exists segment''')
    conn.execute('''create table segment (id integer primary key, start_event_id, close_event_id, end_event_id, combat_id)''')
    conn.commit()
    
    
    print datetime.datetime.now(), "Building combats..."
    combat_list = []
    for event in conn.execute('''select * from event order by time''').fetchall():
        #print event
        
        #if not combat_list:
        #    combat_list.append(LogCombat(event))
        if combat_list and combat_list[-1].isOpen():
            combat_list[-1].addEvent(event)
        else:
            combat_list.append(LogCombat(event))
    
    print datetime.datetime.now(), "Pruning combats..."
    require_set = set()
    for name_str in options.prune_str.split(','):
        require_set.add('NPC/' + name_str)
        require_set.add('Mount/' + name_str)
    combat_list = [combat for combat in combat_list if combat.prune(require_set)]
    
    print datetime.datetime.now(), "Saving to %s" % (options.db_path,)
    for combat in combat_list:
        #combat.sqlite_updateEvents(conn)
        combat.finalizeClose(conn, require_set)
    conn.commit()
    
    


if __name__ == "__main__":
    options, arguments = usage(sys_argv)
    sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof
