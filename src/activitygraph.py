#!/usr/bin/env python

import cgi
import collections
import copy
import csv
import datetime
import itertools
import json
import math
import optparse
import os
import random
import re
import sqlite3
import sys
import time
import urllib
import urllib2

from PIL import Image, ImageDraw, ImageFont

import basicparse
import combatgroup
import armoryutils
import stasisutils
from config import css, load_css, instanceData

#version = None
#htmlContent1 = """..."""
#htmlContent2 = """..."""

def usage(sys_argv):
    op = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
    usage_setup(op)
    combatgroup.usage_setup(op)
    basicparse.usage_setup(op)
    armoryutils.usage_setup(op)
    stasisutils.usage_setup(op)
    return op.parse_args(sys_argv)

def usage_setup(op, **kwargs):
    if kwargs.get('css', True):
        op.add_option("--css"
                , help="Use color settings from etc/css.NAME.json to render images."
                , metavar="NAME"
                , dest="css_str"
                , action="store"
                , type="str"
                #, default="output"
            )


#
#class Timeslice(object):
#    def __init__(self, event_list, end_time=None, width=0.2):
#        #self.actor = actor
#        #self.prev = prev
#        self.width = width
#        self.leftover = 0.0
#        self.cast_dict = {}
#        self.swing_dict = {}
#        self.died_dict = {}
#        self.healing_dict = collections.defaultdict(int)
#        self.overhealing_dict = collections.defaultdict(int)
#        self.damage_dict = collections.defaultdict(int)
#        self.wound_dict = collections.defaultdict(int)
#        self.event_list = []
#
#        self.healTarget_dict = collections.defaultdict(set)
#        self.damageTarget_dict = collections.defaultdict(set)
#        #self.next = None
#        
#        self.id_set = set()
#
#        #event_iter = iter(event_list)
#
#        while event_list:
#            event = event_list.pop()
#
#            if not end_time:
#                end_time = event['time'] + datetime.timedelta(seconds=self.width)
#
#            if not self.event_list and event['time'] > end_time:
#                end_time = event['time'] + datetime.timedelta(seconds=self.width)
#
#            if event['time'] > end_time:
#                event_list.append(event)
#                #print event['time'], end_time
#                #self.next = Timeslice([event] + list(event_iter), end_time + datetime.timedelta(seconds=self.width), width)
#                break
#
#            self.event_list.append(event)
#            self.id_set.add(event['id'])
#
#            if event['sourceType'] == 'PC':
#                if event['prefix'] in ('SWING',):
#                    self.swing_dict[event['sourceName']] = 1
#
#                if event['suffix'] in ('_CAST_START', '_CAST_SUCCESS'):
#                    self.cast_dict[event['sourceName']] = 1
#
#                if event['suffix'] == '_HEAL':
#                    self.healing_dict[event['sourceName']] += event['amount'] - event['extra']
#                    self.overhealing_dict[event['sourceName']] += event['extra']
#                    self.healTarget_dict[event['sourceName']].add(event['destName'])
#
#                if event['suffix'] == '_DAMAGE':
#                    self.damage_dict[event['sourceName']] += event['amount'] - event['extra']
#                    self.damageTarget_dict[event['sourceName']].add(event['destName'])
#
#            if event['destType'] == 'PC' and event['suffix'] == '_DIED':
#                self.died_dict[event['destName']] = 1
#
#            for actor in event['wound_dict'] or {}:
#                self.wound_dict[actor] = max(self.wound_dict[actor], event['wound_dict'][actor])
#                
#    def getTotalDamage(self, conn, **kwargs):
#        select_str = '''select sum(amount) amount, sum(extra) extra from event where '''
#        where_list = ['''id in (%s)''' % ','.join([str(x) for x in self.id_set]), '''suffix = "_DAMAGE"''']
#        arg_list = []
#        for k, v in kwargs.items():
#            if isinstance(v, str):
#                where_list.append('''%s = ?''' % k)
#                arg_list.append(v)
#            else:
#                where_list.append('''%s in ?''' % k)
#                arg_list.append(v)
#        
#        row = conn.execute(select_str + ' and '.join(where_list), tuple(arg_list)).fetchone()
#
#    #def getList(self):
#    #    if self.next:
#    #        return [self] + self.next.getList()
#    #
#    #    return [self]
#
##class CombatImage(object):
##    def __init__(self, timeslice_list, *actor_list):
#def castImage(options, file_path, start_time, actor_dict, actor_list=None, font_path='/Library/Fonts/Arial Bold.ttf'):
#
#    font = ImageFont.load_default()#ImageFont.truetype(font_path, 14, encoding="unic")
#
#    if actor_list:
#        tmp_dict = {}
#        for actor in actor_list:
#            tmp_dict[actor] = actor_dict[actor]
#        actor_dict = tmp_dict
#
#    image_width = 1000
#    image_height = 40 + 100 * len(actor_dict)
#
#    image = Image.new('RGB', (int(image_width), int(image_height)))
#    draw = ImageDraw.Draw(image)
#    
#    #armory_dict = basicparse.scrapeArmory(options, actor_dict)
#    armory_dict = armoryutils.sqlite_scrapeCharacters(options.armorydb_path, actor_list, options.realm_str, options.region_str)
#    color_dict = armoryutils.classColors()
#
#    for i in range(10):
#        draw.line([(i * 100, 0), (i * 100, image_height)], fill='#333')
#
#
#    currentHeight = 20
#    for actor, delta_dict in sorted(actor_dict.items()):
#        draw.line([(0, currentHeight), (image_width, currentHeight)], fill='#333')
#
#        draw.text((5, currentHeight + 3), actor, font=font, fill='#999')
#
#        light_color = color_dict[armory_dict[actor]['class']][2]
#        dark_color = '#%02x%02x%02x' % tuple([int(x * 0.5) for x in color_dict[armory_dict[actor]['class']][0]])
#
#        line_list = []
#        for i in range(101):
#            line_list.append((i * 10, currentHeight + 100 - min(delta_dict[i], 50) * 2))
#
#            if delta_dict[i]:
#                draw.line([(i * 10, currentHeight + 100 - (min(delta_dict[i], 50) * 2)), (i * 10, currentHeight + 100)], fill=dark_color)
#        draw.line(line_list, fill=light_color)
#
#        currentHeight += 100
#
#    draw.line([(0, currentHeight), (image_width, currentHeight)], fill='#333')
#    draw.text((5, 3), str(start_time), font=font, fill='#999')
#
#    image.save(file_path)


class Timeline(object):
    def __init__(self, conn, start_dt, end_dt, width=0.2):
        self.conn = conn
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.setWidth(width)
        
        #max_dt = self.start_time
        #
        #for event in event_list:
        #    if event['time'] >= max_dt:
        #        self.slice_list.append(Timeslice2(max_dt, width_td))
        #        max_dt += width_td
        #        
        #    self.slice_list[-1].addEvent(event)
            
    def __len__(self):
        len_td = self.end_dt - self.start_dt
        return int(math.ceil((len_td.seconds + len_td.microseconds / 1000000.0) / (self.width_td.seconds + self.width_td.microseconds / 1000000.0)))


    def setWidth(self, width=0.2):
        """'width' is a timespan if a float; otherwise it's a fixed number of buckets (presumed int)."""
        if isinstance(width, float):
            self.width_td = datetime.timedelta(seconds=width)
        else:
            len_td = self.end_dt - self.start_dt
            self.width_td = datetime.timedelta(seconds=((len_td.seconds + len_td.microseconds / 1000000.0) / width))
            #(self.end_dt - self.start_dt) * (1 / float(width))


    def containsTime(self, check_dt, index=None):
        if index is None:
            return self.start_dt <= check_dt and self.end_dt > check_dt
        else:
            return (self.start_dt + (self.width_td * index)) <= check_dt and (self.start_dt + (self.width_td * (index+1))) > check_dt
        
    def getEventData(self, index, select_str='*', where_list=None, **kwargs):
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
        
        where_list.append(('''time >= ?''', self.start_dt + (self.width_td * index)))
        where_list.append(('''time < ?''',  self.start_dt + (self.width_td * (index+1))))

        sql_list = []
        arg_list = []
        for tup in where_list:
            sql_list.append(tup[0])
            if len(tup) > 1:
                arg_list.append(tup[1])
            
        for k, v in kwargs.items():
            if isinstance(v, tuple):
                sql_list.append('''%s in (%s)''' % (k, ','.join(['?' for x in v])))
                arg_list.extend(v)
            else:
                sql_list.append('''%s = ?''' % k)
                arg_list.append(v)
        #if index % 500 == 0:
        #    print ('''select %s from event where ''' % select_str) + ' and '.join(sql_list), tuple(arg_list)
        return self.conn.execute(('''select %s from event where ''' % select_str) + ' and '.join(sql_list), tuple(arg_list))

class Region(object):
    def __init__(self, timeline, label_str, graph_list, width, height, parent_region=None, parent_relationship='under', border=False):
        self.timeline = timeline
        self.label_str = label_str
        self.graph_list = graph_list
        self.parent_region = parent_region
        self.parent_relationship = parent_relationship
        self.border = border
        
        self.max_value = 1.0
        for graph in self.graph_list:
            #for index in range(len(timeline)):
                #if index % 100 == 0:
                #    print datetime.datetime.now(), index
                self.max_value = float(max(self.max_value, graph.computeValues(self)))
                
        self.width = width
        if isinstance(height, float):
            self.height = int(math.ceil(self.max_value * height))
        else:
            self.height = int(height)
        if height < 15:
            height = 15
            
    def render(self, draw):
        tmp_list = list(self.graph_list)
        tmp_list.reverse()
        for graph in tmp_list:
            #print "..."
            graph.render(draw, self)
            
        if self.label_str:
            draw.text((self.getLeft() -95, self.getTop() + 3), self.label_str, font=ImageFont.load_default(), fill=css('text_default'))
        if self.border:
            draw.line([(0, self.getBottom()), (self.getRight(), self.getBottom())], fill=css('region_border'))


    def getTop(self):
        if self.parent_region:
            if self.parent_relationship in ('under',):
                return self.parent_region.getBottom() + 3
            #elif self.parent_relationship in ('tl_child', 'tr_child'):
            #    return self.parent_region.getBottom()
        else:
            return 0
        
    def getBottom(self):
        return self.getTop() + self.height
        
    def getLeft(self):
        if self.parent_region:
            if self.parent_relationship in ('under', 'tl_child'):
                return self.parent_region.getLeft()
            #elif self.parent_relationship in ('tr_child',):
            #    return self.parent_region.getRight() - self.width
                
        else:
            # this is a left margin
            return 100 

    def getRight(self):
        return self.getLeft() + self.width
        

def smooth_NWindowAvg(raw_list, *args):
    x_list = list(raw_list)
    v_list = []
    l = len(raw_list)
    for n in args:
        n = int((n-1) / 2)
        for i in range(len(x_list)):
            if i <= n:
                #print '...', len(x_list[0:i+n+1]), (n * 2.0 + 1.0)
                v = sum(x_list[0:i+n+1]) / (n * 2.0 + 1.0)
            else:
                #print '...', len(x_list[i-n:i+n+1]), (n * 2.0 + 1.0)
                v = sum(x_list[i-n:i+n+1]) / (n * 2.0 + 1.0)
            v_list.append(v)
            
        x_list = v_list
        v_list = []
        
    #print sum(x_list), sum(raw_list)
        
    return x_list
            
class Graph(object):
    def __init__(self, render_list, value_func, smoothing=None, stack_graph=None):
        self.render_list = render_list
        self.value_func = value_func
        self.raw_list = []
        self.value_list = []
        self.smoothing = smoothing
        self.stack_graph = stack_graph
        
    #def getValue(self, region, index):
    #    self.computeValues(region)
    #    return self.value_list[index]
        
    def computeValues(self, region):
        if not self.value_list:
            for i in range(len(region.timeline)):
                self.raw_list.append(float(self.value_func(region.timeline, i)))

            if self.smoothing:
                self.value_list = smooth_NWindowAvg(self.raw_list, *self.smoothing)
            else:
                self.value_list = list(self.raw_list)
            
        if self.stack_graph:
            self.stack_graph.computeValues(region)
            return max([a + b for (a, b) in itertools.izip(self.value_list, self.stack_graph.value_list)])
        return max(self.value_list)
        
    def render(self, draw, region):
        self.computeValues(region)
        
        old_value = 0.0
        for i, value in enumerate(self.value_list):
            value = value / region.max_value * region.height
            
            if value >= 1 or old_value >= 1:
                for render_str, color_str in self.render_list:
                    if render_str == 'uppoint':
                        draw.point((i + region.getLeft(), region.getBottom() - value), fill=color_str)
                    elif render_str == 'upline':
                        if old_value < 1:
                            draw.line([(i + region.getLeft(), region.getBottom() - value), (i + region.getLeft(), region.getBottom() - old_value)], fill=color_str)
                        elif value < 1:
                            draw.line([(i + region.getLeft() - 1, region.getBottom() - value), (i + region.getLeft() - 1, region.getBottom() - old_value)], fill=color_str)
                        elif value >= old_value:
                            draw.line([(i + region.getLeft(), region.getBottom() - value), (i + region.getLeft(), region.getBottom() - old_value - 1)], fill=color_str)
                        else:
                            draw.line([(i + region.getLeft() - 1, region.getBottom() - value - 1), (i + region.getLeft() - 1, region.getBottom() - old_value)], fill=color_str)
                            draw.point((i + region.getLeft(), region.getBottom() - value), fill=color_str)
                            
                    elif render_str == 'upbar':
                        draw.line([(i + region.getLeft(), region.getBottom() - value), (i + region.getLeft(), region.getBottom())], fill=color_str)
                    elif render_str == 'downpoint':
                        draw.point((i + region.getLeft(), region.getTop() + value), fill=color_str)
                    elif render_str == 'downline':
                        if old_value < 1:
                            draw.line([(i + region.getLeft(), region.getTop() - value), (i + region.getLeft(), region.getTop() - old_value)], fill=color_str)
                        elif value < 1:
                            draw.line([(i + region.getLeft() - 1, region.getTop() - value), (i + region.getLeft() - 1, region.getTop() - old_value)], fill=color_str)
                        elif value >= old_value:
                            draw.line([(i + region.getLeft(), region.getTop() + value), (i + region.getLeft(), region.getTop() + old_value + 1)], fill=color_str)
                        else:
                            draw.line([(i + region.getLeft() - 1, region.getTop() + value + 1), (i + region.getLeft() - 1, region.getTop() + old_value)], fill=color_str)
                            draw.point((i + region.getLeft(), region.getTop() + value), fill=color_str)
                            
                    elif render_str == 'downbar':
                        draw.line([(i + region.getLeft(), region.getTop() + value), (i + region.getLeft(), region.getTop())], fill=color_str)
                    elif render_str == 'vbar':
                        if value > 0:
                            draw.line([(i + region.getLeft(), region.getBottom()), (i + region.getLeft(), region.getTop())], fill=color_str)
                    elif render_str == 'imagebar':
                        if value > 0:
                            draw.line([(i + region.getLeft(), 10000), (i + region.getLeft(), 0)], fill=color_str)
            
            old_value = value
    
class TimeGraph(Graph):
    def __init__(self):
        pass

    def computeValues(self, region):
        return 0
    
    def render(self, draw, region):
        start_dt = region.timeline.start_dt
        
        tick_td = datetime.timedelta(seconds=10)
        
        if region.timeline.width_td.seconds < 1:
            next_dt = start_dt + tick_td
            for i in range(len(region.timeline)):
                if region.timeline.containsTime(next_dt, i):
                    draw.line([(i + region.getLeft(), 10000), (i + region.getLeft(), 0)], fill=css('time_second'))
                    next_dt += tick_td
                    
        tick_td = datetime.timedelta(seconds=60)
        
        next_dt = start_dt + tick_td
        for i in range(len(region.timeline)):
            if region.timeline.containsTime(next_dt, i):
                draw.line([(i + region.getLeft(), 10000), (i + region.getLeft(), 0)], fill=css('time_minute'))
                next_dt += tick_td

class DeathGraph(Graph):
    def __init__(self, char_dict):
        self.char_dict = char_dict
        pass

    def computeValues(self, region):
        return 0
    
    def render(self, draw, region):
        start_dt = region.timeline.start_dt
        
        color_dict = armoryutils.classColors()
        
        index = 0
        for death in region.timeline.conn.execute('''select time, destName from event where time >= ? and time <= ? and eventType = ? and destType = ? order by time''',
                                     (region.timeline.start_dt, region.timeline.end_dt, 'UNIT_DIED', 'PC')).fetchall():
            while not region.timeline.containsTime(death['time'], index):
                index += 1
                
            draw.line([(index + region.getLeft(), 10000), (index + region.getLeft(), 0)], fill=color_dict[self.char_dict[death['destName']]['class']][2])

class HeroismGraph(Graph):
    def __init__(self):
        pass

    def computeValues(self, region):
        return 0
    
    def render(self, draw, region):
        heroism_count = 0
        
        for index in range(len(region.timeline)):
            heroism_count += region.timeline.getEventData(index, 'count(*)', eventType='SPELL_AURA_APPLIED', spellName="Heroism", destType='PC').fetchone()[0]
            heroism_count -= region.timeline.getEventData(index, 'count(*)', eventType='SPELL_AURA_REMOVED', spellName="Heroism", destType='PC').fetchone()[0]

            heroism_count += region.timeline.getEventData(index, 'count(*)', eventType='SPELL_AURA_APPLIED', spellName="Bloodlust", destType='PC').fetchone()[0]
            heroism_count -= region.timeline.getEventData(index, 'count(*)', eventType='SPELL_AURA_REMOVED', spellName="Bloodlust", destType='PC').fetchone()[0]
            
            if heroism_count > 0:
                draw.line([(index + region.getLeft(), 10000), (index + region.getLeft(), 0)], fill=css('buff_Heroism'))

def region_title(conn, combat, timeline, region_list):
    char_list = [x['sourceName'] for x in conn.execute('''select distinct sourceName from event where combat_id = ? and sourceType = ?''', (combat['id'], 'PC')).fetchall()]
    char_dict = armoryutils.sqlite_scrapeCharacters(options.armorydb_path, char_list, options.realm_str, options.region_str)
    
    region_list.extend([Region(timeline, '%s: %s, %s' % (combat['instance'], combat['encounter'], timeline.start_dt), [DeathGraph(char_dict), TimeGraph(), HeroismGraph()], len(timeline), 20)])
    
def region_bossDpsHealing(conn, combat, timeline, region_list):
    graph_list = []
    graph_list.append(Graph([('upline', css('heal_boss'))],
            lambda timeline, index: timeline.getEventData(index, 'sum(amount) - sum(extra)', suffix='_HEAL', destType=('NPC','Mount')).fetchone()[0] or 0,
            smoothing=[3,3,3,5]))
    graph_list.append(Graph([('upbar', css('dps_boss_bar')), ('upline', css('dps_boss_trend'))],
            lambda timeline, index: timeline.getEventData(index, 'sum(amount) - sum(extra)', suffix='_DAMAGE', sourceType=('PC','Pet'), destType=('NPC','Mount'), \
                                                          destName=tuple(instanceData()[combat['instance']][combat['encounter']]['boss'])).fetchone()[0] or 0,
            smoothing=[3,3,3,5]))
    graph_list.append(Graph([('upbar', css('dps_trash_bar')), ('upline', css('dps_trash_trend'))],
            lambda timeline, index: timeline.getEventData(index, 'sum(amount) - sum(extra)', suffix='_DAMAGE', sourceType=('PC','Pet'), destType=('NPC','Mount')).fetchone()[0] or 0,
            smoothing=[3,3,3,5]))
    region_list.append(Region(timeline, "Player DPS / Boss Healing", graph_list, len(timeline), 0.005, region_list[-1], 'under', True))
    
def region_healers(conn, combat, timeline, region_list):
    toon_dict = armoryutils.sqlite_scrapeCharacters(options.armorydb_path, [], options.realm_str, options.region_str)
    color_dict = armoryutils.classColors()
    
    for healer_str, healer_int in sorted(combat['healer_list']):
        graph_list = []
        graph_list.append(Graph([('vbar', color_dict[toon_dict[healer_str]['class']][2])],
                lambda timeline, index: timeline.getEventData(index, 'count(*)', suffix=('_CAST_START', '_CAST_SUCCESS'), sourceName=healer_str).fetchone()[0] != 0,
                smoothing=None))
        region_list.append(Region(timeline, ("%s: %s" % (healer_str, healer_int)), graph_list, len(timeline), 15, region_list[-1], 'under'))

        graph_list = []
        graph_list.append(Graph([('upbar', css('heal_pc_inst'))],
                lambda timeline, index: timeline.getEventData(index, 'sum(amount) - sum(extra)', suffix='_HEAL', destType='PC', sourceType='PC', sourceName=healer_str).fetchone()[0] or 0,
                smoothing=None))
        region_list.append(Region(timeline, "  Healing", graph_list, len(timeline), 0.005, region_list[-1], 'under'))

        graph_list = []
        graph_list.append(Graph([('downbar', css('overheal_pc_inst'))],
                lambda timeline, index: timeline.getEventData(index, 'sum(extra)', suffix='_HEAL', destType='PC', sourceType='PC', sourceName=healer_str).fetchone()[0] or 0,
                smoothing=None))
        region_list.append(Region(timeline, "  Overhealing", graph_list, len(timeline), 0.005, region_list[-1], 'under', True))
        
def region_dps(conn, combat, timeline, region_list):
    toon_dict = armoryutils.sqlite_scrapeCharacters(options.armorydb_path, [], options.realm_str, options.region_str)
    color_dict = armoryutils.classColors()
    
    for dps_str, dps_int in combat['dps_list']:
        graph_list = []
        graph_list.append(Graph([('vbar', color_dict[toon_dict[dps_str]['class']][2])],
                lambda timeline, index: timeline.getEventData(index, 'count(*)', suffix=('_CAST_START', '_CAST_SUCCESS'), sourceName=dps_str).fetchone()[0] != 0,
                smoothing=None))
        region_list.append(Region(timeline, ("%s: %s" % (dps_str, dps_int)), graph_list, len(timeline), 15, region_list[-1], 'under'))

        graph_list = []
        graph_list.append(Graph([('upbar', css('dps_boss_bar')), ('upline', css('dps_boss_trend'))],
                lambda timeline, index: timeline.getEventData(index, 'sum(amount) - sum(extra)', suffix='_DAMAGE', sourceType=('PC','Pet'), destType=('NPC','Mount'), sourceName=dps_str, \
                                                              destName=tuple(instanceData()[combat['instance']][combat['encounter']]['boss'])).fetchone()[0] or 0,
                smoothing=[3,3,3,5]))
        graph_list.append(Graph([('upbar', css('dps_trash_bar')), ('upline', css('dps_trash_trend'))],
                lambda timeline, index: timeline.getEventData(index, 'sum(amount) - sum(extra)', suffix='_DAMAGE', sourceType=('PC','Pet'), destType=('NPC','Mount'), sourceName=dps_str).fetchone()[0] or 0,
                smoothing=[3,3,3,5]))
        region_list.append(Region(timeline, "  Damage", graph_list, len(timeline), 0.005, region_list[-1], 'under', True))


def main(sys_argv, options, arguments):
    stasisutils.main(sys_argv, options, arguments)
    conn = basicparse.sqlite_connection(options)
    
    if options.css_str:
        load_css(options.css_str)
    
    print datetime.datetime.now(), "Iterating over combat images..."
    for combat in conn.execute('''select * from combat order by start_event_id''').fetchall():
        
        #if combat['id'] < 5:
        #    continue

        time_list = [x['time'] for x in conn.execute('''select time from event where combat_id = ?''', (combat['id'],)).fetchall()]
        start_dt = min(time_list)
        end_dt = max(time_list)
        
        timeline = Timeline(conn, start_dt, end_dt, width=0.5)

        if combat['stasis_path']:
            stasisutils.removeImages(conn, combat)
                
        file_list = []
        file_list.append(re.sub('[^a-zA-Z0-9_-]', '_', combat['instance']))
        file_list.append(re.sub('[^a-zA-Z0-9_-]', '_', combat['encounter']))
        file_list.append(re.sub('[^a-zA-Z0-9_-]', '_', str(timeline.start_dt)).rsplit('.', 1)[0].replace(':', '-'))
        file_list.append('%s')
        
        file_base = '_'.join(file_list) + '.png'
        
        print datetime.datetime.now(), "Rendering: %s" % (file_base % '...')
            
        for type_str in ('damage_out', 'healing', 'damage_in'):
            if combat['stasis_path']:
                file_path = os.path.join(combat['stasis_path'], file_base % type_str)
                stasisutils.addImage(conn, combat, file_path, type_str)
            elif options.stasis_path:
                file_path = os.path.join(options.stasis_path, file_base % type_str)
            
            
            region_list = []
            region_title(conn, combat, timeline, region_list)
            region_bossDpsHealing(conn, combat, timeline, region_list)
            if type_str == 'damage_out':
                region_dps(conn, combat, timeline, region_list)
            if type_str == 'healing':
                region_healers(conn, combat, timeline, region_list)
            
            image = Image.new('RGB', (int(region_list[0].getRight()), int(max([x.getBottom() for x in region_list]))), css('background'))
            draw = ImageDraw.Draw(image)
    
            for region in region_list:
                region.render(draw)
            
            image.save(file_path)
            



if __name__ == "__main__":
    options, arguments = usage(sys.argv[1:])
    sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof
