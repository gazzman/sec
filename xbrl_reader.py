#!/usr/bin/python

__version__ = ".01"
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

def snake_title(string):
    string = string.replace(' ', '')
    return re.sub('(?!^)(A|[A-Z]+)', r'_\1', string).lower() # thanks nickl-

def get_schema(uri, refresh=False):
    ''' Gets and parses a schema file from disk or web
    '''
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

def load_schema(namespace, submission):
    ''' Loads a schema into the submission dictionary   
    '''
    schema_imports = submission['schema'].xpath("//None:import[@namespace='%s']" % namespace, 
                                                namespaces=root_ns(submission['schema']))
    assert len(schema_imports) == 1
    if namespace not in submission:
        schema_url = schema_imports[0].attrib['schemaLocation']
        submission[namespace] = get_schema(schema_url)

def get_tag_schema(tag, submission):
    ''' Returns the schema element for the tag in question
    '''
    m = re.match('{(.*)}(.*)', tag)
    if not m: raise Exception('Tag does not match pattern.')
    namespace = m.group(1)
    name = m.group(2)

    try: # tag schema in an imported schema
        load_schema(namespace, submission)
        tag_schemas = submission[namespace].xpath("//None:element[@name='%s']" % name, 
                                                  namespaces=root_ns(submission['schema']))
    except AssertionError: # tag schema not imported
        tag_schemas = submission['schema'].xpath("//None:element[@name='%s']" % name, 
                                                 namespaces=root_ns(submission['schema']))
    assert len(tag_schemas) == 1
    return tag_schemas[0]

def root_ns(parsed_etree, root_tag='None'):
    return {root_tag: re.match('{(.*)}', parsed_etree.getroot().tag).group(1)}

if __name__ == '__main__':
    ''' Very simple command line utility for printing XBRL instance data

    base_fname: The base filename of the XBRL submission
    reporting_data_fname: The filename containing the tags you
                          want to display using the format
                              [NAMESPACE]:[TAG NAME]
                          If you omit the [TAG NAME], every 
                          element in the namespace that is in the
                          XBRL instance will be printed.   

    '''
    base_fname = sys.argv[1]
    reporting_data_fname = sys.argv[2]
    submission = {}
    for ftype in FTYPES:
        try:
            if ftype == 'schema':
                submission[ftype] = etree.parse('%s.xsd' % base_fname)
            elif ftype == 'instance':
                submission[ftype] = etree.parse('%s.xml' % base_fname)
            else:
                submission[ftype] = etree.parse('%s_%s.xml' % (base_fname, ftype))
        except IOError as err:
                print >> sys.stderr, '%s s missing' % ftype.upper()
    inst_ns = submission['instance'].getroot().nsmap
    if None in inst_ns:
        try:
            if inst_ns[None] == inst_ns['xbrli']: inst_ns.pop(None)
        except KeyError:    
            inst_ns.update(root_ns(submission['instance'], root_tag='xbrli'))
            inst_ns.pop(None)
    cik = submission['instance'].xpath('./dei:EntityCentralIndexKey', namespaces=inst_ns)
    assert len(cik) == 1
    cik = cik[0].text

    with open(reporting_data_fname, 'r') as f:
        data_requests = [ line.strip().split('#')[0] for line in f.read().split('\n') ]
        data_requests = [ data_request for data_request in data_requests if data_request != '' ]
        
    for data_request in data_requests:
        namespace_key, name = data_request.split(':')
        namespace = submission['instance'].getroot().nsmap[namespace_key]
        if name.strip() == '':
            try:
                load_schema(namespace, submission)
                names = [ e.attrib['name'] for e in submission[namespace].xpath('//None:element',
                                                                               namespaces=root_ns(submission[namespace])) ]
            except AssertionError:
                names = [ e.attrib['name'] for e in submission['schema'].xpath('//None:element',
                                                                               namespaces=root_ns(submission['schema'])) ]
        else: names = [name]

        for name in names:
            tag = '%s:%s' % (namespace_key, name)
            schema = get_tag_schema('{%s}%s' % (namespace, name), submission)
            period_type = schema.attrib["{%s}periodType" % inst_ns['xbrli']]
            for r in submission['instance'].xpath('//%s' % tag, namespaces=inst_ns):
                context_ref = r.attrib['contextRef']
                context = submission['instance'].xpath("//xbrli:context[@id='%s']" % context_ref, namespaces=inst_ns)
                assert len(context) == 1
                context = context[0]

                entity = context.xpath("./xbrli:entity", namespaces=inst_ns)[0]
                period = context.xpath("./xbrli:period", namespaces=inst_ns)[0]

                if period_type == 'instant': 
                    period = (period.getchildren()[0].text, )
                elif period_type == 'duration': 
                    period = (period.xpath("./xbrli:startDate", namespaces=inst_ns)[0].text, 
                              period.xpath("./xbrli:endDate", namespaces=inst_ns)[0].text)


                identifier = entity.xpath("./xbrli:identifier[@scheme]", namespaces=inst_ns)
                assert len(identifier) == 1
                identifier = identifier[0]
                segments = entity.xpath('./xbrli:segment', namespaces=inst_ns)
                segment_info = ''
                for segment in segments:
                    for d in segment.iterdescendants():
                        if d.text is None: d.text = ''
                        segment_info = ', '.join([str(d.attrib), d.text])
                if r.text is None: r.text = ''
                print ', '.join([cik, tag, r.text] + list(period) + [segment_info])
