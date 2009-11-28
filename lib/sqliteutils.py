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

#import cgi
import collections
#import copy
#import csv
import datetime
#import glob
#import itertools
#import json
import optparse
#import os
#import random
#import re
import sqlite3
#import subprocess
import sys
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


_count_dict = collections.defaultdict(int)
_time_dict = collections.defaultdict(datetime.timedelta)
_max_dict = collections.defaultdict(datetime.timedelta)
def conn_execute(conn, sql_str, values_tup=None, many=False):
    if sql_str.startswith('insert into event'):
        key_str = 'insert into event'
    else:
        key_str = sql_str

    _count_dict[key_str] += 1
    
    n = datetime.datetime.now()
    
    try:
        if values_tup is not None:
            if many:
                return conn.executemany(sql_str, values_tup)
            else:
                return conn.execute(sql_str, values_tup)
        else:
            return conn.execute(sql_str)
    except:
        print sql_str
        print repr(values_tup)[:1000]
        raise
    finally:
        td = datetime.datetime.now() - n
        _time_dict[key_str] += td
        _max_dict[key_str] = max(td, _max_dict[key_str])
        

def sqlite_print_perf(verbose=True):
    if verbose:
        print '\n' + '\t'.join(["SQL", "Count", "Avg. Time", "Max Time", "Total Time"])
        for sql_str, x in sorted(_time_dict.items(), key=lambda x: (-x[1], x[0]))[:15]:
            print sql_str
            print '\t', _count_dict[sql_str], '\t', _time_dict[sql_str] / _count_dict[sql_str], '\t', _max_dict[sql_str], '\t', _time_dict[sql_str], '\n'
            
            if _time_dict[sql_str] < datetime.timedelta(seconds=1):
                break


class DurationManager(object):
    def __init__(self, conn, table_str, key_list, value_list):
        self.conn = conn
        self.table_str = table_str
        self.key_list = key_list
        self.value_list = value_list

        self.current_dict = {}
        
        conn_execute(self.conn, '''create table if not exists %s (id integer primary key, start_event_id integer default null, end_event_id integer default null, start_time timestamp, end_time timestamp, %s)''' %
                (self.table_str, ','.join(["%s %s" % x for x in self.key_list + self.value_list])))
        conn_execute(self.conn, '''create index if not exists ndx_%s_event on %s (start_event_id, end_event_id, %s)''' %
                (self.table_str, self.table_str, ','.join([x[0] for x in self.key_list])))
        conn_execute(self.conn, '''create index if not exists ndx_%s_time on %s (start_time, end_time, %s)''' %
                (self.table_str, self.table_str, ','.join([x[0] for x in self.key_list])))
        conn_execute(self.conn, '''create index if not exists ndx_%s_key on %s (%s, start_time, end_time)''' %
                (self.table_str, self.table_str, ','.join([x[0] for x in self.key_list])))
        
        col_str = ','.join([x[0] for x in self.key_list + self.value_list])
        qmk_str = ','.join(['?' for x in self.key_list + self.value_list])
        self.insert_str = '''insert into %s (start_event_id, start_time, %s) values (?, ?, %s)''' % (self.table_str, col_str, qmk_str)

    def eventKey(self, event):
        return tuple([event[x[0]] for x in self.key_list])
        
    def eventValue(self, event):
        return tuple([event[x[0]] for x in self.value_list])

    def add(self, event, key=None, value=None):
        if key is None:
            key = self.eventKey(event)
        if value is None and event:
            value = self.eventValue(event)

        if key in self.current_dict:
            self.remove(key, event)
            
        self.current_dict[key] = conn_execute(self.conn, self.insert_str, (event['id'], event['time']) + key + value).lastrowid
        
    def remove(self, event, key=None):
        if key is None:
            key = self.eventKey(event)
            
        if key in self.current_dict:
            conn_execute(self.conn, '''update %s set end_event_id = ?, end_time = ? where id = ?''' % self.table_str, (event['id'], event['time'], self.current_dict[key]))
            del self.current_dict[key]
        
    def get(self, event=None, key=None, value=None):
        if key is None:
            key = self.eventKey(event)
        if value is None and event:
            value = self.eventValue(event)
        
        ret = None
        if key in self.current_dict:
            ret = conn_execute(self.conn, '''select * from %s where id = ?''' % self.table_str, (self.current_dict[key],)).fetchone()
        elif value:
            self.add(event, key, value)
            ret = conn_execute(self.conn, '''select * from %s where id = ?''' % self.table_str, (self.current_dict[key],)).fetchone()
            
        return ret
    
    def close(self, event):
        for key in self.current_dict:
            self.remove(key, event)
            
        conn_execute(self.conn, '''delete from %s where start_event_id = end_event_id''' % self.table_str)
        
class DataRun(object):
    runner_dict = {}
    
    def __init__(self, prereq_list, table_list):
        self.name = self.__class__.__name__
        
        if self.name not in self.runner_dict:
            self.runner_dict[self.name] = self
        
        self.prereq_list = prereq_list
        self.table_list = table_list
        
        self.version = 0
        self.retcode = 0
        
    def getAllPrereqs(self):
        full_list = []
        
        for prereq_str in self.prereq_list:
            full_list[0:0] = self.runner_dict[prereq_str].getAllPrereqs() + [self.runner_dict[prereq_str]]
            #full_list.extend()
            
        #print self.name, "full", [x.name for x in full_list]
                
        ret_list = []
        #full_list.reverse()
        for prereq in full_list:
            if prereq not in ret_list:
                ret_list.append(prereq)
                
        #print self.name, "ret", [x.name for x in ret_list]
        return ret_list
        
    def main(self, sys_argv):
        self.usage(sys_argv)
        try:
            conn = sqlite_connection(self.options)

            conn_execute(conn, '''create table if not exists run (id integer primary key, time timestamp, mostRecent integer default 0, version, name str)''')

            for prereq in self.getAllPrereqs():
                prereq.execute(conn, self.options)
            self.execute(conn, self.options)
    
        finally:
            sqlite_print_perf(self.options.verbose)
            pass
        
        sys.exit(self.retcode)
        
    def needsRun(self, options):
        #print datetime.datetime.now(), "needsRun", self.name
        #if self.alreadyRan:
        #    return False
        
        if options.force:
            return True
        
        run = conn_execute(self.conn, '''select * from run where name = ? and version = ? and mostRecent = ?''', (self.name, self.version, True)).fetchone()
        
        if not run:
            print datetime.datetime.now(), "No previous run found: %s" % self.name
            return True
        
        for prereq_str in self.prereq_list:
            prerun = conn_execute(self.conn, '''select * from run where name = ? and version = ? and mostRecent = ?''', (self.runner_dict[prereq_str].name, self.runner_dict[prereq_str].version, True)).fetchone()
            
            #print "prerun:", prerun
            
            if run['time'] < prerun['time']:
                print datetime.datetime.now(), "Prerequisite run %s newer than %s" % (prerun['name'], run['time'])
                return True

        print datetime.datetime.now(), "Reusing previous %s run: %s" % (run['name'], run['time'])
        return False



    
    def execute(self, conn, options):
        self.conn = conn
        #print datetime.datetime.now(), "execute", self.name
        
        #if self.alreadyRan:
        #    return
        #
        #for prereq in self.prereq_list:
        #    self.runner_dict[prereq].execute(self.conn, self.options)
            
        if self.needsRun(options):
            self.cleanup()
            n = datetime.datetime.now()
            print datetime.datetime.now(), "Starting: %s..." % self.name
            self.impl(options)
            print datetime.datetime.now(), "Finished: %s (%s)" % (self.name, datetime.datetime.now() - n)
            
            conn_execute(self.conn, '''update run set mostRecent = ? where name = ?''', (False, self.name))
            conn_execute(self.conn, '''insert into run (time, mostRecent, version, name) values (?,?,?,?)''', (datetime.datetime.now(), True, self.version, self.name))
            self.conn.commit()
            
            self.alreadyRan = True
    
    def impl(self, options):
        pass
    
    def cleanup(self):
        print datetime.datetime.now(), "Cleaning: %s..." % self.name
        for table_str in self.table_list:
            conn_execute(self.conn, '''drop table if exists %s''' % table_str)


    def usage(self, sys_argv):
        parser = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
        
        for prereq in self.getAllPrereqs():
            prereq.usage_setup(parser)
        self.usage_setup(parser)
        
        parser.add_option("--db"
                , help="Desired sqlite database output file name."
                , metavar="OUTPUT"
                , dest="db_path"
                , action="store"
                , type="str"
                #, default="output"
            )
        parser.add_option("--force"
                , help="Force reparsing from scratch."
                #, metavar="OUTPUT"
                , dest="force"
                , action="store_true"
                #, type="str"
                #, default="output"
            )
        parser.add_option("-v", "--verbose"
                , help="Print more output; may include debugging information not intended for end-users."
                #, metavar="OUTPUT"
                , dest="verbose"
                , action="store_true"
                #, type="str"
                , default=False
            )

        self.options, self.arguments = parser.parse_args(sys_argv)

        for prereq in self.getAllPrereqs():
            prereq.usage_defaults(self.options)
        self.usage_defaults(self.options)
        
        return self.options, self.arguments

    #def needsSetup(self, parser):
    #    #print datetime.datetime.now(), "needsRun", self.name
    #    if self.alreadySetup:
    #        return
    #    
    #    self.alreadySetup = True
    #    
    #    self.usage_setup(parser)
    #    for prereq in self.prereq_list:
    #        self.runner_dict[prereq].needsSetup(parser)
            

    def usage_setup(self, parser, **kwargs):
        pass
    
    def usage_defaults(self, options):
        pass
    
        
        
    




# eof
