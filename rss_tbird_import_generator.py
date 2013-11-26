#!/usr/bin/python

__version__ = ".00"
__author__ = "gazzman"
__copyright__ = "(C) gazzman GNU GPL 3."
__contributors__ = []

import argparse
import lxml.etree as etree
import subprocess
import urllib2

from xbrl_retreiver import CIKFinder, UASTRING, HEADER

XMLURL = 'http://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=%i&output=atom'
HTMLURL = 'http://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=%i'
DEFAULTFNAME = 'rss_tbird_import.xml'

def gen_xmldoc():
    root = etree.XML("<opml version='1.0' xmlns:fz='urn:forumzilla:'></opml>")
    head = etree.SubElement(root, 'head')
    title = etree.SubElement(head, 'title')
    title.text = 'Thunderbird OPML Export - SEC Filings'
    datecreated = etree.SubElement(head, 'dateCreated')
    body = etree.SubElement(root, 'body')
    return root


if __name__ == '__main__':
    description = 'A utilty for quickly adding SEC RSS feeds to Thunderbird.'

    p = argparse.ArgumentParser(description=description)
    p.add_argument('symbol', help="Ticker symbol")
    p.add_argument('--filename', help="Existing XML File to add entry to")
    p.add_argument('--refresh', action="store_true", help="Refresh data")
    args = p.parse_args()

    c = CIKFinder()
    cik = c.get_cik(args.symbol, refresh=args.refresh)
    xmlurl = XMLURL % cik
    htmlurl = HTMLURL % cik
    req = urllib2.Request(xmlurl, headers=HEADER)
    page = urllib2.urlopen(req)
    tree = etree.parse(page)
    nsmap = tree.getroot().nsmap
    if None in nsmap: 
        nsmap.update({'xmlns': nsmap[None]})
        nsmap.pop(None)
    title = tree.xpath('./xmlns:title', namespaces=nsmap)[0].text.title()

    try:
        xmldoc = etree.parse(args.filename)
    except TypeError:
        xmldoc = gen_xmldoc()
        args.filename = DEFAULTFNAME
    datecreated = xmldoc.xpath('./head/dateCreated')[0]
    date = subprocess.Popen('date', stdout=subprocess.PIPE)
    datecreated.text = date.stdout.read().strip()
    body = xmldoc.xpath('./body')[0]
    if len(body.xpath('./outline[@title="%s"]' % title)) == 0:
        outline = etree.SubElement(body, 'outline', {'title': title})
        soutline_attribs = {'type': 'rss', 
                            'title': title, 
                            'text': title, 
                            'version': 'RSS',
                            '{%s}quickMode' % body.nsmap['fz']: 'false',
                            'xmlUrl': xmlurl,
                            'htmlUrl': htmlurl
                           }
        soutline = etree.SubElement(outline, 'outline', soutline_attribs)
        with open(args.filename, 'w') as xmlfile:
            xmlfile.write(etree.tostring(xmldoc, pretty_print=True))
