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
import sys
import time
import urllib
import urllib2
import xml.etree.ElementTree

import combatlogparser
import combatlogorg
import armoryutils

def usage(sys_argv):
    op = optparse.OptionParser()
    usage_setup(op)
    combatlogparser.usage_setup(op)
    return op.parse_args(sys_argv)

def usage_setup(op, **kwargs):
    if kwargs.get('stasisout', True):
        op.add_option("--stasisout"
                , help="Path to base dir for (Apo)StasisCL parses."
                , metavar="PATH"
                , dest="stasis_path"
                , action="store"
                , type="str"
                #, default="armory.db"
            )


def matchCombatToStasis(conn, combat, stasisbase_path):
    start_dt = conn.execute('''select time from event where id = ?''', (combat['start_event_id'],)).fetchone()[0]
    
    start_seconds = time.mktime(start_dt.timetuple())
    #print start_seconds
    
    stasis_str = armoryutils.getStasisName(combat['instance'], combat['encounter'])
    
    min_float = 1000.0
    for stasis_path in glob.glob(os.path.join(stasisbase_path, 'sws-%s-??????????' % stasis_str)):
        try:
            stasis_seconds = int(stasis_path.rsplit('-', 1)[-1])
            diff_float = stasis_seconds - start_seconds
            
            if diff_float < 60 and diff_float > -10:
                return stasis_path
            
            if abs(diff_float) < abs(min_float):
                min_float = diff_float
        except:
            pass
    else:
        print datetime.datetime.now(), "Min diff found:", min_float, stasis_str, start_seconds, glob.glob(os.path.join(stasisbase_path, 'sws-%s-??????????' % stasis_str))
        
    return None

def main(sys_argv, options, arguments):
    combatlogorg.main(sys_argv, options, arguments)
    conn = combatlogparser.sqlite_connection(options)
    
    if options.stasis_path:
        combatlogparser.sqlite_insureColumns(conn, 'combat', [('stasis_path', 'str')])
    
        print datetime.datetime.now(), "Iterating over combat images (finding stasis parses)..."
        for combat in conn.execute('''select * from combat order by start_event_id''').fetchall():
            start_dt = conn.execute('''select time from event where id = ?''', (combat['start_event_id'],)).fetchone()[0]
            
            conn.execute('''update combat set stasis_path = ? where id = ?''', (matchCombatToStasis(conn, combat, options.stasis_path), combat['id']))
    
        conn.commit()

if __name__ == "__main__":
    options, arguments = usage(sys.argv[1:])
    sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof
