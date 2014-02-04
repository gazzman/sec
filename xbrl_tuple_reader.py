#!/usr/bin/python
__version__ = ".02"
__author__ = "gazzman"
__copyright__ = "(C) gazzman GNU GPL 3."
__contributors__ = []

from datetime import datetime
from collections import OrderedDict
from StringIO import StringIO
import csv
import pickle
import sys

from sec import xbrl_reader as xr

ROWKEY = ('CIK', 'Reporting Period End Date', 'Submission Time', 'Segments',
          'Submission Period Focus', 'Period Start', 'Period End')
DATEFMT = '%Y-%m-%d'


def add_data(rows, rowkey, header, data):
    try:
        rows[rowkey][header] = data
    except KeyError:
        rows[rowkey] = {header: data}


def durations_covered(submission):
    instance_namespace = xr.clean_instance_namespace(submission)
    periods = submission['instance'].xpath('//xbrli:period', namespaces=instance_namespace)
    durations = [ (period.xpath('./xbrli:startDate', namespaces=instance_namespace)[0].text,
                   period.xpath('./xbrli:endDate', namespaces=instance_namespace)[0].text)
                 for period in periods 
                 if len(period.xpath('./xbrli:startDate', namespaces=instance_namespace)) == 1 ]
    durations = list(set(durations))
    durations.sort()
    durations = [ (datetime.strptime(d[0], DATEFMT), 
                   datetime.strptime(d[1], DATEFMT)) for d in durations ]
    return durations


def extract_data(submission, header_tag_tuples):
    instance_namespace = xr.clean_instance_namespace(submission)
    cik = int(xr.get_singleton_tag_value(submission, 'dei:EntityCentralIndexKey'))
    period_end_date = xr.get_singleton_tag_value(submission, 'dei:DocumentPeriodEndDate')
    try:
        fiscal_year = xr.get_singleton_tag_value(submission, 'dei:DocumentFiscalYearFocus')
        fiscal_period = xr.get_singleton_tag_value(submission, 'dei:DocumentFiscalPeriodFocus')
        submission_period_focus = '%s%s' % (fiscal_year, fiscal_period)
    except LookupError:
        submission_period_focus = None
    durations = durations_covered(submission)

    rows = {}
    for header, tag in header_tag_tuples:
        namespace_key, name = tag.split(':')
        namespace = submission['instance'].getroot().nsmap[namespace_key]
        schema = xr.get_tag_schema('{%s}%s' % (namespace, name), submission)
        if schema is not None:
            period_type = schema.attrib["{%s}periodType" %instance_namespace['xbrli']]
            for e in submission['instance'].xpath('//%s' % tag, namespaces=instance_namespace):
                context_ref = e.attrib['contextRef']
                context = submission['instance'].xpath("//xbrli:context[@id='%s']" % context_ref, 
                                                       namespaces=instance_namespace)
                assert len(context) == 1
                context = context[0]

                period = context.xpath("./xbrli:period", namespaces=instance_namespace)[0]
                entity = context.xpath("./xbrli:entity", namespaces=instance_namespace)[0]

                segments = entity.xpath('./xbrli:segment', namespaces=instance_namespace)
                segment_info = None
                for segment in segments:
                    for d in segment.iterdescendants():
                        if d.text is None: d.text = ''
                        descendant_info = ', '.join([str(d.attrib), d.text])
                        try:
                            segment_info = '; '.join([segment_info, descendant_info])
                        except TypeError:
                            segment_info = descendant_info

                if period_type == 'instant': 
                    instant = period.xpath("./xbrli:instant", namespaces=instance_namespace)[0].text
                    instant = datetime.strptime(instant, DATEFMT)
                    def apply_period_boundaries(index, prefix):
                        ps = [ d for d in durations if abs(d[index] - instant).days <= 1 ]
                        rowkeys = [ tuple(zip(ROWKEY, 
                                          (cik, period_end_date, submission['time'], 
                                           segment_info, submission_period_focus,
                                           start.date().isoformat(), end.date().isoformat())))
                                    for start, end in ps ]
                        for rowkey in rowkeys:
                            add_data(rows, rowkey, '%s %s' % (prefix, header), e.text)
                    apply_period_boundaries(0, 'BoP')
                    apply_period_boundaries(1, 'EoP')
                elif period_type == 'duration': 
                    start = period.xpath("./xbrli:startDate", namespaces=instance_namespace)[0].text
                    end = period.xpath("./xbrli:endDate", namespaces=instance_namespace)[0].text
                    rowkey = tuple(zip(ROWKEY, (cik, period_end_date, submission['time'], segment_info, 
                                                submission_period_focus, start, end)))
                    add_data(rows, rowkey, header, e.text)
    return rows


def listify_data(rows, header_tag_tuples):
    data_headers = [ k for v in rows.values() for k in v ]
    data_headers = list(set(data_headers))
    data_headers.sort()
    headers = list(ROWKEY) + data_headers
    rowdicts = [ dict(list(k) + rows[k].items()) for k in rows ]
    return headers, rowdicts


def print_data(headers, rowdicts):
    ''' Print csv-formatted data to stdout
    '''
    s = StringIO()
    c = csv.DictWriter(s, headers)
    c.writerows(rowdicts)
    s.seek(0)
    print ','.join(headers)
    print s.read()


def period_aligned(rowdict):
    try:
        quarter = int(rowdict['Submission Period Focus'][-1])
        days = 90*quarter
    except ValueError:
        days = 365
    except TypeError:
        return False
    start = datetime.strptime(rowdict['Period Start'], '%Y-%m-%d')
    end = datetime.strptime(rowdict['Period End'], '%Y-%m-%d')
    period_delta = end - start
    return period_delta.days in range(days-5, days+6)

if __name__ == '__main__':
    ''' Very simple command line utility for printing XBRL instance data

    base_fname: The base filename of the XBRL submission retreived
                by the xbrl_retreiver.py utility.
    header_tag_tuples: The filename containing a pickled list of tuples
                       to display using the format
                        [(FIELDNAME1, NAMESPACE1:TAGNAME1), 
                         (FIELDNAME2, NAMESPACE2:TAGNAME2), ...
                        ]
    '''
    base_fname = sys.argv[1]
    header_tag_tuples_fname = sys.argv[2]

    header_tag_tuples = pickle.load(open(header_tag_tuples_fname, 'r'))
    submission_time = base_fname.split('/')[-1].split('_')[0]
    submission = xr.load_submission(base_fname, submission_time)
    rows = extract_data(submission, header_tag_tuples)
    headers, rowdicts = listify_data(rows, header_tag_tuples)
    rowdicts = [ rowdict for rowdict in rowdicts if not rowdict['Segments'] ]
    rowdicts = [ rowdict for rowdict in rowdicts if period_aligned(rowdict) ]
    rowdicts = [ rowdict for rowdict in rowdicts 
        if rowdict['Reporting Period End Date'] == rowdict['Period End']
        ]
    print_data(headers, rowdicts)
