#!/usr/bin/python

__version__ = ".01"
__author__ = "gazzman"
__copyright__ = "(C) gazzman GNU GPL 3."
__contributors__ = []

from collections import namedtuple
try: from collections import OrderedDict # >= 2.7
except ImportError: from ordereddict import OrderedDict # 2.6
import os
import pickle
import re
import sys
import time
import urllib2

from BeautifulSoup import BeautifulSoup
import feedparser

UASTRING=('Mozilla/5.0 (X11; Linux x86_64; rv:10.0.5) Gecko/20120606'
            + 'Firefox/10.0.5')
HEADER = {'User-Agent' : UASTRING}
SERVER = 'http://sec.gov'
DATEFORMAT = '%Y-%m-%dT%H:%M:%S'

Submission = namedtuple('Submission', ['date', 'title', 'sub_url', 'form'])

class CIKFinder:
    def __init__(self, filename='cikmap.pkl'):
        self.filename = filename
        try:
            self.cik_dict = pickle.load(open(self.filename, 'rb'))
        except IOError:
            msg = 'No pickled cik file found, generating new pickle file.'
            print >> sys.stdout, msg
            self.cik_dict = {}

    def get_cik(self, symbol):
        if symbol not in self.cik_dict:
            url = (SERVER + '/cgi-bin/browse-edgar?company=&match=&CIK=' + 
                   symbol + '&filenum=&State=&Country=&SIC=&owner=exclude&' + 
                   'Find=Find+Companies&action=getcompany')
            req = urllib2.Request(url, headers=HEADER)
            page = urllib2.urlopen(req)
            soup = BeautifulSoup(page)
            info = soup.find(attrs={'class': 'companyName'})
            try:
                info = info.getText().partition('CIK#:')[2]
            except AttributeError:
                self.cik_dict[symbol] = None
                pickle.dump(self.cik_dict, open(self.filename, 'wb'))
                raise Exception('No CIK found for %s' % symbol)
                
            self.cik_dict[symbol] = int(info.split(' ')[0])
            pickle.dump(self.cik_dict, open(self.filename, 'wb'))
        elif self.cik_dict[symbol] == None:
            raise Exception('No CIK found for %s' % symbol)
        return self.cik_dict[symbol]

class FilingURLs:
    """FilingURLs: Gets the filing URLs of SEC filings for a cik

    A FilingURLs is initialized with the entity's cik integer 
    and a list of strings denoting form names.

    """

    def __init__(self, cik):
        self.dirname = '%i/' % cik
        if not os.path.exists(self.dirname):
            os.makedirs(self.dirname)
        self.cik = cik
        self.sub_urlfile = '%i_submissions.pkl' % cik
        try:
            self.submissions = pickle.load(open(self.sub_urlfile, 'rb'))
        except IOError as err:
            if re.search('No such file', str(err)):
                message = ('No pickled submission url data.'
                           + ' Run \'pull_submission_urls\' to populate list.')
                print >> sys.stderr, message
                self.submissions = OrderedDict()
            else:
                raise err

    def feed_url(self, cik, start):
        return (SERVER 
                + '/cgi-bin/browse-edgar?action=getcompany&CIK=' 
                + str(cik) 
                + '&type=&dateb=&owner=exclude&start='
                + str(start) + '&count=100&output=atom')

    def match_form(self, sub_form):
        if len(self.forms) == 0:
            return True
        else:
            for form in self.forms:
                if re.match(form.lower(), sub_form.lower()):
                    return True
        return False

    def pull_submission_urls(self, refresh=False, verbose=False):
        """Parse the rss feed for the cik and store the urls,
           titles, and dates

        Keyword arguments:
        refresh -- will refresh from web even if data had been pickled
        verbose -- Print extra information

        """
        if len(self.submissions) == 0 or refresh:
            start = 0
            d = feedparser.parse(self.feed_url(self.cik, start))
            while len(d.entries) > 0:
                if verbose:
                    print self.feed_url(self.cik, start)
                start += 100
                for e in d.entries:
                    title = e.title.encode('UTF-8')
                    form = title.partition(' ')[0]
                    url = e.link
                    date = (time.strftime(DATEFORMAT, e['updated_parsed']) 
                            + '+00:00')
                    s = Submission(date, title, url, form)
                    if s not in self.submissions:
                        self.submissions[s] = None
                d = feedparser.parse(self.feed_url(self.cik, start))
            self.submissions = OrderedDict(sorted(self.submissions.items(), 
                                                  key=lambda d: d[0].date, 
                                                  reverse=True))
            pickle.dump(self.submissions, open(self.sub_urlfile, 'wb'))
        elif verbose:
            outmsg = ('Already pulled submission urls.'
                     + ' Pass \'refresh=True\' to refresh anew.')
            print >> sys.stderr, outmsg
        print >> sys.stderr, 'Submission URLs pulled.'

    def pull_xbrl_urls(self, refresh=False, verbose=False):
        """Grabs XBRL filing urls and pickles them

        Keyword arguments:
        refresh -- will refresh from web even if data had been pickled
        verbose -- Print extra information

        """
        self.pull_submission_urls(refresh, verbose)
        self.tens = [ s for s in self.submissions if '10-q' in s.title.lower() 
                                                  or '10-k' in s.title.lower() ]
        for ten in self.tens:
            if refresh is True or self.submissions[ten] is None:
                req = urllib2.Request(ten.sub_url, headers=HEADER)
                page = urllib2.urlopen(req)
                soup = BeautifulSoup(page)
                table = soup.find(name='table', attrs={'summary': 'Data Files'})
                try:
                    self.submissions[ten] = [ '%s%s' % (SERVER, a['href'])
                        for a in table.findAll(name='a')]
                    outmsg = '%s on %s xbrl url stored.' % (ten.title, ten.date)
                    print >> sys.stderr, outmsg
                except AttributeError:
                    self.submissions[ten] = []
                    outmsg = '%s on %s has no xbrl filings.' % (ten.title, ten.date)
                    print >> sys.stderr, outmsg
        pickle.dump(self.submissions, open(self.sub_urlfile, 'wb'))
        print >> sys.stderr, 'XBRL URLs pulled.'

    def save_xbrl_filings(self, refresh=False):
        """Grabs XBRL filings and stores them on disk

        Keyword arguments:
        refresh -- will refresh from web even if data had been pickled

        """
        for ten in self.tens:
            form = ten.title.split()[0]
            for url in self.submissions[ten]:
                fname = '%s_%s_%s' % (ten.date, form, url.split('/')[-1])
                fname = fname.replace('/', '_')
                if refresh == True or not os.path.exists('%s/%s' % (self.dirname, fname)):
                    outmsg = 'Grabbing %s' % fname
                    print >> sys.stderr, outmsg
                    req = urllib2.Request(url, headers=HEADER)
                    page = urllib2.urlopen(req)
                    with open('%s/%s' % (self.dirname, fname), 'w') as f:
                        f.write(page.read())
        print >> sys.stderr, 'XBRL filings pulled.'

if __name__ == '__main__':
    """First argument is the stock ticker
        
    """
    t = sys.argv[1]
    c = CIKFinder()
    cik = c.get_cik(t)
    f = FilingURLs(cik)
    f.pull_xbrl_urls()
    f.save_xbrl_filings()
