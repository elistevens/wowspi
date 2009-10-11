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

from PIL import Image, ImageDraw, ImageFont

import combatlogparser
import combatlogorg
import armoryutils

#version = None
#htmlContent1 = """..."""
#htmlContent2 = """..."""

def usage(sys_argv):
    op = optparse.OptionParser()
    usage_setup(op)
    combatlogorg.usage_setup(op)
    combatlogparser.usage_setup(op)
    armoryutils.usage_setup(op)
    return op.parse_args(sys_argv)

def usage_setup(op, **kwargs):
    pass
    #if kwargs.get('xxx', True):
    #    op.add_option("--xxx"
    #            , help="Desired output file name (excluding extension)."
    #            , metavar="OUTPUT"
    #            , dest="out_str"
    #            , action="store"
    #            , type="str"
    #            , default="output"
    #        )



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

            if event['sourceType'] == 'PC':
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

            if event['destType'] == 'PC' and event['suffix'] == '_DIED':
                self.died_dict[event['destName']] = 1

            for actor in event['wound_dict']:
                self.wound_dict[actor] = max(self.wound_dict[actor], event['wound_dict'][actor])

    #def getList(self):
    #    if self.next:
    #        return [self] + self.next.getList()
    #
    #    return [self]

#class CombatImage(object):
#    def __init__(self, timeslice_list, *actor_list):
def castImage(options, file_path, start_time, actor_dict, actor_list=None, font_path='/Library/Fonts/Arial Bold.ttf'):

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
    
    #armory_dict = combatlogparser.scrapeArmory(options, actor_dict)
    armory_dict = armoryutils.sqlite_scrapeCharacters(options.armorydb_path, actor_list, options.realm_str, options.region_str)
    color_dict = armoryutils.classColors()

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


def timelineImage(options, file_path, timeslice_list, actor_list, font_path='/Library/Fonts/Arial Bold.ttf'):
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

    armory_dict = armoryutils.sqlite_scrapeCharacters(options.armorydb_path, actor_list + list(actor_set), options.realm_str, options.region_str)
    color_dict = armoryutils.classColors()
    #armory_dict = combatlogparser.scrapeArmory(options, actor_set)
    #color_dict = combatlogparser.classColors()

    #print "Image size:", width, height

    image_height = height

    image = Image.new('RGB', (int(image_width), int(image_height)))
    draw = ImageDraw.Draw(image)

    for i, timeslice in enumerate(timeslice_list):
        #armory_dict = armoryutils.sqlite_scrapeCharacters(options.armorydb_path, timeslice.died_dict, options.realm_str, options.region_str)
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
            #armory_dict = armoryutils.sqlite_scrapeCharacters(options.armorydb_path, actor_list, options.realm_str, options.region_str)

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
    options, arguments = usage(sys_argv)

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

    #logFile = combatlogorg.LogFile(arguments)
    ##print repr(logFile)
    #logFile.prune(set(options.prune_str.split(',')))

    #date_str = arguments[0].split('-', 1)[1].split('.')[0]
    #file_path = "%s_" + date_str + "_%02d_%s_%s.png"

    if not options.db_path:
        db_path = options.log_path + ".db"
    else:
        db_path = options.db_path

    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row

    #for i, combat in enumerate(logFile.combat_list):
    for i in [x['combat_id'] for x in conn.execute('''select distinct combat_id from event''').fetchall() if x['combat_id']]:
        print repr(i)
        #event_list = list(combat.eventIter())
        event_list = conn.execute('''select * from event where combat_id = ? order by time''', (i,)).fetchall()
        actor_list = [x['sourceName'].split('/', 1)[-1] for x in event_list if x['sourceName'] and x['sourceName'].startswith('PC/')]

        file_path = "%s_" + event_list[0]['time'].strftime('+%Y-%m-%d_%H-%M-%S') + "_%02d_%s_%s.png"

        #actor_list = [x.split('/', 1)[-1] for x in combat.getActorSet() if x.startswith('PC/')]
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
            #castImage(file_path % ('CastInfo', i, re.sub('[^a-zA-Z]+', '', sorted(combat.prune_set)[0]), 'all'), list(combat.eventIter())[0]['time'], actor_dict)#, sorted(["Tantryst", "Mutagen", "Vampirion", "Ardwen", "Sameil", "Fatima", "Dusken", "Radamanthass", "Bluemorwe"]))
            castImage(options, file_path % ('CastInfo', i, re.sub('[^a-zA-Z]+', '', 'FIXME'), 'all'), event_list[0]['time'], actor_dict)#, sorted(["Tantryst", "Mutagen", "Vampirion", "Ardwen", "Sameil", "Fatima", "Dusken", "Radamanthass", "Bluemorwe"]))

        timeslice_list = []
        event_list.reverse()
        while event_list:
            timeslice_list.append(Timeslice(event_list))

        timelineImage(options, file_path % ('Timeline', i, re.sub('[^a-zA-Z]+', '', 'FIXME'), 'healer'), timeslice_list, sorted(["Tantryst", "Aurastraza", "Detty", "Burlyn", "Daliah", "Mutagen", "Vampirion", "Ardwen", "Sameil", "Fatima", "Dusken", "Radamanthass", "Radanepenthe", "Bluemorwe"]))
        #for class_str in classColors():
        #    armory_dict = scrapeArmory()
        #    player_list = [k for (k, v) in armory_dict.items() if v['class'] == class_str]
        #    combatImage(file_path % (i, re.sub('[^a-zA-Z]+', '', sorted(combat.prune_set)[0]), class_str.replace(' ', '')), timeslice_list, sorted(player_list))

        #break




if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)

# eof
