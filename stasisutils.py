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

import combatlogparser
import combatlogorg
import armoryutils

def usage(sys_argv):
    op = optparse.OptionParser()
    usage_setup(op)
    combatlogparser.usage_setup(op)
    return op.parse_args(sys_argv)

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


def main(sys_argv, options, arguments):
    combatlogorg.main(sys_argv, options, arguments)
    conn = combatlogparser.sqlite_connection(options)
    
    if options.bin_path and not glob.glob(os.path.join(options.stasis_path, 'sws-*')):
        print datetime.datetime.now(), "Running stasis into: %s" % options.stasis_path
        runStasis(conn, options)
        
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
