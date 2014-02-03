#!/usr/bin/python
__version__ = ".01"
__author__ = "gazzman"
__copyright__ = "(C) gazzman GNU GPL 3."
__contributors__ = []

import os
import pickle
import sys

from sec import xbrl_reader as xr

SKIP = 'or press \'s\' to skip'
ENTERLABEL = 'Please enter the label for %s'
LABELNOTFOUND = 'Label \'%s\' not found.'

def label_tags(submission, label):
    ids = [ e.attrib['id'] for e in submission['lab'].iter() if label_match(e.text, label) ]
    return [ ':'.join(id.split('_')[1:3]) for id in ids ] 

def label_match(text, label):
    if not text: return False
    return text.lower() == label.lower()

if __name__ == '__main__':
    ''' 
    Very simple command line utility for producing a pickle of
    a list of tuples for feeding into the xbrl_tuple_reader.py

    base_fname: The base filename of the XBRL submission retreived
                by the xbrl_retreiver.py utility.
    fields_fname: The filename of the fieldnames from which to 
                  isolate data from, one per line.
    '''
    base_fname = sys.argv[1]
    fields_fname = sys.argv[2]
    ofext = os.path.split(fields_fname)[-1]
    if len(sys.argv) == 4: ofname = '%s.%s' % (sys.argv[3], ofext)
    else: ofname = '%s.%s' % (base_fname, ofext)

    submission_time = base_fname.split('/')[-1].split('_')[0]
    submission = xr.load_submission(base_fname, submission_time)
    fields = xr.listify_commented_file(fields_fname)
    header_tags = {}
    for field in fields:
        # associate label with field
        tags = []
        while len(tags) == 0:
            pout = '%s %s: ' % (ENTERLABEL % field, SKIP)
            label = raw_input(pout)
            if label.lower() == 's': break
            tags = label_tags(submission, label)
            if len(tags) == 0: print LABELNOTFOUND % label

        # associate tag with label
        if len(tags) == 1:
            header_tags[field] = tags[0]
        elif len(tags) > 1:
            output = 'The following tag IDs have been found:\n\n'
            choices = [ str(i) for i in range(len(tags)) ]
            choice_tuples = zip(choices, tags)
            output += '\n'.join([ '\t(%s) %s' % choice_tuple for choice_tuple in choice_tuples ])
            output = '%s\n\nPlease choose.\nValid choices are %s: ' % (output, ', '.join(choices))
            verify = 'n'
            while verify == 'n':
                choice = raw_input(output).strip()
                while choice not in choices:
                    choice = raw_input(output).strip()
                tag = tags[int(choice)]
                you_chose = 'You chose \'%s\' as the tag for \'%s\'' % (tag, field)
                verify = raw_input('%s\nIs this correct? ' % you_chose).strip().lower()
                while verify not in ['y', 'n']:
                    verify = raw_input('%s\nIs this correct? ' % you_chose).strip().lower()
            header_tags[field] = tag

    # pickle fieldnames for xbrl_tuple_reader.py
    pickle.dump(header_tags.items(), open(ofname, 'w'))
