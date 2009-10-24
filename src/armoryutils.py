#!/usr/bin/env python

import cgi
import collections
import copy
import csv
import datetime
import itertools
import json
import optparse
import random
import re
import sqlite3
import sys
import time
import urllib
import urllib2
import xml.etree.ElementTree

from config import instanceData


def usage(sys_argv):
    op = optparse.OptionParser("Usage: wowspi %s [options]" % __file__.rsplit('/')[-1].split('.')[0])
    usage_setup(op)
    return op.parse_args(sys_argv)

def usage_setup(op, **kwargs):
    if kwargs.get('armorydb', True):
        op.add_option("--armorydb"
                , help="Desired sqlite database output file name."
                , metavar="DB"
                , dest="armorydb_path"
                , action="store"
                , type="str"
                , default="armory.db"
            )

    if kwargs.get('realm', True):
        op.add_option("--realm"
                , help="Realm to use for armory data queries."
                , metavar="REALM"
                , dest="realm_str"
                , action="store"
                , type="str"
                , default="Proudmoore"
            )
    
    if kwargs.get('region', True):
        op.add_option("--region"
                , help="Region to use for armory data queries (www, eu, kr, cn, tw)."
                , metavar="REGION"
                , dest="region_str"
                , action="store"
                , type="str"
                , default="www"
            )



armoryField_list = ['name', 'class', 'level', 'guildName', 'faction', 'gender', 'race']

def sqlite_scrapeCharacters(db_path, name_list, realm_str, region_str, maxAge_td=datetime.timedelta(14), force=False):
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    
    try:
        row_list = conn.execute('''select name from toon where updatedAt > ?''', (datetime.datetime.now() - maxAge_td,))
        #print "row_list", row_list
    except Exception, e:
        print "Dropping...", e
        row_list = []
        conn.execute('''drop table if exists toon''')
        conn.execute('''create table toon (id integer primary key, updatedAt timestamp, %s, specName1, specPoints1, specName2, specPoints2)''' % ', '.join(armoryField_list))
        
    name_set = set()
    for row in row_list:
        name_set.add(row['name'])
    
    #print "name_list, name_set:", name_list, name_set
    for name_str in name_list or []:
        if name_str not in name_set:
            armory_dict = dict_scrapeCharacter(name_str, realm_str, region_str)
            
            #print armory_dict
            
            if armory_dict:
                colval_list = list(armory_dict.items())
                
                col_list = [x[0] for x in colval_list]
                val_list = [x[1] for x in colval_list]
                
                conn.execute('''insert into toon (updatedAt, %s) values (?, %s) ''' % (', '.join(col_list), ', '.join(['?' for x in col_list])), tuple([datetime.datetime.now()] + val_list))
    conn.commit()
    
    return dict([(x['name'], x) for x in conn.execute('''select * from toon''').fetchall()])
    
    
    
def dict_scrapeCharacter(name_str, realm_str, region_str):
    armory_dict = {}
    try:
        opener = urllib2.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X; en-US; rv:1.8.1.6) Gecko/20070725 Firefox/2.0.0.6')]
        
        time.sleep(5)
        xml_str = opener.open("http://%s.wowarmory.com/character-sheet.xml?r=%s&n=%s" % (region_str, realm_str, name_str)).read()
        armory_xml = xml.etree.ElementTree.XML(xml_str)
        
        #print "http://%s.wowarmory.com/character-sheet.xml?r=%s&n=%s" % (region_str, realm_str, name_str)
        #print armory_xml, list(armory_xml.getchildren())
        
        character_elem = armory_xml.find('characterInfo').find('character')
        
        #print character_elem, character_elem.attrib
        
        for col_str in armoryField_list:
            try:
                armory_dict[col_str] = character_elem.get(col_str)
            except:
                pass
            
        for talent_elem in armory_xml.find('characterInfo').find('characterTab').find('talentSpecs').findall('talentSpec'):
            index_str = talent_elem.get('group')
            
            armory_dict['specName' + index_str] = talent_elem.get('prim')
            armory_dict['specPoints' + index_str] = '/'.join([talent_elem.get('tree' + x) for x in ('One', 'Two', 'Three')])

        return armory_dict
    except Exception, e:
        print e
        #raise
        return {}

def instanceData():
    return {
        "Naxxramas": {
            "Anub'Rekhan": {
                "boss": ["Anub'Rekhan"],
                "mobs": [],
            },
            "Grand Widow Faerlina": {
                "boss": ["Grand Widow Faerlina"],
                "mobs": [],
            },
            "Maexxna": {
                "boss": ["Maexxna"],
                "mobs": [],
            },
            "Noth the Plaguebringer": {
                "boss": ["Noth the Plaguebringer"],
                "mobs": ["Plagued Champion", "Plagued Guardian"],
            },
            "Heigan the Unclean": {
                "boss": ["Heigan the Unclean"],
                "mobs": [],
            },
            "Loatheb": {
                "boss": ["Loatheb"],
                "mobs": [],
            },
            "Instructor Razuvious": {
                "boss": ["Instructor Razuvious"],
                "mobs": [],
            },
            "Gothik the Harvester": {
                "boss": ["Gothik the Harvester"],
                "mobs": ["Unrelenting Trainee","Unrelenting Deathknight","Unrelenting Rider"
                            "Spectral Trainee","Spectral Deathknight","Spectral Rider","Spectral Horse"],
            },
            "Four Horsemen": {
                "boss": ["Thane Korth'azz","Lady Blaumeux","Baron Rivendare","Sir Zeliek"],
                "mobs": [],
            },
            "Patchwerk": {
                "boss": ["Patchwerk"],
                "mobs": [],
            },
            "Grobbulus": {
                "boss": ["Grobbulus"],
                "mobs": [],
            },
            "Gluth": {
                "boss": ["Gluth"],
                "mobs": ["Zombie Chow"],
            },
            "Thaddius": {
                "boss": ["Thaddius"],
                "mobs": ["Feugen","Stalagg"],
            },
            "Sapphiron": {
                "boss": ["Sapphiron"],
                "mobs": [],
            },
            "Kel'Thuzad": {
                "boss": ["Kel'Thuzad"],
                "mobs": ["Soldier of the Frozen Wastes","Unstoppable Abomination","Soul Weaver","Guardian of Icecrown"],
            },
        },
        "The Obsidian Sanctum": {
            "Sartharion": {
                "boss": ["Sartharion"],
                "mobs": ["Shadron", "Vesperon", "Tenebron"],
            },
        },
        "The Eye of Eternity": {
            "Malygos": {
                "boss": ["Malygos"],
                "mobs": ["Nexus Lord", "Scion of Eternity"],
            },
        },
        "Ulduar": {
            #"Flame Leviathan": {
            #    "boss": ["Flame Leviathan"],
            #    "mobs": [],
            #},
            "Ignis the Furnace Master": {
                "boss": ["Ignis the Furnace Master"],
                "mobs": [],
            },
            "Razorscale": {
                "boss": ["Razorscale"],
                "mobs": ["Dark Rune Sentinel", "Dark Rune Watcher", "Dark Rune Guardian"],
            },
            "XT-002 Deconstructor": {
                "boss": ["XT-002 Deconstructor"],
                "mobs": ["Heart of the Deconstructor"],
            },
            "Assembly of Iron": {
                "boss": ["Steelbreaker", "Runemaster Molgeim", "Stormcaller Brundir"],
                "mobs": [],
            },
            "Kologarn": {
                "boss": ["Kologarn"],
                "mobs": [],
            },
            "Auriya": {
                "boss": ["Auriya"],
                "mobs": [],
            },
            "Mimiron": {
                "boss": ["Leviathan Mk II", "VX-001", "Aerial Command Unit"],
                "mobs": ["Assault Bot", "Junk Bot"],
            },
            "Freya": {
                "boss": ["Freya"],
                "mobs": [],
            },
            "Thorim": {
                "boss": ["Thorim", "Runic Colossus", "Ancient Rune Giant"],
                "mobs": ["Dark Rune Champion", "Dark Rune Evoker", "Dark Rune Warbringer", "Dark Rune Commoner", "Dark Rune Acolyte", "Iron Ring Guard", "Iron Honor Guard"],
            },
            "Hodir": {
                "boss": ["Hodir"],
                "mobs": [],
            },
            "General Vezax": {
                "boss": ["General Vezax"],
                "mobs": ["Saronite Animus"],
                "stasis": "vezax",
            },
            "Yogg-Saron": {
                "boss": ["Guardian of Yogg-Saron", "Crusher Tentacle", "Brain of Yogg-Saron", "Yogg-Saron"],
                "mobs": ["Corruptor Tentacle", "Constrictor Tentacle", "Immortal Guardian"],
            },
            "Algalon": {
                "boss": ["Algalon the Observer"],
                "mobs": [],
            },
        },
        "Trial of the Crusader": {
            "Northrend Beasts": {
                "boss": ["Gormok the Impaler","Acidmaw","Dreadscale","Icehowl"],
                "mobs": [],
            },
            "Lord Jaraxxus": {
                "boss": ["Lord Jaraxxus"],
                "mobs": [],
            },
            "Twin Val'kyr": {
                "boss": ["Eydis Darkbane","Fjola Lightbane"],
                "mobs": [],
            },
            "Faction Champions": {
                "boss": ["Gorgrim Shadowcleave","Birana Stormhoof","Erin Misthoof","Ruj'kah","Ginselle Blightslinger","Liandra Suncaller",
                            "Malithas Brightblade","Caiphus the Stern","Vivienne Blackwhisper","Maz'dinah","Broln Stouthorn","Thrakgar",
                            "Harkzog","Narrhok Steelbreaker",
                            "Tyrius Duskblade","Kavina Grovesong","Melador Valestrider","Alyssia Moonstalker","Nozle Whizzlestick",
                            "Velanaa","Baelnor Lightbearer","Anthar Forgemender","Brienna Nightfell","Irieth Shadowstep","Shaabad",
                            "Saamul","Serissa Grimdabbler","Shocuul",
                        ],
                "mobs": [],
            },
            "Anub'arak": {
                "boss": ["Anub'arak"],
                "mobs": ["Nerubian Burrower", "Swarm Scarab"],
            },
        },
        "Onyxia's Lair": {
            "Onyxia": {
                "boss": ["Onyxia"],
                "mobs": ["Onyxian Lair Guard", "Onyxian Whelp"],
            },
        },
    }
    
def getBossMobs():
    boss_list = []
    
    for instance, instance_dict in instanceData().items():
        for encounter, encounter_dict in instance_dict.items():
            boss_list.extend(encounter_dict['boss'])
            
    return boss_list

def getMobs():
    mobs_list = []
    
    for instance, instance_dict in instanceData().items():
        for encounter, encounter_dict in instance_dict.items():
            mobs_list.extend(encounter_dict['mobs'])
            
    return mobs_list

def getAllMobs():
    mobs_list = []
    
    for instance, instance_dict in instanceData().items():
        for encounter, encounter_dict in instance_dict.items():
            mobs_list.extend(encounter_dict['boss'])
            mobs_list.extend(encounter_dict['mobs'])
            
    return mobs_list

def encounterByMob(npc_str):
    for instance, instance_dict in instanceData().items():
        for encounter, encounter_dict in instance_dict.items():
            if npc_str in encounter_dict['boss']:
                return encounter
            if npc_str in encounter_dict['mobs']:
                return encounter
    
def instanceByMob(npc_str):
    for instance, instance_dict in instanceData().items():
        for encounter, encounter_dict in instance_dict.items():
            if npc_str in encounter_dict['boss']:
                return instance
            if npc_str in encounter_dict['mobs']:
                return instance

def getStasisName(instance, encounter):
    data_dict = instanceData()[instance][encounter]
    
    return data_dict.get('stasis', re.sub('[^a-z]', '', encounter.lower()))

def classColors():
    color_dict = {
            'Death Knight': ((196,  30,  59), (0.77, 0.12, 0.23), '#C41F3B'),
            'Druid':        ((250, 125,  10), (0.98, 0.49, 0.04), '#FA7D0A'),
            'Hunter':       ((171, 212, 115), (0.67, 0.83, 0.45), '#ABD473'),
            'Mage':         ((105, 204, 240), (0.41, 0.80, 0.94), '#69CCF0'),
            'Paladin':      ((245, 140, 186), (0.96, 0.55, 0.73), '#F58CBA'),
            'Priest':       ((250, 250, 250), (0.98, 0.98, 0.98), '#FAFAFA'),
            'Rogue':        ((250, 245, 105), (0.98, 0.96, 0.41), '#FAF569'),
            'Shaman':       (( 36,  89, 250), (0.14, 0.35, 0.98), '#2459FA'),
            'Warlock':      ((148, 130, 201), (0.58, 0.51, 0.79), '#9482C9'),
            'Warrior':      ((199, 156, 110), (0.78, 0.61, 0.43), '#C79C6E'),
        }

    return color_dict



def main(sys_argv):
    options, arguments = usage(sys_argv)
    
    sqlite_scrapeCharacters(options.armorydb_path, arguments, options.realm_str, options.region_str)



if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)

# eof
