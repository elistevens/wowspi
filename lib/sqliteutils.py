#!/usr/bin/env python

#import cgi
#import collections
#import copy
#import csv
import datetime
#import glob
#import itertools
#import json
#import optparse
#import os
#import random
#import re
import sqlite3
#import subprocess
#import sys
#import time
#import urllib
#import urllib2
#import xml.etree.ElementTree

#def usage(sys_argv):
#    op = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
#    usage_setup(op)
#    basicparse.usage_setup(op)
#    return op.parse_args(sys_argv)
#
#def usage_setup(op, **kwargs):
#    if kwargs.get('stasisbin', True):
#        op.add_option("--stasisbin"
#                , help="Path to (Apo)StasisCL executable; will run stasis into --stasisout."
#                , metavar="PATH"
#                , dest="bin_path"
#                , action="store"
#                , type="str"
#                #, default="armory.db"
#            )
#
#    if kwargs.get('stasisout', True):
#        op.add_option("--stasisout"
#                , help="Path to base dir for (Apo)StasisCL parses."
#                , metavar="PATH"
#                , dest="stasis_path"
#                , action="store"
#                , type="str"
#                #, default="armory.db"
#            )


def sqlite_connection(options):
    conn = sqlite3.connect(options.db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    
    return conn
    
def sqlite_insureColumns(conn, table_str, column_list):
    col_set = set(conn_execute(conn, '''select * from %s limit 1''' % table_str).fetchone().keys())
    
    for col_str, def_str in column_list:
        if col_str not in col_set:
            conn_execute(conn, '''alter table %s add column %s %s''' % (table_str, col_str, def_str))


_count_dict = {}
_time_dict = {}
def conn_execute(conn, sql_str, values_tup=None):
    _time_dict.setdefault(sql_str, datetime.timedelta())
    _count_dict.setdefault(sql_str, 0)
    _count_dict[sql_str] += 1
    
    n = datetime.datetime.now()
    
    try:
        if values_tup is not None:
            return conn.execute(sql_str, values_tup)
        else:
            return conn.execute(sql_str)
    except:
        print sql_str
        print values_tup
        raise
    finally:
        _time_dict[sql_str] += datetime.datetime.now() - n
        

def sqlite_print_perf(verbose=True):
    if verbose:
        print '\n' + '\t'.join(["SQL", "Count", "Avg. Time", "Total Time"])
        for sql_str, x in sorted(_time_dict.items(), key=lambda x: (-x[1], x[0]))[:20]:
            print sql_str
            print '\t', _count_dict[sql_str], '\t', _time_dict[sql_str] / _count_dict[sql_str], '\t', _time_dict[sql_str], '\n'
        

#def main(sys_argv, options, arguments):
#    combatgroup.main(sys_argv, options, arguments)
#    conn = basicparse.sqlite_connection(options)
#    
#    if options.bin_path and not glob.glob(os.path.join(options.stasis_path, 'sws-*')):
#        print datetime.datetime.now(), "Running stasis into: %s" % options.stasis_path
#        runStasis(conn, options)
#        
#    if options.stasis_path:
#        basicparse.sqlite_insureColumns(conn, 'combat', [('stasis_path', 'str')])
#    
#        print datetime.datetime.now(), "Iterating over combat images (finding stasis parses)..."
#        for combat in conn_execute(conn, '''select * from combat order by start_event_id''').fetchall():
#            start_dt = conn_execute(conn, '''select time from event where id = ?''', (combat['start_event_id'],)).fetchone()[0]
#            
#            conn_execute(conn, '''update combat set stasis_path = ? where id = ?''', (matchCombatToStasis(conn, combat, options.stasis_path), combat['id']))
#    
#        conn.commit()
#
#if __name__ == "__main__":
#    options, arguments = usage(sys.argv[1:])
#    sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof
