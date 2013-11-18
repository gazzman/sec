#!/usr/bin/python
from StringIO import StringIO
import csv
import pickle
import sys

from sec import xbrl_reader as xr

ROWKEY = ('CIK', 'Reporting Period End Date', 'Submission Time', 'Period Start', 'Period End', 'Segments')

def extract_data(submission, header_tag_tuples):
    instance_namespace = xr.clean_instance_namespace(submission)
    cik = int(xr.get_singleton_tag_value(submission, 'dei:EntityCentralIndexKey'))
    period_end_date = xr.get_singleton_tag_value(submission, 'dei:DocumentPeriodEndDate')

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

                if period_type == 'instant': 
                    start = period.xpath("./xbrli:instant", namespaces=instance_namespace)[0].text
                    end =  None
                elif period_type == 'duration': 
                    start = period.xpath("./xbrli:startDate", namespaces=instance_namespace)[0].text
                    end = period.xpath("./xbrli:endDate", namespaces=instance_namespace)[0].text

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
                rowkey = tuple(zip(ROWKEY, (cik, period_end_date, submission['time'], start, end, segment_info)))
                try:
                    rows[rowkey][header] = e.text
                except KeyError:
                    rows[rowkey] = {header: e.text}
    return rows


def print_data(rows, header_tag_tuples):
    ''' Print csv-formatted data to stdout
    '''
    s = StringIO()
    headers = list(ROWKEY) + [ htt[0] for htt in header_tag_tuples ]
    c = csv.DictWriter(s, headers)
    rowdicts = [ dict(list(k) + rows[k].items()) for k in rows ]
    c.writerows(rowdicts)
    s.seek(0)
    print ','.join(headers)
    print s.read()


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
    print_data(rows, header_tag_tuples)
