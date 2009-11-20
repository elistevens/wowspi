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

def usage(sys_argv):
    parser = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
    module_list = ['basicparse', 'combatgroup', 'stasisutils', 'execution']

    usage_setup(parser)
    for module in module_list:
        globals()[module].usage_setup(parser)
    
    options, arguments = parser.parse_args(sys_argv)
    
    for module in module_list:
        globals()[module].usage_defaults(options)
    usage_defaults(options)

    return options, arguments


def usage_setup(op, **kwargs):
    pass
    #if kwargs.get('dps', True):
    #    op.add_option("--dps"
    #            , help="Compute DPS rankings"
    #            #, metavar="PATH"
    #            , dest="dps_bool"
    #            , action="store_true"
    #            #, type="str"
    #            #, default="armory.db"
    #        )
    #
    #if kwargs.get('execution', True):
    #    op.add_option("--execution"
    #            , help="Compute execution failures."
    #            , dest="execution_bool"
    #            , action="store_true"
    #        )

def usage_defaults(options):
    pass

def pretty(x):
    if isinstance(x, float):
        return "%0.4f" % x
    return str(x)
    
def report(conn, options):
    print options
    
    details_file = file(os.path.join(options.stasis_path, 'execution_details.tsv'), 'w')
    
    needsHeader = True
    header_list = ['combat_id','date_str','size','type','instance','encounter','typeName','normalizedValue','toonName','value']
    print >>details_file, '\t'.join([str(x) for x in header_list])
    
    toon_set = set()
    for row in conn_execute(conn, '''select * from combat join execution on (combat.id = execution.combat_id) order by instance, encounter, typeName, value desc'''):
        try:
            print >>details_file, '\t'.join([pretty(row[x]) for x in header_list])
            toon_set.add(row['toonName'])
        except IndexError, e:
            print 'Error:', e, x
            raise

    final_list = []
    for toonName in toon_set:
        fail_count = conn_execute(conn, '''select count(*) from execution where type = ? and toonName = ?''', ('fail', toonName)).fetchone()[0]
        final_count = int(math.ceil(fail_count * 0.5))
        
        value_avg = 0
        if final_count > 0:
            value_avg = sum([row['normalizedValue'] for row in conn_execute(conn, '''select * from execution where type = ? and toonName = ? order by normalizedValue desc limit ?''', ('fail', toonName, final_count))]) / final_count
            
        final_list.append((value_avg, toonName))

    
    overall_file = file(os.path.join(options.stasis_path, 'execution_overall.tsv'), 'w')
    print >>overall_file, '\t'.join(['toonName', 'avgValue'])
    for t in sorted(final_list):
        print >>overall_file, '\t'.join([pretty(x) for x in t])


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
