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
import glob
import itertools
import json
import math
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
import execution
import armoryutils
import stasisutils
from config import css, load_css, instanceData

from sqliteutils import *

#def usage(sys_argv):
#    parser = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
#    module_list = ['basicparse', 'combatgroup', 'stasisutils', 'execution']
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
#    #if kwargs.get('dps', True):
#    #    op.add_option("--dps"
#    #            , help="Compute DPS rankings"
#    #            #, metavar="PATH"
#    #            , dest="dps_bool"
#    #            , action="store_true"
#    #            #, type="str"
#    #            #, default="armory.db"
#    #        )
#    #
#    #if kwargs.get('execution', True):
#    #    op.add_option("--execution"
#    #            , help="Compute execution failures."
#    #            , dest="execution_bool"
#    #            , action="store_true"
#    #        )
#
#def usage_defaults(options):
#    pass

def pretty(x):
    if isinstance(x, float):
        return "%0.4f" % x
    return str(x)
    
    
class ReportRun(DataRun):
    def __init__(self):
        DataRun.__init__(self, ['ExecutionRun'], [])
        self.version = datetime.datetime.now()
        
    def impl(self, options):
        conn = self.conn
        
        execution_conn = sqlite_connection(os.path.join('data', 'reports', 'execution.db'))
        
        date_str = conn_execute(conn, '''select date_str from execution limit 1''').fetchone()[0]
        
        header_list = ['combat_id','date_str','size','type','instance','encounter','typeName','normalizedValue','toonName','value']
        
        conn_execute(execution_conn, '''create table if not exists execution (id integer primary key, date_str str, type str, combat_id int, size int, instance str, encounter str, typeName str, toonName str, value float default 0.0, normalizedValue float default 0.0)''' )
        conn_execute(execution_conn, '''delete from execution where date_str = ?''' , (date_str,))
        
        #toon_set = set()
        for row in conn_execute(conn, '''select * from combat join execution on (combat.id = execution.combat_id) order by instance, encounter, typeName, value desc'''):
            value_list = []
            for col_str in header_list:
                value_list.append(row[col_str])
                
            conn_execute(execution_conn, '''insert into execution (%s) values (%s)''' % (','.join(header_list), ','.join(['?' for x in header_list])), tuple(value_list))
        execution_conn.commit()


        if hasattr(options, 'stasis_path'):
            details_file = file(os.path.join(options.stasis_path, 'execution_details.tsv'), 'w')
            print >>details_file, '\t'.join([str(x) for x in header_list])


            for row in conn_execute(conn, '''select * from combat join execution on (combat.id = execution.combat_id) order by instance, encounter, typeName, value desc'''):
                print >>details_file, '\t'.join([pretty(row[x]) for x in header_list])
            
            
        fail_list = conn_execute(execution_conn,
                '''select max(normalizedValue) normalizedValue, toonName from execution where type = ? and date_str > ? and typeName not in ('Fel Lightning') group by date_str, instance, encounter, typeName, toonName''',
                ('fail', (datetime.datetime.now() - datetime.timedelta(182)).strftime('%Y-%m-%d'))).fetchall()
        constructBuckets(fail_list)
    
        #final_list = []
        #for toonName in toon_set:
        #    fail_count = conn_execute(conn, '''select count(*) from execution where type = ? and toonName = ?''', ('fail', toonName)).fetchone()[0]
        #    final_count = int(math.ceil(fail_count * 0.5))
        #    
        #    value_avg = 0
        #    if final_count > 0:
        #        value_avg = sum([row['normalizedValue'] for row in conn_execute(conn, '''select * from execution where type = ? and toonName = ? order by normalizedValue desc limit ?''', ('fail', toonName, final_count))]) / final_count
        #        
        #    final_list.append((value_avg, toonName))
        #
        #
        #overall_file = file(os.path.join(options.stasis_path, 'execution_overall.tsv'), 'w')
        #print >>overall_file, '\t'.join(['toonName', 'avgValue'])
        #for t in sorted(final_list):
        #    print >>overall_file, '\t'.join([pretty(x) for x in t])


t2f_dict = {}
def pf(fail_path):
    line_list = [x.split('\t') for x in file(fail_path)]
    toon_index = line_list[0].index('toonName')
    size_index = line_list[0].index('size')
    norm_index = line_list[0].index('normalizedValue')
    
    max_dict = {}
    for sub_list in line_list[1:]:
        if int(sub_list[size_index]) > 20:
            max_dict.setdefault(sub_list[toon_index], 0)
            max_dict[sub_list[toon_index]] = max(sub_list[norm_index], max_dict[sub_list[toon_index]])
    for key, value in max_dict.items():
        t2f_dict.setdefault(key, [])
        t2f_dict[key].append(value)
    

def pall(cutoff=0.5):
    global t2f_dict
    t2f_dict = {}
    print '\n'.join(glob.glob('data/reports/*/execution_details.tsv'))
    #for fail_path in sorted(glob.glob('data/reports/*/execution_details.tsv'), reverse=True)[:10]:
    for fail_path in sorted(glob.glob('data/reports/*/execution_details.tsv'), reverse=True):
        pf(fail_path)
    final_dict = {}
    for toon, fail_list in t2f_dict.items():
        if len(fail_list) >= 5:
            final_dict[toon] = float(len([x for x in fail_list if float(x) >= cutoff])) / len(fail_list)
    ret_list = sorted(final_dict.items(), key=lambda x: x[1])
    for x in ret_list:
        print "%12s" % x[0], '\t', x[1]

def rflist(l):
    return "[%s]" % ", ".join(["%.2f" %x for x in l])

def constructBuckets(fail_list):
    print len(fail_list)
    bucketSize_int = 20
    #bucketFraction_float = 1
    bucketMultiple_int = 2
    
    fail_dict = collections.defaultdict(list)
    
    for fail_row in fail_list:
        fail_dict[fail_row['toonName']].append(fail_row['normalizedValue'])
    print 'Tantryst', len(fail_dict['Tantryst']), rflist(sorted(fail_dict['Tantryst'], reverse=True))
    print 'Kosmo   ', len(fail_dict['Kosmo']), rflist(sorted(fail_dict['Kosmo'], reverse=True))
        
    bucketed_dict = {}
    min_list = [1.0] * bucketSize_int
    max_list = [0.0] * bucketSize_int
    for name_str, full_list in fail_dict.items():
        if len(full_list) < bucketSize_int * bucketMultiple_int:
            #print "Skipping:", name_str, len(full_list)
            continue
        
        full_list.sort(reverse=True)
        #full_list = full_list[0:int(len(full_list)*bucketFraction_float)]
        
        bucketed_dict[name_str] = full_list[0:-1:len(full_list)/bucketSize_int]
        
        min_list = [min(x, y) for x, y in itertools.izip(min_list, bucketed_dict[name_str])]
        max_list = [max(x, y) for x, y in itertools.izip(max_list, bucketed_dict[name_str])]
        
    minmax_list = [list() for x in range(bucketSize_int)]
    for name_str, bucket_list in bucketed_dict.items():
        for sub_list, x in itertools.izip(minmax_list, bucket_list):
            sub_list.append(x)
            
    for sub_list in minmax_list:
        sub_list.sort()
        
    #min_list = [sub_list[1] for sub_list in minmax_list]
    #max_list = [sub_list[-2] for sub_list in minmax_list]
    #min_list = [sub_list[int(len(sub_list) * 0.1)] for sub_list in minmax_list]
    min_list = [sub_list[0] for sub_list in minmax_list]
    max_list = [sub_list[int(len(sub_list) * 1.0 - 1)] for sub_list in minmax_list]
    
        
    print rflist(min_list)
    print rflist(max_list)
    #print bucketed_dict
    
    #def normalize(x, min_x, max_x):
    #    return x
    
    def normalize(x, min_x, max_x):
        if x < min_x:
            return 0.0
        #if min_x == 1.0:
        #    return 1.0
        if x > max_x:
            return 1.0
        
        return (x - min_x * 0.9) / (1 - min_x * 0.9) ** 0.5
        #return ((x-min_x) / (1-min_x)) #** 0.5
        
    normalized_dict = {}
    for name_str, bucket_list in bucketed_dict.items():
        #normalized_dict[name_str] = [(x-min_x)/(max_x-min_x or 1) for x, min_x, max_x in itertools.izip(bucket_list, min_list, max_list)]
        #normalized_dict[name_str] = [(x-min_x) if (x-min_x) >= 0.0 else 0.0 for x, min_x, max_x in itertools.izip(bucket_list, min_list, max_list)]
        #normalized_dict[name_str] = [(x-min_x) ** 0.5 if (x-min_x) >= 0.0 else 0.0 for x, min_x, max_x in itertools.izip(bucket_list, min_list, max_list)]
        normalized_dict[name_str] = [normalize(x, min_x, max_x) for x, min_x, max_x in itertools.izip(bucket_list, min_list, max_list)]
        #normalized_dict[name_str] = bucket_list
    #print normalized_dict
        
    final_dict = {}
    for name_str, normalized_list in normalized_dict.items():
        final_dict[name_str] = sum(normalized_list) / len(normalized_list)
    #print final_dict
    
    for name_str, final_float in sorted(final_dict.items(), key=lambda x: (x[1], x[0])):
        print "%12s" % name_str, "%.4f" % final_float, rflist(bucketed_dict[name_str][:10]), '\t', rflist(normalized_dict[name_str][:10])
        
    return final_dict
    
    

def main(sys_argv, options, arguments):
    try:
        execution.main(sys_argv, options, arguments)
        conn = sqlite_connection(options)
        
        report(conn, options)
        

    finally:
        sqlite_print_perf(options.verbose)
        pass



if __name__ == "__main__":
    options, arguments = usage(sys.argv[1:])
    sys.exit(main(sys.argv[1:], options, arguments) or 0)
    
# eof
