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



options, arguments = None, None
def usage(sys_argv):
    global options, arguments
    op = optparse.OptionParser()

    #op.add_option("--log"
    #        , help="Path to the WoWCombatLog.txt file."
    #        , metavar="LOGFILE"
    #        , dest="log_path"
    #        , action="store"
    #        , type="str"
    #        #, default="output"
    #    )

    op.add_option("--db"
            , help="Desired sqlite database output file name."
            , metavar="OUTPUT"
            , dest="db_path"
            , action="store"
            , type="str"
            #, default="output"
        )
    
    options, arguments = op.parse_args(sys_argv)



#def createKey(event):
#    if event['sourceName']:
#        source_str = "%s/%s" % (event['sourceType'], event['sourceName'])
#    else:
#        source_str = None
#    if event['destName']:
#        dest_str = "%s/%s" % (event['destType'], event['destName'])
#    else:
#        dest_str = None
#
#    return (event['eventType'], source_str, dest_str, event.get('spellName', None) or event.get('environmentalType', None), event.get('missType', None) or event.get('critical', None) and 'critical' or 'normal')
#
#def quickExclude(row):
#    return False
#    #return row[0].endswith('SPELL_PERIODIC_ENERGIZE') or 'SPELL_AURA' in row[0]
#
#
#def jsonDate(x):
#    if isinstance(x, datetime.datetime):
#        return x.strftime("%Y-%m-%d_%H:%M:%S.%f")
#    if isinstance(x, dict):
#        return dict([(k, jsonDate(v)) for k,v in x.items()])
#    return x

def scrapeArmory(options, pc_list):
    try:
        armory_dict = json.load(file('armory.json'))
    except:
        armory_dict = {}

    for pc_str in pc_list:

        if pc_str in armory_dict and 'class' in armory_dict[pc_str]:
            continue

        opener = urllib2.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X; en-US; rv:1.8.1.6) Gecko/20070725 Firefox/2.0.0.6')]

        characterTag_str = None
        #<character battleGroup="Bloodlust" charUrl="r=Proudmoore&amp;n=Ragingfire" class="Mage" classId="8" faction="Alliance" factionId="0" gender="Female" genderId="1" guildName="Game Theory" guildUrl="r=Proudmoore&amp;n=Game+Theory&amp;p=1" lastModified="February 16, 2009" level="80" name="Ragingfire" points="3270" prefix="Twilight Vanquisher " race="Human" raceId="1" realm="Proudmoore" suffix=""/>

        print "http://%s.wowarmory.com/character-sheet.xml?r=%s&n=%s" % (options.region_str, options.realm_str, pc_str)
        try:
            for line_str in opener.open("http://%s.wowarmory.com/character-sheet.xml?r=%s&n=%s" % (options.region_str, options.realm_str, pc_str)):
                if "<character " in line_str:
                    characterTag_str = line_str
                    break
            else:
                #print "Skipping:", toon.name
                #time.sleep(10)
                continue
        except:
            pass

        armory_dict.setdefault(pc_str, {})
        try:
            armory_dict[pc_str]['class'] = re.match(r'''.* class="([^"]+)" .*''', characterTag_str).group(1)
        except:
            print characterTag_str
            raise
            pass

    try:
        json.dump(armory_dict, file('armory.json', 'w'))
    except:
        pass

    return armory_dict

def classColors():
    color_dict = {
            'Death Knight': ((196, 30, 59), (0.77, 0.12, 0.23), '#C41F3B'),
            'Druid': ((255, 125, 10), (1.00, 0.49, 0.04), '#FF7D0A'),
            'Hunter': ((171, 212, 115), (0.67, 0.83, 0.45), '#ABD473'),
            'Mage': ((105, 204, 240), (0.41, 0.80, 0.94), '#69CCF0'),
            'Paladin': ((245, 140, 186), (0.96, 0.55, 0.73), '#F58CBA'),
            'Priest': ((255, 255, 255), (1.00, 1.00, 1.00), '#FFFFFF'),
            'Rogue': ((255, 245, 105), (1.00, 0.96, 0.41), '#FFF569'),
            'Shaman': ((36, 89, 255), (0.14, 0.35, 1.00), '#2459FF'),
            'Warlock': ((148, 130, 201), (0.58, 0.51, 0.79), '#9482C9'),
            'Warrior': ((199, 156, 110), (0.78, 0.61, 0.43), '#C79C6E'),
        }

    return color_dict


class LogFragment(object):
    aggregateKey_tup = ('amount', 'extra', 'resisted', 'blocked', 'absorbed')

    def __init__(self, event, closeDelay=10):
        self.event_list = [event]
        self.closeDelay = closeDelay
        self.closeEvent = None
        #self.openEvent = None
        self.npcEvent = None
        self.aggregate_dict = {}
        self.actor_set = set()

    def addEvent(self, event):
        if prefix_dict[event['prefix']][0] and suffix_dict[event['suffix']][0]:
            self.event_list.append(event)

            if not self.npcEvent and event.get('sourceType', None) == 'NPC':
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

            key_tup = createKey(event)

            # The last column is the count.
            self.aggregate_dict.setdefault(key_tup, [0] * (len(self.aggregateKey_tup) + 1))
            for i, col in enumerate(self.aggregateKey_tup):
                try:
                    self.aggregate_dict[key_tup][i] += event.get(col, 0)
                except:
                    print repr(event)
                    print self.aggregate_dict[key_tup][i], col, event.get(col, 0)
                    raise

            self.aggregate_dict[key_tup][-1] += 1


            global eventSeen_dict
            eventSeen_dict.setdefault(event['prefix'], {})
            eventSeen_dict[event['prefix']].setdefault(event['suffix'], {})
            if event.get('spellName', None):
                eventSeen_dict[event['prefix']][event['suffix']].setdefault(event['spellName'], {})
                spellSeen_dict[event['spellName']] = {}

            global actorSeen_dict
            for actor_str in ('source', 'dest'):
                if event[actor_str + 'GUID']:
                    actorType_str = actorType(event[actor_str + 'GUID'])
                    actorSeen_dict.setdefault(actorType_str, {})
                    actorSeen_dict[actorType_str].setdefault(event[actor_str + 'Name'], {})

                    if event.get('spellName', None):
                        actorSeen_dict[actorType_str][event[actor_str + 'Name']].setdefault(event['spellName'], {})

    def isOpen(self):
        if not self.npcEvent and self.event_list[-1]['time'] - self.event_list[0]['time'] > datetime.timedelta(seconds=self.closeDelay):
            return False

        if not self.closeEvent:
            return True

        return datetime.timedelta(seconds=self.closeDelay) > self.event_list[-1]['time'] - self.closeEvent['time']

    def lastEvent(self):
        return self.event_list[-1]

    def prune(self, require_set):
        print [x for x in sorted(self.actor_set) if not x.startswith('PC/')]
        return require_set.intersection(self.actor_set)

        #for actor in require_set:
        #    if actor in self.actor_set:
        #        return True
        #return False

    def forJson(self, eventType_str):
        aggregate_list = []
        for k,v in self.aggregate_dict.items():
            if k[0] == eventType_str:
                aggregate_list.append([abv(x) for x in k] + v)

        return {'aggregate_list':aggregate_list,
                'close': jsonDate(self.closeEvent),
                'start': jsonDate(self.event_list[0]['time']),
                'end': jsonDate(self.event_list[-1]['time'])}

    def __repr__(self):
        return "<LogFragment %s> %d aggregates" % (hex(id(self)), len(self.aggregate_dict))



class LogCombat(object):
    def __init__(self, event, closeDelay=30):
        self.fragment_list = [LogFragment(event)]
        self.closeDelay = closeDelay
        self.closeEvent = None
        self.openEvent = None

    def addEvent(self, event):
        if self.fragment_list[-1].isOpen():
            self.fragment_list[-1].addEvent(event)
        else:
            self.fragment_list.append(LogFragment(event))

        if event['eventType'] == 'SWING_DAMAGE' or event['eventType'] == 'SPELL_DAMAGE':
            self.closeEvent = event

            if not self.openEvent and event['destType'] == 'NPC':
                self.openEvent = event

        if not self.isOpen():
            wound_dict = collections.defaultdict(int)
            #active_dict = {}
            for event in self.eventIter():
                if event.get('destType', None) == 'PC':
                    if event['suffix'] == '_DAMAGE':
                        wound_dict = copy.deepcopy(wound_dict)
                        wound_dict[event['destName']] += event['amount'] - event['extra']
                    elif event['suffix'] == '_HEAL':
                        wound_dict = copy.deepcopy(wound_dict)
                        wound_dict[event['destName']] -= event['amount'] - event['extra']
                        if event['extra'] > 0:
                                del wound_dict[event['destName']]
                    elif event['suffix'] == '_DIED':
                        wound_dict = copy.deepcopy(wound_dict)
                        del wound_dict[event['destName']]

                    if wound_dict[event['destName']] < 0:
                        wound_dict = copy.deepcopy(wound_dict)
                        del wound_dict[event['destName']]

                event['wound_dict'] = wound_dict

                #if event['sourceType'] == 'PC':
                #    if event['suffix'] == '_CAST_START':
                #        active_dict['sourceName'] = event['spellName']
                #    elif 'sourceName' in active_dict and (event['suffix'] == '_CAST_SUCCESS' or event['suffix'] == '_CAST_FAILED'):
                #        del active_dict['sourceName']

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

    def forJson(self, eventType_str):
        return {'fragment_list': [x.forJson(eventType_str) for x in self.fragment_list],
            'open': jsonDate(self.openEvent),
            'close': jsonDate(self.closeEvent),
            'start': jsonDate(self.fragment_list[0].event_list[0]['time']),
            'end': jsonDate(self.fragment_list[-1].event_list[-1]['time'])}

    def getActorSet(self):
        actor_set = set()
        for fragment in self.fragment_list:
            actor_set.update(fragment.actor_set)

        return actor_set

    def __repr__(self):
        return "<LogCombat %s> %d fragments\n%s" % (hex(id(self)), len(self.fragment_list), "\n".join(["\t\t%d: %s" % (i, repr(x)) for i, x in enumerate(self.fragment_list)]))

class LogFile(object):
    def __init__(self, log_list):
        csv_list = []
        for log_path in log_list:
            print datetime.datetime.now(), log_path
            csv_list.extend(list(csv.reader(file(log_path))))

        print datetime.datetime.now(), "Parsing"
        self.event_list = [parseRow(x) for x in csv_list if not quickExclude(x)]
        print datetime.datetime.now(), "Sorting"
        self.event_list.sort(key=lambda x: x['time'])

        self.combat_list = []
        self.combat_list.append(LogCombat(self.event_list[0]))

        print datetime.datetime.now(), "Event Loop"
        for event in self.event_list[1:]:
            if self.combat_list[-1].isOpen():
                self.combat_list[-1].addEvent(event)
            else:
                self.combat_list.append(LogCombat(event))
        print datetime.datetime.now(), "Done"

    def prune(self, require_set):
        self.combat_list = [x for x in self.combat_list if x.prune(require_set)]

        return self.combat_list

    def forJson(self):
        event_dict = {}
        for prefix_str, suffix_dict in eventSeen_dict.items():
            for suffix_str in suffix_dict:
                eventType_str = prefix_str + suffix_str

                event_dict[eventType_str] = [x.forJson(eventType_str) for x in self.combat_list]

        return {'event_dict': event_dict,
            'start': jsonDate(self.combat_list[0].fragment_list[0].event_list[0]['time']),
            'end': jsonDate(self.combat_list[-1].fragment_list[-1].event_list[-1]['time'])}

    def __repr__(self):
        return "<LogFile %s> %d combats\n%s" % (hex(id(self)), len(self.combat_list), "\n".join(["\t%d: %s" % (i, repr(x)) for i, x in enumerate(self.combat_list)]))


def main(sys_argv):
    global options, arguments
    usage(sys_argv)
    
    




if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)

# eof
