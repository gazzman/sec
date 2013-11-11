#!/usr/bin/python

__version__ = ".00"
__author__ = "gazzman"
__copyright__ = "(C) gazzman GNU GPL 3."
__contributors__ = []

from datetime import datetime
import lxml.etree as etree
import os
import re
import sys
import urllib2

try: from sec.xbrl_retreiver import IMPORTED_SCHEMA_DIR, SERVER, UASTRING
except ImportError: 
    IMPORTED_SCHEMA_DIR = 'imported_schemas'
    SERVER = 'http://sec.gov'
    UASTRING=('Mozilla/5.0 (X11; Linux x86_64; rv:10.0.5) Gecko/20120606'
              + 'Firefox/10.0.5')

HEADER = {'User-Agent' : UASTRING}
FTYPES = ['schema', # schema: contains detailed info about tag
          'instance', # instance: contains the data
          'cal', # calculation linkbase
          'def', # definition linkbase
          'lab', # label linkbase
          'pre', # presentaion linkbase
]

DATEFMT = '%Y-%m-%d'
DATETIMEFMT = '%Y-%m-%dT%H:%M:%S'

def snake_title(string):
    string = string.replace(' ', '')
    return re.sub('(?!^)(A|[A-Z]+)', r'_\1', string).lower() # thanks nickl-

def get_schema(uri, refresh=False):
    fname = uri.split('/')[-1]
    rel_path = '%s/%s' % (IMPORTED_SCHEMA_DIR, fname)
    if not os.path.exists(IMPORTED_SCHEMA_DIR):
        os.makedirs(IMPORTED_SCHEMA_DIR)
        refresh = True

    if refresh == True or not os.path.exists(rel_path):
        outmsg = 'Grabbing schema %s' % fname
        print >> sys.stderr, outmsg
        req = urllib2.Request(uri, headers=HEADER)
        page = urllib2.urlopen(req)
        with open(rel_path, 'wb') as f:
            f.write(page.read())

    return etree.parse(rel_path)

def get_tag_schema(tag, s):
    xmlns = s['schema'].getroot().nsmap[None]
    def_ns = {'xmlns': xmlns}

    namespace, name = tag.split(':')
    tag_schemas = s['schema'].xpath("//xmlns:element[@name='%s']" % name, namespaces=def_ns)
    if len(tag_schemas) < 1:
        ns_uri = inst_ns[namespace]
        schema_import = s['schema'].xpath("//xmlns:import[@namespace='%s']" % ns_uri,
                                            namespaces=def_ns)
        assert len(schema_import) == 1
        schema_url = schema_import[0].attrib['schemaLocation']
        s[namespace] = get_schema(schema_url)
        tag_schemas = s[namespace].xpath("//xs:element[@name='%s']" % name, 
                                        namespaces=s[namespace].getroot().nsmap)
    assert len(tag_schemas) == 1
    return tag_schemas[0]

if __name__ == '__main__':
    base_fname = sys.argv[1]
    reporting_data_fname = sys.argv[2]
    s = {}
    for ftype in FTYPES:
        try:
            if ftype == 'schema':
                s[ftype] = etree.parse('%s.xsd' % base_fname)
            elif ftype == 'instance':
                s[ftype] = etree.parse('%s.xml' % base_fname)
            else:
                s[ftype] = etree.parse('%s_%s.xml' % (base_fname, ftype))
        except IOError as err:
                print >> sys.stderr, '%s s missing' % ftype.upper()
    inst_ns = s['instance'].getroot().nsmap

    with open(reporting_data_fname, 'r') as f:
        tags = [ line.strip() for line in f.read().split('\n') if line != '' ]
    tags = [ tag for tag in tags if tag[0] != '#' ]
    namespaces = [ tag.split(':')[0] for tag in tags ]
    
    for tag in tags:
        tag_schema = get_tag_schema(tag, s)
        period_type = tag_schema.attrib['{%s}periodType' % inst_ns['xbrli']]
        for r in s['instance'].xpath('//%s' % tag, namespaces=inst_ns):
            context_ref = r.attrib['contextRef']
            period_tag = s['instance'].xpath("//xbrli:context[@id='%s']/xbrli:period" % context_ref,
                                             namespaces=inst_ns)
            assert len(period_tag) == 1
            period_tag = period_tag[0]
            if period_type == 'instant': 
                period = period_tag.getchildren()[0].text
            elif period_type == 'duration': 
                period = [ p.text for p in period_tag.getchildren() ]
                period.sort()
                period = '%s %s' % tuple(period)
            print snake_title(tag.replace(':', '')), r.text, period, tag_schema.attrib
