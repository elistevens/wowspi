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

import config
from sqliteutils import *

def usage(sys_argv):
    options = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
    usage_setup(options)
    basicparse.usage_setup(options)
    
   
    options, arguments = op.parse_args(sys_argv)
    
    basicparse.usage_defaults(options)
    usage_defaults(options)
    
    return options, arguments


def usage_setup(op, **kwargs):
    if kwargs.get('stasisbin', True):
        op.add_option("--stasisbin"
                , help="Path to (Apo)StasisCL executable; will run stasis into --stasisout."
                , metavar="PATH"
                , dest="bin_path"
                , action="store"
                , type="str"
                #, default="armory.db"
            )

    if kwargs.get('stasisout', True):
        op.add_option("--stasisout"
                , help="Path to base dir for (Apo)StasisCL parses."
                , metavar="PATH"
                , dest="stasis_path"
                , action="store"
                , type="str"
                #, default="armory.db"
            )

def usage_defaults(options):
    #print "before", options
    if options.date_str:
        options.stasis_path = os.path.join(config.wowspi_path, 'data', 'reports', options.date_str)
    #    
    #    #print options
    #else:
    #    if hasattr(options, 'log_path') and re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', options.log_path):
    #        try:
    #            options.log_path = (glob.glob(options.log_path) + glob.glob(os.path.join(config.wowspi_path, 'data', 'logs', '*' + options.log_path + '*')))[0]
    #        except:
    #            pass
    #        
    #    if hasattr(options, 'db_path') and re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', options.db_path):
    #        options.db_path = os.path.join(config.wowspi_path, 'data', 'parses', options.db_path + '.db')
    #
    ##return options, arguments


def matchCombatToStasis(conn, combat, stasisbase_path):
    start_dt = conn_execute(conn, '''select time from event where id = ?''', (combat['start_event_id'],)).fetchone()[0]
    
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

def addImage(conn, combat, file_path, tab_str):
    file_str = file_path.rsplit('/', 1)[-1]
    
    div_str = '''<div class="tab" id="tab_%s">''' % tab_str
    comment_str = '''<!-- wowspi start -->%s<!-- wowspi end -->'''
    img_str = '''<br/><br/><br/><img src="%s" /><br /><br />''' % file_str

    index_str = file(os.path.join(combat['stasis_path'], 'index.html')).read()
    index_str = re.sub(div_str, div_str + (comment_str % img_str), index_str)
        
    file(os.path.join(combat['stasis_path'], 'index.html'), 'w').write(index_str)

def removeImages(conn, combat):
    index_str = file(os.path.join(combat['stasis_path'], 'index.html')).read()
    index_str = re.sub('''<!-- wowspi start -->.*?<!-- wowspi end -->''', '', index_str)
    file(os.path.join(combat['stasis_path'], 'index.html'), 'w').write(index_str)
    
def runStasis(conn, options):
    if not os.path.exists(options.stasis_path):
        os.mkdir(options.stasis_path)
    cmd_list = [os.path.join(options.bin_path, 'stasis'), 'add', '-dir', options.stasis_path, '-file', options.log_path, '-server', options.realm_str, '-attempt', '-overall', '-combine', '-nav']

    env_dict = copy.deepcopy(os.environ)
    if 'PERL5LIB' in env_dict:
        env_dict['PERL5LIB'] += (':%s' % os.path.join(options.bin_path, 'lib'))
    else:
        env_dict['PERL5LIB'] = os.path.join(options.bin_path, 'lib')
    
    subprocess.call(cmd_list, env=env_dict)
    
    subprocess.call(['cp', '-r', os.path.join(options.bin_path, 'extras'), options.stasis_path])
    
    css_str = file(os.path.join(options.bin_path, 'extras', 'sws2.css')).read()
    new_str = '''.swsmaster div.tabContainer {
    text-align: center;
}

.swsmaster div.tabContainer div.tabBar, .swsmaster div.tabContainer div.tab table {'''

    css_str = css_str.replace('''.swsmaster div.tabContainer {''', new_str)
    
    file(os.path.join(options.stasis_path, 'extras', 'ses2.css'), 'w').write(css_str)
    subprocess.call(['rm', '-rf', os.path.join(options.stasis_path, 'extras', '.svn')])


def main(sys_argv, options, arguments):
    combatgroup.main(sys_argv, options, arguments)
    conn = basicparse.sqlite_connection(options)
    
    if options.bin_path and not glob.glob(os.path.join(options.stasis_path, 'sws-*')):
        print datetime.datetime.now(), "Running stasis into: %s" % options.stasis_path
        runStasis(conn, options)
        
    if options.stasis_path:
        basicparse.sqlite_insureColumns(conn, 'combat', [('stasis_path', 'str')])
    
        print datetime.datetime.now(), "Iterating over combat images (finding stasis parses)..."
        for combat in conn_execute(conn, '''select * from combat order by start_event_id''').fetchall():
            start_dt = conn_execute(conn, '''select time from event where id = ?''', (combat['start_event_id'],)).fetchone()[0]
            
            conn_execute(conn, '''update combat set stasis_path = ? where id = ?''', (matchCombatToStasis(conn, combat, options.stasis_path), combat['id']))
    
        conn.commit()

if __name__ == "__main__":
    options, arguments = usage(sys.argv[1:])
    sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof