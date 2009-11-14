#!/usr/bin/env python

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
