#!/usr/bin/python
__version__ = ".02"
__author__ = "gazzman"
__copyright__ = "(C) gazzman GNU GPL 3."
__contributors__ = []

from datetime import datetime
from StringIO import StringIO
import csv
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
DATA_HEADERS = ['cik', 'period_end_date', 'submission_time', 'tag', 'value', 
                'start', 'end', 'segments']


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


def load_schema(namespace, submission, refresh=False):
    ''' Loads a schema into the submission dictionary   
    '''
    if namespace not in submission or refresh == True:
        schema_imports = submission['schema'].xpath("//None:import[@namespace='%s']" % namespace, 
                                                    namespaces=root_ns(submission['schema']))
        assert len(schema_imports) == 1
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
    try:
        assert len(tag_schemas) == 1
    except AssertionError:
        if len(tag_schemas) < 1: 
            print >> sys.stderr, '%s not found in schema' % tag
            return None
        else: raise Exception('multiple %s found in schema' % tag)
    return tag_schemas[0]


def load_submission(base_fname, submission_time=None):
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
    submission['time'] = submission_time
    return submission


def clean_instance_namespace(submission):    
    instance_namespace = submission['instance'].getroot().nsmap
    if None in instance_namespace:
        try:
            if instance_namespace[None] == instance_namespace['xbrli']: instance_namespace.pop(None)
        except KeyError:    
            instance_namespace.update(root_ns(submission['instance'], root_tag='xbrli'))
            instance_namespace.pop(None)
    return instance_namespace


def get_singleton_tag_value(submission, tag):
    try:
        v = submission['instance'].xpath('./%s' % tag, namespaces=submission['instance'].getroot().nsmap)
    except TypeError:
        inst_ns = clean_instance_namespace(submission)
        v = submission['instance'].xpath('./%s' % tag, namespaces=inst_ns)

    try:
        assert len(v) == 1
    except AssertionError:
        if len(v) > 1:
            raise LookupError('Submission has more than one %s' % tag)
        else:
            raise LookupError('Submission has no %s' % tag)
    return v[0].text


def listify_commented_file(fname, comment_symbol='#'):
    with open(fname, 'r') as f:
        lines = [ line.strip().split('#')[0] for line in f.read().split('\n') ]
        lines = [ line for line in lines if line != '' ]
    return lines


def extract_data(submission, data_requests):
    ''' Extracts data into a list of dicts
    '''
    rows = []
    cik = int(get_singleton_tag_value(submission, 'dei:EntityCentralIndexKey'))
    period_end_date = get_singleton_tag_value(submission, 'dei:DocumentPeriodEndDate')
    inst_ns = clean_instance_namespace(submission)
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
            if schema is not None:
                period_type = schema.attrib["{%s}periodType" % inst_ns['xbrli']]
                for r in submission['instance'].xpath('//%s' % tag, namespaces=inst_ns):
                    row = {'cik': cik, 'period_end_date': period_end_date, 
                           'submission_time': submission['time'], 'tag': tag, 
                           'value': r.text, 'segments': None}
                    context_ref = r.attrib['contextRef']
                    context = submission['instance'].xpath("//xbrli:context[@id='%s']" % context_ref, namespaces=inst_ns)
                    assert len(context) == 1
                    context = context[0]

                    entity = context.xpath("./xbrli:entity", namespaces=inst_ns)[0]
                    period = context.xpath("./xbrli:period", namespaces=inst_ns)[0]

                    if period_type == 'instant': 
                        row['start'] = period.xpath("./xbrli:instant", namespaces=inst_ns)[0].text
                        row['end'] = None
                    elif period_type == 'duration': 
                        row['start'] = period.xpath("./xbrli:startDate", namespaces=inst_ns)[0].text
                        row['end'] = period.xpath("./xbrli:endDate", namespaces=inst_ns)[0].text

#                    identifier = entity.xpath("./xbrli:identifier[@scheme]", namespaces=inst_ns)
#                    assert len(identifier) == 1
#                    identifier = identifier[0]

                    segments = entity.xpath('./xbrli:segment', namespaces=inst_ns)
                    for segment in segments:
                        for d in segment.iterdescendants():
                            if d.text is None: d.text = ''
                            descendant_info = ', '.join([str(d.attrib), d.text])
                            try:
                                row['segments'] = '; '.join([row['segments'], descendant_info])
                            except TypeError as err:
                                row['segments'] = descendant_info
                    rows += [row]
    return rows


def print_data(rows):
    ''' Print csv-formatted data to stdout
    '''
    s = StringIO()
    c = csv.DictWriter(s, DATA_HEADERS)
    c.writerows(rows)
    s.seek(0)
    print ','.join(DATA_HEADERS)
    print s.read()


def root_ns(parsed_etree, root_tag='None'):
    return {root_tag: re.match('{(.*)}', parsed_etree.getroot().tag).group(1)}


if __name__ == '__main__':
    ''' Very simple command line utility for printing XBRL instance data

    base_fname: The base filename of the XBRL submission retreived
                by the xbrl_retreiver.py utility.
    reporting_data_fname: The filename containing the tags you
                          want to display using the format
                              [NAMESPACE]:[TAG NAME]
                          If you omit the [TAG NAME], every 
                          element in the namespace that is in the
                          XBRL instance will be printed.   

    '''
    base_fname = sys.argv[1]
    reporting_data_fname = sys.argv[2]

    submission_time = base_fname.split('/')[-1].split('_')[0]
    submission = load_submission(base_fname, submission_time)
    data_requests = listify_commented_file(reporting_data_fname)
    rows = extract_data(submission, data_requests)
    print_data(rows)
