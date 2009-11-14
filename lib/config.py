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

#import basicparse
#import combatgroup
#import armoryutils
#
#def usage(sys_argv):
#    op = optparse.OptionParser()
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
#

wowspi_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

_instance_dict = json.load(file(os.path.join(wowspi_path, 'etc', 'instancedata.json')))
def instanceData():
    return _instance_dict
    #return copy.deepcopy(_instance_dict)


_css_dict = {}
_notFound_dict = {}
def css(color_str, default='#f0f'):
    css_str = color_str
    
    while css_str not in _css_dict and '.' in css_str:
        css_str = css_str.rsplit('.', 1)[0]
        
    if css_str not in _css_dict:
        css_str = color_str

    if color_str not in _css_dict and color_str not in _notFound_dict:
        print "CSS name not found: %s, using %s" % (color_str, css_str)
        _notFound_dict[color_str] = 1
        
    return _css_dict.get(css_str, default)
   
def load_css(name_str='default'):
    global _css_dict
    
    _css_dict = json.load(file(os.path.join(wowspi_path, 'etc', 'css.%s.json' % name_str)))
    
load_css()
    


#def main(sys_argv, options, arguments):
#    #combatgroup.main(sys_argv, options, arguments)
#    #conn = basicparse.sqlite_connection(options)
#    pass
#
#
#
#if __name__ == "__main__":
#    options, arguments = usage(sys.argv[1:])
#    sys.exit(main(sys.argv[1:], options, arguments) or 0)

# eof
