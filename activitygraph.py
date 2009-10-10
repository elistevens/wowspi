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
import sys
import time
import urllib
import urllib2

from PIL import Image, ImageDraw, ImageFont

import combatlogparser

version = None
htmlContent1 = """..."""
htmlContent2 = """..."""

options, arguments = None, None
def usage(sys_argv):
    global options, arguments
    op = optparse.OptionParser()

    op.add_option("--prune"
            , help="Prune the resulting combats/fragments to only include those where the named actors were present (ex: 'NPC/Sartharion,NPC/Tenebron,NPC/Shadron,NPC/Vesperon').  Defaults to all T7 raid bosses."
            , metavar="TYPE:ACTOR"
            , dest="prune_str"
            , action="store"
            , type="str"
            , default="NPC/Sartharion,NPC/Malygos,NPC/Anub'Rekhan,NPC/Grand Widow Faerlina,NPC/Maexxna,NPC/Noth the Plaguebringer,NPC/Heigan the Unclean,NPC/Loatheb," +\
                      "NPC/Instructor Razuvious,NPC/Gothik the Harvester,NPC/Patchwerk,NPC/Grobbulus,NPC/Gluth,NPC/Thaddius,NPC/Sapphiron,NPC/Kel'Thuzad," +\
                      "Mount/Ignis the Furnace Master,NPC/Razorscale,Mount/XT-002 Deconstructor,NPC/Steelbreaker,NPC/Kologarn,NPC/Auriya,Mount/Aerial Command Unit,Mount/Leviathan Mk II,Mount/VX-001,NPC/Thorim,NPC/Hodir,NPC/Freya",
        )

    op.add_option("--out"
            , help="Desired output file name (excluding extension)."
            , metavar="OUTPUT"
            , dest="out_str"
            , action="store"
            , type="str"
            , default="output"
        )

    op.add_option("--realm"
            , help="Realm to use for armory data queries."
            , metavar="REALM"
            , dest="realm_str"
            , action="store"
            , type="str"
            , default="Proudmoore"
        )

    op.add_option("--region"
            , help="Region to use for armory data queries (www, eu, kr, cn, tw)."
            , metavar="REGION"
            , dest="region_str"
            , action="store"
            , type="str"
            , default="www"
        )

    if version is None:
        op.add_option("--ext"
                , help="Desired output file extension (default: js)."
                , metavar="EXTENSION"
                , dest="ext_str"
                , action="store"
                , type="str"
                , default="js"
            )
        op.add_option("--release"
                , help="Freeze the script into script_vXXX.py, including html, etc."
                , metavar="VERSION"
                , dest="version_str"
                , action="store"
                , type="str"
            )
    else:
        op.add_option("--ext"
                , help="Desired output file extension (default: html)."
                , metavar="EXTENSION"
                , dest="ext_str"
                , action="store"
                , type="str"
                , default="html"
            )

    options, arguments = op.parse_args(sys_argv)

#
#counter = itertools.count()
#abv_dict = {}
#rabv_dict = {}
#def abv(s):
#    global abv_dict
#
#    if isinstance(s, str):
#        #print s, abv_dict
#        try:
#            return abv_dict[s]
#        except:
#            abv_dict[s] = next(counter)
#            rabv_dict[abv_dict[s]] = s
#            return abv_dict[s]
#    return s
#
#
#fixed_list = ['sourceGUID', 'sourceName', 'sourceFlags', 'destGUID', 'destName', 'destFlags']
#
## Note: order is important here, because 'SPELL' is a prefix for 'SPELL_XXX', the rest are in rough priority order
#prefix_list = [
#        ('SPELL_PERIODIC',      (1, ['spellId', 'spellName', 'spellSchool'])),
#        ('SPELL_BUILDING',      (0, ['spellId', 'spellName', 'spellSchool'])),
#        ('SPELL',               (1, ['spellId', 'spellName', 'spellSchool'])),
#        ('SWING',               (1, [])),
#        ('DAMAGE',              (1, ['spellId', 'spellName', 'spellSchool'])),
#        ('RANGE',               (1, ['spellId', 'spellName', 'spellSchool'])),
#        ('ENVIRONMENTAL',       (1, ['environmentalType'])),
#        ('ENCHANT',             (0, ['spellName', 'itemID', 'itemName'])),
#        ('UNIT',                (1, [])),
#        ('PARTY',                (1, [])),
#    ]
#prefix_dict = dict(prefix_list)
#
## See: _DAMAGE vs. _DURABILITY_DAMAGE
#suffix_list = [
#        ('_DAMAGE',             (2, ['amount', 'extra', 'school', 'resisted', 'blocked', 'absorbed', 'critical', 'glancing', 'crushing'])),
#        ('_MISSED',             (1, ['missType', '?amount'])),
#        ('_HEAL',               (3, ['amount', 'extra', 'critical'])),
#        ('_ENERGIZE',           (1, ['amount', 'powerType'])),
#        ('_DRAIN',              (2, ['amount', 'powerType', 'extra'])),
#        ('_LEECH',              (2, ['amount', 'powerType', 'extra'])),
#        ('_INTERRUPT',          (1, ['extraSpellID', 'extraSpellName', 'extraSchool'])),
#        ('_DISPEL',             (1, ['extraSpellID', 'extraSpellName', 'extraSchool', 'auraType'])),
#        ('_DISPEL_FAILED',      (1, ['extraSpellID', 'extraSpellName', 'extraSchool'])),
#        ('_STOLEN',             (1, ['extraSpellID', 'extraSpellName', 'extraSchool', 'auraType'])),
#        ('_EXTRA_ATTACKS',      (1, ['amount'])),
#        ('_AURA_APPLIED',       (1, ['auraType'])),
#        ('_AURA_REMOVED',       (1, ['auraType'])),
#        ('_AURA_APPLIED_DOSE',  (1, ['auraType', 'amount'])),
#        ('_AURA_REMOVED_DOSE',  (1, ['auraType', 'amount'])),
#        ('_AURA_REFRESH',       (1, ['auraType'])),
#        ('_AURA_BROKEN',        (1, ['auraType'])),
#        ('_AURA_BROKEN_SPELL',  (1, ['extraSpellID', 'extraSpellName', 'extraSchool', 'auraType'])),
#        ('_CAST_START',         (1, [])),
#        ('_CAST_SUCCESS',       (1, [])),
#        ('_CAST_FAILED',        (1, ['failedType'])),
#        ('_INSTAKILL',          (1, [])),
#        ('_DURABILITY_DAMAGE',  (0, [])),
#        ('_DURABILITY_DAMAGE_ALL',  (0, [])),
#        ('_CREATE',             (0, [])),
#        ('_SUMMON',             (0, [])),
#        ('_RESURRECT',          (1, [])),
#        ('_SPLIT',              (1, ['amount', 'extra', 'school', 'resisted', 'blocked', 'absorbed', 'critical', 'glancing', 'crushing'])),
#        ('_SHIELD',             (1, ['amount', 'extra', 'school', 'resisted', 'blocked', 'absorbed', 'critical', 'glancing', 'crushing'])),
#        ('_SHIELD_MISSED',      (1, ['missType', '?amount'])),
#        ('_REMOVED',            (0, [])),
#        ('_APPLIED',            (0, [])),
#        ('_DIED',               (1, [])),
#        ('_DESTROYED',          (0, [])),
#        ('_KILL',               (0, [])),
#    ]
#suffix_dict = dict(suffix_list)
#
#
#actor_dict = {
#        0x0000000000000000: 'PC',
#        0x0010000000000000: 'Obj',
#        0x0030000000000000: 'NPC',
#        0x0040000000000000: 'Pet',
#        0x0050000000000000: 'Mount',
#        #0x0010000000000000: '1???',
#        #0x0050000000000000: '5???'
#    }
#
#eventSeen_dict = {}
#spellSeen_dict = {}
#actorSeen_dict = {}
#
#time_re = re.compile('(\\d+)/(\\d+) (\\d+):(\\d+):(\\d+).(\\d+)')
#
#def actorType(guid):
#    return actor_dict.get(0x00F0000000000000 & guid, 'unknown:' + hex(0x00F0000000000000 & guid))
#
#
#def parseRow(row):
#    """
#    10/21 20:59:04.831  SWING_DAMAGE,0x0000000002B0C69C,"Biggdog",0x514,0xF130005967003326,"High Warlord Naj'entus",0xa48,171,0,1,0,0,0,nil,1,nil
#    10/21 20:59:04.873  SPELL_DAMAGE,0x000000000142C9BE,"Autogun",0x514,0xF130005967003326,"High Warlord Naj'entus",0xa48,27209,"Shadow Bolt",0x20,2233,0,32,220,0,0,nil,nil,nil
#    """
#    #print row
#
#    #rowCopy = list(row)
#    event = {}
#
#    try:
#        date_str, time_str, eventType_str = row.pop(0).split()
#
#        event['eventType'] = eventType_str
#
#        tmp_list = time_str.split(".")
#        time_list = [int(x) for x in date_str.split('/') + tmp_list[0].split(':') + [tmp_list[1]]]
#
#        event['time'] = datetime.datetime(datetime.datetime.now().year, time_list[0], time_list[1], time_list[2], time_list[3], time_list[4], time_list[5] * 1000)
#        if event['time'] > datetime.datetime.now():
#            event['time'] = datetime.datetime(datetime.datetime.now().year - 1, time_list[0], time_list[1], time_list[2], time_list[3], time_list[4], time_list[5] * 1000)
#
#        for col in fixed_list:
#            event[col] = row.pop(0)
#
#        event['prefix'] = ''
#        for prefix_tup in prefix_list:
#            if eventType_str.startswith(prefix_tup[0]):
#                event['prefix'] = prefix_tup[0]
#                for col in prefix_tup[1][1]:
#                    event[col] = row.pop(0)
#                break
#
#        event['suffix'] = event['eventType'][len(event['prefix']):]
#        for col in suffix_dict[event['suffix']][1]:
#            if col.startswith('?'):
#                col = col[1:]
#                if row:
#                    event[col] = row.pop(0)
#            else:
#                event[col] = row.pop(0)
#
#
#        assert len(row) == 0, row
#
#        tmp = {}
#        tmp.update(event)
#        for key, value in tmp.items():
#            if value == 'nil':
#                event[key] = None
#            elif isinstance(value, str):
#                if value.startswith('0x'):
#                    event[key] = int(value[2:], 16)
#                elif re.match(r"^-?\d+$", value):
#                    event[key] = int(value)
#
#        for actor_str in ('source', 'dest'):
#            if event[actor_str + 'GUID']:
#                actorType_str = actorType(event[actor_str + 'GUID'])
#                event[actor_str + 'Type'] = actorType_str
#                event[actor_str + actorType_str] = True
#
#        return event
#    except:
#        #print rowCopy
#        raise
#
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
#
#def scrapeArmory(*pc_list):
#    try:
#        armory_dict = json.load(file('armory.json'))
#    except:
#        armory_dict = {}
#
#    for pc_str in pc_list:
#
#        if pc_str in armory_dict and 'class' in armory_dict[pc_str]:
#            continue
#
#        opener = urllib2.build_opener()
#        opener.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X; en-US; rv:1.8.1.6) Gecko/20070725 Firefox/2.0.0.6')]
#
#        characterTag_str = None
#        #<character battleGroup="Bloodlust" charUrl="r=Proudmoore&amp;n=Ragingfire" class="Mage" classId="8" faction="Alliance" factionId="0" gender="Female" genderId="1" guildName="Game Theory" guildUrl="r=Proudmoore&amp;n=Game+Theory&amp;p=1" lastModified="February 16, 2009" level="80" name="Ragingfire" points="3270" prefix="Twilight Vanquisher " race="Human" raceId="1" realm="Proudmoore" suffix=""/>
#
#        print "http://%s.wowarmory.com/character-sheet.xml?r=%s&n=%s" % (options.region_str, options.realm_str, pc_str)
#        try:
#            for line_str in opener.open("http://%s.wowarmory.com/character-sheet.xml?r=%s&n=%s" % (options.region_str, options.realm_str, pc_str)):
#                if "<character " in line_str:
#                    characterTag_str = line_str
#                    break
#            else:
#                #print "Skipping:", toon.name
#                #time.sleep(10)
#                continue
#        except:
#            pass
#
#        armory_dict.setdefault(pc_str, {})
#        try:
#            armory_dict[pc_str]['class'] = re.match(r'''.* class="([^"]+)" .*''', characterTag_str).group(1)
#        except:
#            print characterTag_str
#            raise
#            pass
#
#    try:
#        json.dump(armory_dict, file('armory.json', 'w'))
#    except:
#        pass
#
#    return armory_dict
#
#def classColors():
#    color_dict = {
#            'Death Knight': ((196, 30, 59), (0.77, 0.12, 0.23), '#C41F3B'),
#            'Druid': ((255, 125, 10), (1.00, 0.49, 0.04), '#FF7D0A'),
#            'Hunter': ((171, 212, 115), (0.67, 0.83, 0.45), '#ABD473'),
#            'Mage': ((105, 204, 240), (0.41, 0.80, 0.94), '#69CCF0'),
#            'Paladin': ((245, 140, 186), (0.96, 0.55, 0.73), '#F58CBA'),
#            'Priest': ((255, 255, 255), (1.00, 1.00, 1.00), '#FFFFFF'),
#            'Rogue': ((255, 245, 105), (1.00, 0.96, 0.41), '#FFF569'),
#            'Shaman': ((36, 89, 255), (0.14, 0.35, 1.00), '#2459FF'),
#            'Warlock': ((148, 130, 201), (0.58, 0.51, 0.79), '#9482C9'),
#            'Warrior': ((199, 156, 110), (0.78, 0.61, 0.43), '#C79C6E'),
#        }
#
#    return color_dict
#
#
#class LogFragment(object):
#    aggregateKey_tup = ('amount', 'extra', 'resisted', 'blocked', 'absorbed')
#
#    def __init__(self, event, closeDelay=30):
#        self.event_list = [event]
#        self.closeDelay = closeDelay
#        self.closeEvent = None
#        self.openEvent = None
#        self.aggregate_dict = {}
#        self.actor_set = set()
#
#    def addEvent(self, event):
#        if prefix_dict[event['prefix']][0] and suffix_dict[event['suffix']][0]:
#            self.event_list.append(event)
#
#            if event['eventType'] == 'UNIT_DIED' and event['destType'] == 'PC':
#                self.closeEvent = event
#
#            try:
#                self.actor_set.add(event['sourceType'] + "/" + event['sourceName'])
#            except:
#                pass
#            try:
#                self.actor_set.add(event['destType'] + "/" + event['destName'])
#            except:
#                pass
#
#            key_tup = createKey(event)
#
#            # The last column is the count.
#            self.aggregate_dict.setdefault(key_tup, [0] * (len(self.aggregateKey_tup) + 1))
#            for i, col in enumerate(self.aggregateKey_tup):
#                try:
#                    self.aggregate_dict[key_tup][i] += event.get(col, 0)
#                except:
#                    print repr(event)
#                    print self.aggregate_dict[key_tup][i], col, event.get(col, 0)
#                    raise
#
#            self.aggregate_dict[key_tup][-1] += 1
#
#
#            global eventSeen_dict
#            eventSeen_dict.setdefault(event['prefix'], {})
#            eventSeen_dict[event['prefix']].setdefault(event['suffix'], {})
#            if event.get('spellName', None):
#                eventSeen_dict[event['prefix']][event['suffix']].setdefault(event['spellName'], {})
#                spellSeen_dict[event['spellName']] = {}
#
#            global actorSeen_dict
#            for actor_str in ('source', 'dest'):
#                if event[actor_str + 'GUID']:
#                    actorType_str = actorType(event[actor_str + 'GUID'])
#                    actorSeen_dict.setdefault(actorType_str, {})
#                    actorSeen_dict[actorType_str].setdefault(event[actor_str + 'Name'], {})
#
#                    if event.get('spellName', None):
#                        actorSeen_dict[actorType_str][event[actor_str + 'Name']].setdefault(event['spellName'], {})
#
#    def isOpen(self):
#        if not self.closeEvent:
#            return True
#
#        return datetime.timedelta(seconds=self.closeDelay) > self.event_list[-1]['time'] - self.closeEvent['time']
#
#    def lastEvent(self):
#        return self.event_list[-1]
#
#    def prune(self, require_set):
#        #print [x for x in sorted(self.actor_set) if not x.startswith('PC/')]
#        return require_set.intersection(self.actor_set)
#
#        #for actor in require_set:
#        #    if actor in self.actor_set:
#        #        return True
#        #return False
#
#    def forJson(self, eventType_str):
#        aggregate_list = []
#        for k,v in self.aggregate_dict.items():
#            if k[0] == eventType_str:
#                aggregate_list.append([abv(x) for x in k] + v)
#
#        return {'aggregate_list':aggregate_list,
#                'close': jsonDate(self.closeEvent),
#                'start': jsonDate(self.event_list[0]['time']),
#                'end': jsonDate(self.event_list[-1]['time'])}
#
#    def __repr__(self):
#        return "<LogFragment %s> %d aggregates" % (hex(id(self)), len(self.aggregate_dict))
#
#
#
#class LogCombat(object):
#    def __init__(self, event, closeDelay=60):
#        self.fragment_list = [LogFragment(event)]
#        self.closeDelay = closeDelay
#        self.closeEvent = None
#        self.openEvent = None
#
#    def addEvent(self, event):
#        if self.fragment_list[-1].isOpen():
#            self.fragment_list[-1].addEvent(event)
#        else:
#            self.fragment_list.append(LogFragment(event))
#
#        if event['eventType'] == 'SWING_DAMAGE' or event['eventType'] == 'SPELL_DAMAGE':
#            self.closeEvent = event
#
#            if not self.openEvent and event['destType'] == 'NPC':
#                self.openEvent = event
#
#        if not self.isOpen():
#            wound_dict = collections.defaultdict(int)
#            #active_dict = {}
#            for event in self.eventIter():
#                if event.get('destType', None) == 'PC':
#                    if event['suffix'] == '_DAMAGE':
#                        wound_dict[event['destName']] += event['amount']
#                    elif event['suffix'] == '_HEAL':
#                        wound_dict[event['destName']] -= event['amount']
#                    elif event['suffix'] == '_DIED':
#                        wound_dict[event['destName']] = 0
#
#                    if wound_dict[event['destName']] < 0:
#                        wound_dict[event['destName']] = 0
#
#                event['wound_dict'] = copy.deepcopy(wound_dict)
#
#                #if event['sourceType'] == 'PC':
#                #    if event['suffix'] == '_CAST_START':
#                #        active_dict['sourceName'] = event['spellName']
#                #    elif 'sourceName' in active_dict and (event['suffix'] == '_CAST_SUCCESS' or event['suffix'] == '_CAST_FAILED'):
#                #        del active_dict['sourceName']
#
#    def isOpen(self):
#        if not self.closeEvent:
#            return True
#
#        return datetime.timedelta(seconds=self.closeDelay) > self.fragment_list[-1].lastEvent()['time'] - self.closeEvent['time']
#
#    def prune(self, require_set):
#        self.fragment_list = [x for x in self.fragment_list if x.prune(require_set)]
#
#        self.prune_set = set()
#        for x in self.fragment_list:
#            self.prune_set.update(x.prune(require_set))
#
#        return self.fragment_list
#
#    def eventIter(self):
#        return itertools.chain.from_iterable([x.event_list for x in self.fragment_list])
#
#    def forJson(self, eventType_str):
#        return {'fragment_list': [x.forJson(eventType_str) for x in self.fragment_list],
#            'open': jsonDate(self.openEvent),
#            'close': jsonDate(self.closeEvent),
#            'start': jsonDate(self.fragment_list[0].event_list[0]['time']),
#            'end': jsonDate(self.fragment_list[-1].event_list[-1]['time'])}
#
#    def __repr__(self):
#        return "<LogCombat %s> %d fragments\n%s" % (hex(id(self)), len(self.fragment_list), "\n".join(["\t\t%d: %s" % (i, repr(x)) for i, x in enumerate(self.fragment_list)]))
#
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
#    def forJson(self):
#        event_dict = {}
#        for prefix_str, suffix_dict in eventSeen_dict.items():
#            for suffix_str in suffix_dict:
#                eventType_str = prefix_str + suffix_str
#
#                event_dict[eventType_str] = [x.forJson(eventType_str) for x in self.combat_list]
#
#        return {'event_dict': event_dict,
#            'start': jsonDate(self.combat_list[0].fragment_list[0].event_list[0]['time']),
#            'end': jsonDate(self.combat_list[-1].fragment_list[-1].event_list[-1]['time'])}
#
#    def __repr__(self):
#        return "<LogFile %s> %d combats\n%s" % (hex(id(self)), len(self.combat_list), "\n".join(["\t%d: %s" % (i, repr(x)) for i, x in enumerate(self.combat_list)]))


class Timeslice(object):
    def __init__(self, event_list, end_time=None, width=0.2):
        #self.actor = actor
        #self.prev = prev
        self.width = width
        self.leftover = 0.0
        self.cast_dict = {}
        self.swing_dict = {}
        self.died_dict = {}
        self.healing_dict = collections.defaultdict(int)
        self.overhealing_dict = collections.defaultdict(int)
        self.damage_dict = collections.defaultdict(int)
        self.wound_dict = collections.defaultdict(int)
        self.event_list = []

        self.healTarget_dict = collections.defaultdict(set)
        self.damageTarget_dict = collections.defaultdict(set)
        #self.next = None

        #event_iter = iter(event_list)

        while event_list:
            event = event_list.pop()

            if not end_time:
                end_time = event['time'] + datetime.timedelta(seconds=self.width)

            if not self.event_list and event['time'] > end_time:
                end_time = event['time'] + datetime.timedelta(seconds=self.width)

            if event['time'] > end_time:
                event_list.append(event)
                #print event['time'], end_time
                #self.next = Timeslice([event] + list(event_iter), end_time + datetime.timedelta(seconds=self.width), width)
                break

            self.event_list.append(event)

            if event.get('sourceType', None) == 'PC':
                if event['prefix'] in ('SWING',):
                    self.swing_dict[event['sourceName']] = 1

                if event['suffix'] in ('_CAST_START', '_CAST_SUCCESS'):
                    self.cast_dict[event['sourceName']] = 1

                if event['suffix'] == '_HEAL':
                    self.healing_dict[event['sourceName']] += event['amount'] - event['extra']
                    self.overhealing_dict[event['sourceName']] += event['extra']
                    self.healTarget_dict[event['sourceName']].add(event['destName'])

                if event['suffix'] == '_DAMAGE':
                    self.damage_dict[event['sourceName']] += event['amount'] - event['extra']
                    self.damageTarget_dict[event['sourceName']].add(event['destName'])

            if event.get('destType', None) == 'PC' and event['suffix'] == '_DIED':
                self.died_dict[event['destName']] = 1

            for actor in event.get('wound_dict', {}):
                self.wound_dict[actor] = max(self.wound_dict[actor], event['wound_dict'][actor])

    #def getList(self):
    #    if self.next:
    #        return [self] + self.next.getList()
    #
    #    return [self]

#class CombatImage(object):
#    def __init__(self, timeslice_list, *actor_list):
def castImage(file_path, start_time, actor_dict, actor_list=None, font_path='/Library/Fonts/Arial Bold.ttf'):

    font = ImageFont.load_default()#ImageFont.truetype(font_path, 14, encoding="unic")

    if actor_list:
        tmp_dict = {}
        for actor in actor_list:
            tmp_dict[actor] = actor_dict[actor]
        actor_dict = tmp_dict

    image_width = 1000
    image_height = 40 + 100 * len(actor_dict)

    image = Image.new('RGB', (int(image_width), int(image_height)))
    draw = ImageDraw.Draw(image)

    armory_dict = combatlogparser.scrapeArmory(options, actor_dict)
    color_dict = combatlogparser.classColors()

    for i in range(10):
        draw.line([(i * 100, 0), (i * 100, image_height)], fill='#333')


    currentHeight = 20
    for actor, delta_dict in sorted(actor_dict.items()):
        draw.line([(0, currentHeight), (image_width, currentHeight)], fill='#333')

        draw.text((5, currentHeight + 3), actor, font=font, fill='#999')

        light_color = color_dict[armory_dict[actor]['class']][2]
        dark_color = '#%02x%02x%02x' % tuple([int(x * 0.5) for x in color_dict[armory_dict[actor]['class']][0]])

        line_list = []
        for i in range(101):
            line_list.append((i * 10, currentHeight + 100 - min(delta_dict[i], 50) * 2))

            if delta_dict[i]:
                draw.line([(i * 10, currentHeight + 100 - (min(delta_dict[i], 50) * 2)), (i * 10, currentHeight + 100)], fill=dark_color)
        draw.line(line_list, fill=light_color)

        currentHeight += 100

    draw.line([(0, currentHeight), (image_width, currentHeight)], fill='#333')
    draw.text((5, 3), str(start_time), font=font, fill='#999')

    image.save(file_path)


def timelineImage(file_path, timeslice_list, actor_list, font_path='/Library/Fonts/Arial Bold.ttf'):
    #self.timeslice_list = timeslice_list

    font = ImageFont.load_default()#ImageFont.truetype(font_path, 14, encoding="unic")

    actor_set = set()

    image_width = len(timeslice_list)
    height = 20
    heal_scale =  0.002 / (1 + int(timeslice_list[0].width))
    wound_scale = 0.002 / (1 + int(timeslice_list[0].width))
    trend_len = 10

    healing_dict = collections.defaultdict(int)
    overhealing_dict = collections.defaultdict(int)
    damage_dict = collections.defaultdict(int)
    wound_max = 0

    for timeslice in timeslice_list:
        actor_set.update(timeslice.healing_dict)
        actor_set.update(timeslice.damage_dict)

        wound_total = 0
        for actor in timeslice.wound_dict:
            #actor_set.add(actor)
            wound_total += timeslice.wound_dict[actor]

        wound_max = max(wound_max, wound_total)

        for actor in actor_list:
            healing_dict[actor] = max(healing_dict[actor], timeslice.healing_dict[actor])
            overhealing_dict[actor] = max(overhealing_dict[actor], timeslice.overhealing_dict[actor])
            damage_dict[actor] = max(damage_dict[actor], timeslice.damage_dict[actor])

    damageTrend_dict = {}
    healTrend_dict = {}
    actor_list = [x for x in actor_list if x in actor_set]
    for actor in actor_list:
        #actor_set.add(actor)

        damageTrend_dict[actor] = [0 for x in range(int(trend_len / timeslice_list[0].width))]
        healTrend_dict[actor] = [0 for x in range(int(trend_len / timeslice_list[0].width))]

        #print "healing_dict[%s]:\t" % actor,  healing_dict[actor]
        #print "overhealing_dict[%s]:\t" % actor,  overhealing_dict[actor]
        #print "damage_dict[%s]:\t" % actor,  damage_dict[actor]

        height += 20
        height += healing_dict[actor] * heal_scale
        height += overhealing_dict[actor] * heal_scale
        height += damage_dict[actor] * heal_scale

    height += wound_max * wound_scale

    armory_dict = combatlogparser.scrapeArmory(options, actor_set)
    color_dict = combatlogparser.classColors()

    #print "Image size:", width, height

    image_height = height

    image = Image.new('RGB', (int(image_width), int(image_height)))
    draw = ImageDraw.Draw(image)

    for i, timeslice in enumerate(timeslice_list):
        #i += 120
        if (i * timeslice.width) % 60 == 0:
            draw.line([(i, 0), (i, image.size[1])], fill='#666')
        elif (i * timeslice.width) % 10 == 0:
            draw.line([(i, 0), (i, image.size[1])], fill='#333')

        for actor in timeslice.died_dict:
            color = '#%02x%02x%02x' % tuple([int(x * 0.5) for x in color_dict[armory_dict[actor]['class']][0]])

            print i, actor, color

            draw.line([(i, 0), (i, image_height)], fill=color)


        currentHeight = 20
        for actor in actor_list:

            if i == 100:
                draw.text((5, currentHeight + 3), actor, font=font, fill='#999')

            height = 20
            #delta = timeslice.damage_dict[actor] * heal_scale
            color = color_dict[armory_dict[actor]['class']][2]

            if timeslice.cast_dict.get(actor, None):
                #print [(i, currentHeight), (i, currentHeight+height)]
                draw.line([(i, currentHeight), (i, currentHeight+height)], fill=color)
            currentHeight += height


            height = damage_dict[actor] * heal_scale
            delta = timeslice.damage_dict[actor] * heal_scale
            index = min(4, len(timeslice.damageTarget_dict[actor])) - 1
            color = ['#f00', '#c00', '#a00', '#800'][index]

            damageTrend_dict[actor].insert(0, delta)
            damageTrend_dict[actor].pop()

            draw.point((i, currentHeight), fill='#333')
            if damage_dict[actor] > 10000:
                draw.point((i, currentHeight + 10000 * heal_scale), fill='#333')
            if sum(damageTrend_dict[actor]) / trend_len >= 1:
                draw.point((i, currentHeight + sum(damageTrend_dict[actor]) / trend_len), fill='#500')

            if delta:
                draw.line([(i, currentHeight), (i, currentHeight + delta)], fill=color)
            currentHeight += height


            height = overhealing_dict[actor] * heal_scale
            delta = timeslice.overhealing_dict[actor] * heal_scale
            color = '#ff0'

            if delta:
                draw.line([(i, currentHeight + (height - delta)), (i, currentHeight + height)], fill=color)
            currentHeight += height


            height = healing_dict[actor] * heal_scale
            delta = timeslice.healing_dict[actor] * heal_scale
            index = min(4, len(timeslice.healTarget_dict[actor])) - 1
            color = ['#0f0', '#0c0', '#0a0', '#080'][index]

            healTrend_dict[actor].insert(0, delta)
            healTrend_dict[actor].pop()


            draw.point((i, currentHeight), fill='#333')
            if healing_dict[actor] > 10000:
                draw.point((i, currentHeight + 10000 * heal_scale), fill='#333')
            if sum(healTrend_dict[actor]) / trend_len >= 1:
                draw.point((i, currentHeight + sum(healTrend_dict[actor]) / trend_len), fill='#050')

            if delta:
                draw.line([(i, currentHeight), (i, currentHeight + delta)], fill=color)
            currentHeight += height

        for wound, wound_actor in sorted([(v, k) for (k, v) in timeslice.wound_dict.items()], reverse=False):
            try:
                draw.line([(i, currentHeight), (i, currentHeight + wound * wound_scale)], fill=color_dict[armory_dict[wound_actor]['class']][2])
                currentHeight += wound * wound_scale
            except:
                pass
            #currentHeight += wound * wound_scale


            #if timeslice.cast_dict.get(actor, None):
            #    draw.line([(i, currentHeight), (i, currentHeight+100)], fill=color)
            #currentHeight += 100
            #draw.line([(i, currentHeight), (i, currentHeight+timeslice.healing_dict)], fill=color_dict[armory_dict[actor]['class']][2])

    draw.text((5, 3), str(timeslice_list[0].event_list[0]['time']), font=font, fill='#999')

    image.save(file_path)


def combatSvg():
    pass



lf = None

color_dict = {}

def main(sys_argv):
    global options, arguments
    usage(sys_argv)

    #print set(options.prune_str.split(','))

    global color_dict
    raw_dict = {
            'Death Knight': (0.77 , 0.12 , 0.23 ),
            'Druid': (1.00 , 0.49 , 0.04 ),
            'Hunter': (0.67 , 0.83 , 0.45 ),
            'Mage': (0.41 , 0.80 , 0.94 ),
            'Paladin': (0.96 , 0.55 , 0.73 ),
            'Priest': (1.00 , 1.00 , 1.00 ),
            'Rogue': (1.00 , 0.96 , 0.41 ),
            'Shaman': (0.14 , 0.35 , 1.00 ),
            'Warlock': (0.58 , 0.51 , 0.79 ),
            'Warrior': (0.78 , 0.61 , 0.43 ),
            'NPC': (0.50 , 0.40 , 0.10 ),
        }

    raw_dict['Priest'] = tuple([x * 0.7 for x in raw_dict['Priest']])
    raw_dict['Rogue'] = tuple([x * 0.9 for x in raw_dict['Rogue']])

    logFile = combatlogparser.LogFile(arguments)
    #print repr(logFile)
    logFile.prune(set(options.prune_str.split(',')))

    date_str = arguments[0].split('-', 1)[1].split('.')[0]
    file_path = "%s_" + date_str + "_%02d_%s_%s.png"

    for i, combat in enumerate(logFile.combat_list):
        event_list = list(combat.eventIter())

        actor_list = [x.split('/', 1)[-1] for x in combat.getActorSet() if x.startswith('PC/')]
        actor_dict = {}
        for actor in actor_list:
            cast_list = [x for x in event_list if x['sourceName'] == actor and x['prefix'] == 'SPELL' and x['suffix'] in ('_CAST_START', '_CAST_SUCCESS')]

            if cast_list:
                delta_list = []
                last = cast_list.pop(0)
                for event in cast_list:
                    delta_list.append(event['time'] - last['time'])
                    last = event

                delta_dict = collections.defaultdict(int)
                for delta in delta_list:
                    bucket_int = int(float(delta.seconds + delta.microseconds / 1000000.0) * 10)
                    if bucket_int < 100:
                        delta_dict[bucket_int] += 1

                actor_dict[actor] = delta_dict
            #for x in sorted(delta_dict.items()):
            #    print actor, x
        if actor_dict:
            castImage(file_path % ('CastInfo', i, re.sub('[^a-zA-Z]+', '', sorted(combat.prune_set)[0]), 'all'), list(combat.eventIter())[0]['time'], actor_dict)#, sorted(["Tantryst", "Mutagen", "Vampirion", "Ardwen", "Sameil", "Fatima", "Dusken", "Radamanthass", "Bluemorwe"]))

        timeslice_list = []
        event_list.reverse()
        while event_list:
            timeslice_list.append(Timeslice(event_list))

        timelineImage(file_path % ('Timeline', i, re.sub('[^a-zA-Z]+', '', sorted(combat.prune_set)[0]), 'healer'), timeslice_list, sorted(["Tantryst", "Mutagen", "Vampirion", "Ardwen", "Sameil", "Fatima", "Dusken", "Radamanthass", "Bluemorwe"]))
        #for class_str in classColors():
        #    armory_dict = scrapeArmory()
        #    player_list = [k for (k, v) in armory_dict.items() if v['class'] == class_str]
        #    combatImage(file_path % (i, re.sub('[^a-zA-Z]+', '', sorted(combat.prune_set)[0]), class_str.replace(' ', '')), timeslice_list, sorted(player_list))

        #break




if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)

# eof
