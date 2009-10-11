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


fragment_counter = 1
class LogFragment(object):
    aggregateKey_tup = ('amount', 'extra', 'resisted', 'blocked', 'absorbed')

    def __init__(self, event, closeDelay=10):
        global fragment_counter
        
        self.event_list = [event]
        self.closeDelay = closeDelay
        self.closeEvent = None
        #self.openEvent = None
        self.npcEvent = None
        self.aggregate_dict = {}
        self.actor_set = set()
        self.db_id = fragment_counter
        fragment_counter += 1

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

            #key_tup = createKey(event)
            #
            ## The last column is the count.
            #self.aggregate_dict.setdefault(key_tup, [0] * (len(self.aggregateKey_tup) + 1))
            #for i, col in enumerate(self.aggregateKey_tup):
            #    try:
            #        self.aggregate_dict[key_tup][i] += event[col] or 0
            #    except:
            #        print repr(event)
            #        print self.aggregate_dict[key_tup][i], col, event[col] or 0
            #        raise
            #
            #self.aggregate_dict[key_tup][-1] += 1


            #global eventSeen_dict
            #eventSeen_dict.setdefault(event['prefix'], {})
            #eventSeen_dict[event['prefix']].setdefault(event['suffix'], {})
            #if event['spellName']:
            #    eventSeen_dict[event['prefix']][event['suffix']].setdefault(event['spellName'], {})
            #    spellSeen_dict[event['spellName']] = {}
            #
            #global actorSeen_dict
            #for actor_str in ('source', 'dest'):
            #    if event[actor_str + 'GUID']:
            #        actorType_str = actorType(event[actor_str + 'GUID'])
            #        actorSeen_dict.setdefault(actorType_str, {})
            #        actorSeen_dict[actorType_str].setdefault(event[actor_str + 'Name'], {})
            #
            #        if event['spellName']:
            #            actorSeen_dict[actorType_str][event[actor_str + 'Name']].setdefault(event['spellName'], {})

    def isOpen(self):
        if not self.npcEvent and self.event_list[-1]['time'] - self.event_list[0]['time'] > datetime.timedelta(seconds=self.closeDelay):
            return False

        if not self.closeEvent:
            return True

        return datetime.timedelta(seconds=self.closeDelay) > self.event_list[-1]['time'] - self.closeEvent['time']

    def lastEvent(self):
        return self.event_list[-1]

    def prune(self, require_set):
        #print [x for x in sorted(self.actor_set) if not x.startswith('PC/')]
        return require_set.intersection(self.actor_set)

        #for actor in require_set:
        #    if actor in self.actor_set:
        #        return True
        #return False

    def sqlite_updateEvents(self, conn, combat_id):
        for event in self.event_list:
            conn.execute('''update event set combat_id = ?, fragment_id = ? where id = ?''', (combat_id, self.db_id, event['id']))
        conn.commit()

    #def forJson(self, eventType_str):
    #    aggregate_list = []
    #    for k,v in self.aggregate_dict.items():
    #        if k[0] == eventType_str:
    #            aggregate_list.append([abv(x) for x in k] + v)
    #
    #    return {'aggregate_list':aggregate_list,
    #            'close': jsonDate(self.closeEvent),
    #            'start': jsonDate(self.event_list[0]['time']),
    #            'end': jsonDate(self.event_list[-1]['time'])}

    def __repr__(self):
        return "<LogFragment %s> %d aggregates" % (hex(id(self)), len(self.aggregate_dict))


combat_counter = 1
class LogCombat(object):
    def __init__(self, event, closeDelay=60):
        global combat_counter
        
        self.fragment_list = [LogFragment(event)]
        self.closeDelay = closeDelay
        self.closeEvent = None
        self.openEvent = None
        self.db_id = combat_counter
        
        combat_counter += 1

    def addEvent(self, event, conn):
        if self.fragment_list[-1].isOpen():
            self.fragment_list[-1].addEvent(event)
        else:
            self.fragment_list.append(LogFragment(event))

        if event['eventType'] == 'SWING_DAMAGE' or event['eventType'] == 'SPELL_DAMAGE':
            self.closeEvent = event

            if not self.openEvent and event['destType'] == 'NPC':
                self.openEvent = event

        if not self.isOpen():
            wound_dict = {} #collections.defaultdict(int)
            active_dict = {}
            for event in self.eventIter():
                if event['destType'] == 'PC':
                    wound_dict.setdefault(event['destName'], 0)
                    
                    if event['suffix'] == '_DAMAGE':
                        #wound_dict = copy.deepcopy(wound_dict)
                        wound_dict[event['destName']] += event['amount'] - event['extra']
                    elif event['suffix'] == '_HEAL':
                        #wound_dict = copy.deepcopy(wound_dict)
                        wound_dict[event['destName']] -= event['amount'] - event['extra']
                        if event['extra'] > 0:
                            wound_dict[event['destName']] = -event['extra']

                    if event['suffix'] == '_DIED' or wound_dict[event['destName']] <= 0:
                        #wound_dict = copy.deepcopy(wound_dict)
                        del wound_dict[event['destName']]
                    #
                    #if wound_dict.get(event['destName'], 0) < 0:
                    #    #wound_dict = copy.deepcopy(wound_dict)
                    #    del wound_dict[event['destName']]

                #event['wound_dict'] = copy.deepcopy(wound_dict)
                #conn.execute('''update event set wound_dict = ? where id = ?''', (wound_dict, event['id']))

                if event['sourceType'] == 'PC':
                    if event['suffix'] == '_CAST_START':
                        active_dict[event['sourceName']] = event['spellName']
                    elif 'sourceName' in active_dict and (event['suffix'] == '_CAST_SUCCESS' or event['suffix'] == '_CAST_FAILED'):
                        del active_dict[event['sourceName']]

                #event['active_dict'] = copy.deepcopy(active_dict)
                conn.execute('''update event set active_dict = ?, wound_dict = ? where id = ?''', (active_dict, wound_dict, event['id']))
                #conn.commit()

    def isOpen(self):
        if not self.closeEvent:
            return True

        return datetime.timedelta(seconds=self.closeDelay) > self.fragment_list[-1].lastEvent()['time'] - self.closeEvent['time']

    def prune(self, require_set):
        self.fragment_list = [x for x in self.fragment_list if x.prune(require_set)]

        self.prune_set = set()
        for x in self.fragment_list:
            self.prune_set.update(x.prune(require_set))

        return self.fragment_list

    def eventIter(self):
        return itertools.chain.from_iterable([x.event_list for x in self.fragment_list])
        
    def sqlite_updateEvents(self, conn):
        #for event in self.event_list:
        #    conn.execute('''update event set combat_id = ? where id = ?''', (self.db_id, event['id']))
            
        for fragment in self.fragment_list:
            fragment.sqlite_updateEvents(conn, self.db_id)
        

    #def forJson(self, eventType_str):
    #    return {'fragment_list': [x.forJson(eventType_str) for x in self.fragment_list],
    #        'open': jsonDate(self.openEvent),
    #        'close': jsonDate(self.closeEvent),
    #        'start': jsonDate(self.fragment_list[0].event_list[0]['time']),
    #        'end': jsonDate(self.fragment_list[-1].event_list[-1]['time'])}

    #def getActorSet(self):
    #    actor_set = set()
    #    for fragment in self.fragment_list:
    #        actor_set.update(fragment.actor_set)
    #
    #    return actor_set

    def __repr__(self):
        return "<LogCombat %s> %d fragments\n%s" % (hex(id(self)), len(self.fragment_list), "\n".join(["\t\t%d: %s" % (i, repr(x)) for i, x in enumerate(self.fragment_list)]))

#class LogFile(object):
#    def __init__(self, log_list):
#        csv_list = []
#        for log_path in log_list:
#            print datetime.datetime.now(), log_path
#            csv_list.extend(list(csv.reader(file(log_path))))
#
#        print datetime.datetime.now(), "Parsing"
#        self.event_list = [parseRow(x) for x in csv_list if not quickExclude(x)]
#        print datetime.datetime.now(), "Sorting"
#        self.event_list.sort(key=lambda x: x['time'])
#
#        self.combat_list = []
#        self.combat_list.append(LogCombat(self.event_list[0]))
#
#        print datetime.datetime.now(), "Event Loop"
#        for event in self.event_list[1:]:
#            if self.combat_list[-1].isOpen():
#                self.combat_list[-1].addEvent(event)
#            else:
#                self.combat_list.append(LogCombat(event))
#        print datetime.datetime.now(), "Done"
#
#    def prune(self, require_set):
#        self.combat_list = [x for x in self.combat_list if x.prune(require_set)]
#
#        return self.combat_list
#
#    #def forJson(self):
#    #    event_dict = {}
#    #    for prefix_str, suffix_dict in eventSeen_dict.items():
#    #        for suffix_str in suffix_dict:
#    #            eventType_str = prefix_str + suffix_str
#    #
#    #            event_dict[eventType_str] = [x.forJson(eventType_str) for x in self.combat_list]
#    #
#    #    return {'event_dict': event_dict,
#    #        'start': jsonDate(self.combat_list[0].fragment_list[0].event_list[0]['time']),
#    #        'end': jsonDate(self.combat_list[-1].fragment_list[-1].event_list[-1]['time'])}
#
#    def __repr__(self):
#        return "<LogFile %s> %d combats\n%s" % (hex(id(self)), len(self.combat_list), "\n".join(["\t%d: %s" % (i, repr(x)) for i, x in enumerate(self.combat_list)]))


def main(sys_argv):
    options, arguments = usage(sys_argv)
    
    if not options.db_path:
        db_path = options.log_path + ".db"
    else:
        db_path = options.db_path
        
    if options.log_path:
        print datetime.datetime.now(), "Parsing %s --> %s" % (options.log_path, db_path)
        combatlogparser.sqlite_parseLog(db_path, options.log_path, False)
        
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    
    print datetime.datetime.now(), "Building combats..."
    combat_list = []
    for event in conn.execute('''select * from event order by time''').fetchall():
        #print event
        
        if not combat_list:
            combat_list.append(LogCombat(event))
        elif combat_list[-1].isOpen():
            combat_list[-1].addEvent(event, conn)
        else:
            combat_list.append(LogCombat(event))
    conn.commit()
    
    print datetime.datetime.now(), "Pruning combats..."
    require_set = set()
    for name_str in options.prune_str.split(','):
        require_set.add('NPC/' + name_str)
        require_set.add('Mount/' + name_str)
    combat_list = [combat for combat in combat_list if combat.prune(require_set)]
    
    print datetime.datetime.now(), "Saving to %s" % (db_path,)
    for combat in combat_list:
        combat.sqlite_updateEvents(conn)
    
    
    




if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)

# eof
