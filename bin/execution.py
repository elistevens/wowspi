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
import subprocess
import sys
import time
import urllib
import urllib2
import xml.etree.ElementTree

import basicparse
import combatgroup
import armoryutils
from config import css, load_css, instanceData

from sqliteutils import *

def usage(sys_argv):
    op = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
    usage_setup(op)
    basicparse.usage_setup(op)
    
    options, arguments = op.parse_args(sys_argv)
    
    basicparse.usage_defaults(options)

    return options, arguments


def usage_setup(op, **kwargs):
    if kwargs.get('dps', True):
        op.add_option("--dps"
                , help="Compute DPS rankings"
                #, metavar="PATH"
                , dest="dps_bool"
                , action="store_true"
                #, type="str"
                #, default="armory.db"
            )

    if kwargs.get('execution', True):
        op.add_option("--execution"
                , help="Compute execution failures."
                , dest="execution_bool"
                , action="store_true"
            )


    
def getAllPresent(conn, combat):
    where_list = []
    
    start_event = basicparse.getEventData(conn, id=combat['start_event_id']).fetchone()
    end_event = basicparse.getEventData(conn, id=combat['end_event_id']).fetchone()
    
    where_list.append(('''time >= ?''', start_event['time']))
    where_list.append(('''time <= ?''', end_event['time']))
    where_list.append(('''combat = ?''', combat['id']))
    where_list.append(('''wipe = ?''', 0))
    
    present_dict = {}
    for row in basicparse.getEventData(conn, 'distinct sourceName', where_list, sourceType='PC'):
        present_dict[row['sourceName']] = 0
        
    return present_dict, where_list



def runAwayDebuff(conn, combat, debuffSpellId, damageSpellId, ignoredSeconds=0, **kwargs):
    fail_dict, where_list = getAllPresent(conn, combat)
    
    application_dict = {}
    
    current = None
    for event in basicparse.getEventData(conn, '*', where_list, 'time', spellId=(debuffSpellId, damageSpellId), destType='PC'):
        if event['eventType'] == 'SPELL_AURA_APPLIED':
            current = event
            application_dict.setdefault(event['destName'], [])
            application_dict[current['destName']].append((current, []))

            
        elif not current:
            pass
                
        #elif event['eventType'] == 'SPELL_AURA_REMOVED' and event['destGUID'] == current['destGUID']:
        #    process_list = fail_list
        #    fail_list = []
            
        elif event['eventType'] == 'SPELL_DAMAGE':
            application_dict[current['destName']][-1][1].append(event)
            #fail_list.append(event)
            
    ignored_td = datetime.timedelta(seconds=ignoredSeconds)
    #fail_dict = {}
    for destName_str, application_list in application_dict.items():
        fail_dict[destName_str] = 0
        
        for event, damage_list in application_list:
            #print destName_str, len(damage_list), '\t', event['time']
            #print '\t' + '\n\t'.join([str(x['time']) for x in damage_list])
            
            while damage_list and event['time'] + ignored_td > damage_list[0]['time']:
                damage_list.pop(0)
            #print destName_str, len(damage_list)
            fail_dict[destName_str] += len(damage_list)
            
    return fail_dict
    


def avoidableDamage(conn, combat, damageSpellId=0, ignoredSeconds=0, ignoredDamage=0, binary=False, **kwargs):
    fail_dict, where_list = getAllPresent(conn, combat)

    application_dict = {}
    
    current = None
    for event in basicparse.getEventData(conn, '*', where_list, 'time', suffix='_DAMAGE', spellId=damageSpellId, destType='PC'):
        application_dict.setdefault(event['destName'], [])
        
        if application_dict[event['destName']] and application_dict[event['destName']][-1][0]['time'] + datetime.timedelta(seconds=4) > event['time']:
            application_dict[event['destName']][-1][1].append(event)
        else:
            application_dict[event['destName']].append((event, [event]))
            
    #print application_dict

            
    ignored_td = datetime.timedelta(seconds=ignoredSeconds)
    for destName_str, application_list in application_dict.items():
        print destName_str, damageSpellId
        
        fail_dict[destName_str] = 0
        for event, damage_list in application_list:
            #print [x['amount'] for x in damage_list], damageSpellId
            
            while damage_list and event['time'] + ignored_td > damage_list[0]['time']:
                damage_list.pop(0)

            if binary:
                fail_dict[destName_str] += len([x['amount'] - ignoredDamage for x in damage_list if x['amount'] and x['amount'] - ignoredDamage > 0])
            else:
                fail_dict[destName_str] += sum([x['amount'] - ignoredDamage for x in damage_list if x['amount'] and x['amount'] - ignoredDamage > 0])
            
    return fail_dict



def chainLightning(conn, combat, damageSpellId, ignoredTargets=2):
    fail_dict, where_list = getAllPresent(conn, combat)

    fail_list = []
    process_list = []
    for event in basicparse.getEventData(conn, '*', where_list, 'time', spellId=damageSpellId, suffix='_DAMAGE', destType='PC'):
        if not fail_list or fail_list[-1][-1]['time'] + datetime.timedelta(seconds=0.5) > event['time']:
            fail_list.append([event])
        else:
            fail_list[-1].append(event)
            
    #fail_dict = {}
    for process_list in fail_list:
        if len(process_list) > ignoredTargets:
            for event in process_list:
                fail_dict.setdefault(event['destName'], 0)
                fail_dict[event['destName']] += len(process_list) - ignoredTargets
            
    return fail_dict


def clumpDebuff(conn, combat, debuffSpellId, ignoredTargets=2):
    fail_dict, where_list = getAllPresent(conn, combat)

    fail_list = []
    process_list = []
    for event in basicparse.getEventData(conn, '*', where_list, spellId=debuffSpellId, eventType='SPELL_AURA_APPLIED', destType='PC'):
        if not fail_list or fail_list[-1][-1]['time'] + datetime.timedelta(seconds=0.5) > event['time']:
            fail_list.append([event])
        else:
            fail_list[-1].append(event)
            
    #fail_dict = {}
    for process_list in fail_list:
        if len(process_list) > ignoredTargets:
            for event in process_list:
                fail_dict.setdefault(event['destName'], 0)
                fail_dict[event['destName']] += len(process_list) - ignoredTargets
            
    return fail_dict


def normalize(fail_dict):
    normalized_dict = {}
    
    if fail_dict:
        max_value = float(max(fail_dict.values()))
        for k,v in fail_dict.items():
            if max_value:
                normalized_dict[k] = v / max_value
            else:
                normalized_dict[k] = 0
        
    return normalized_dict



def avgDictsPerKey(dict_list):
    key_set = set()
    sum_dict = {}
    count_dict = {}
    
    for d in dict_list:
        for k in d.keys():
            key_set.add(k)
            sum_dict.setdefault(k, 0)
            sum_dict[k] += d[k]
    
            count_dict.setdefault(k, 0)
            count_dict[k] += 1
            
    for k in sum_dict:
        sum_dict[k] /= float(count_dict[k])
        
    return sum_dict
    


def main(sys_argv, options, arguments):
    try:
        combatgroup.main(sys_argv, options, arguments)
        conn = sqlite_connection(options)
        
        #if options.bin_path and not glob.glob(os.path.join(options.stasis_path, 'sws-*')):
        #    print datetime.datetime.now(), "Running stasis into: %s" % options.stasis_path
        #    runStasis(conn, options)
        
        overall_dict = {}
        
        
        print datetime.datetime.now(), "Iterating over combats (finding execution failures)..."
        for combat in conn_execute(conn, '''select * from combat order by start_event_id''').fetchall():
            
            start_dt = conn_execute(conn, '''select time from event where id = ?''', (combat['start_event_id'],))
            end_dt = conn_execute(conn, '''select time from event where id = ?''', (combat['end_event_id'],))
            
            if (end_dt - start_dt) >= datetime.timedelta(seconds=110):
                for fail_str, args_dict in instanceData()[combat['instance']][combat['encounter']].get('execution', {}).items():
                    fail_dict = globals().get(args_dict['type'])(conn, combat, **dict([(str(k), v) for k,v in args_dict.items()]))
                    
                    #for k,v in sorted(fail_dict.items(), key=lambda x: (-x[1], x[0])):
                    #    print combat['id'], combat['encounter'], fail_str, k, v
                        
                    overall_dict.setdefault((combat['instance'], combat['encounter'], fail_str), [])
                    overall_dict[(combat['instance'], combat['encounter'], fail_str)].append(fail_dict)
                
        for key in sorted(overall_dict):
            for k,v in sorted(normalize(avgDictsPerKey(overall_dict[key])).items(), key=lambda x: (-x[1], x[0])):
                print "overall", key, k, v
    finally:
        sqlite_print_perf(options.verbose)
        pass



if __name__ == "__main__":
    options, arguments = usage(sys.argv[1:])
    sys.exit(main(sys.argv[1:], options, arguments) or 0)
    
# eof
