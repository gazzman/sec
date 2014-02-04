sec
===

Utilities for working with EDGAR filings

Example: Extracting Data from an XOM 10-Q
-----------------------------------------

1. The first step is to run xbrl_retreiver.py. This will collect
all of the 10-Q and 10-K filings for a particular ticker, eg.

    $ xbrl_retreiver.py XOM


2. Next, create a file of fields you would like to extract from the 
XBRL filings, eg.

    $ echo Assets > fields
    $ echo Liabilities >> fields

3. Then run the xbrl_tuple_generator.py, eg.

    $ xbrl_tuple_generator.py 2013-11-05T17:08:04+00:00_10-Q_xom-20130930 fields xom
    Please enter the label for Assets or press 's' to skip: total assets
    The following tag IDs have been found:

    	(0) us-gaap:Assets
    	(1) us-gaap:Assets
    	(2) us-gaap:Assets

    Please choose.
    Valid choices are 0, 1, 2: 0
    You chose 'us-gaap:Assets' as the tag for 'Assets'
    Is this correct? y
    Please enter the label for Liabilities or press 's' to skip: total liabilities
    The following tag IDs have been found:

    	(0) us-gaap:Liabilities
    	(1) us-gaap:Liabilities
    	(2) us-gaap:Liabilities

    Please choose.
    Valid choices are 0, 1, 2: 0
    You chose 'us-gaap:Liabilities' as the tag for 'Liabilities'
    Is this correct? y

This will result in a pickled list of tuples stored in `xom_fields`. The 
tuples associate the fields you specified to an XML tag in the XBRL data file.

4. From here, run xbrl_tuple_reader.py to extract and print the fields of 
interest to STDOUT, eg.

    $ xbrl_tuple_reader.py 2013-11-05T17:08:04+00:00_10-Q_xom-20130930 xom_fields
    CIK,Reporting Period End Date,Submission Time,Segments,Submission Period Focus,Period Start,Period End,BoP Assets,BoP Liabilities,EoP Assets,EoP Liabilities
    34088,2013-09-30,2013-11-05T17:08:04+00:00,,2013Q3,2013-01-01,2013-09-30,333795000000,162135000000,347564000000,172086000000

5. You can use your favorite shell-scripting language to extract data from 
multiple filings, eg.
`
    $ echo extractor.bash
    #!/bin/bash
    PTUPLE=$1
    echo "" > csvs
    for base in `ls | grep xsd | awk -F . '{print $1}'`
    do
    	xbrl_tuple_reader.py $base $PTUPLE > $base.$PTUPLE.csv
    	echo $base.$PTUPLE.csv >> csvs
    done
    merge_csvs csvs -s $PTUPLE.csv
    for f in `cat csvs`
    do
    	rm $f
    done
    rm csvs
`
(merge_csvs can be found in the http://github.com/gazzman/data_cleaning repo) 

Then run

    $ extractor.bash xom_fields

to generate a file called `xom_fields.csv` that looks like this:
    
    $ cat xom_fields.csv
    CIK,Reporting Period End Date,Submission Time,Segments,Submission Period Focus,Period Start,Period End,BoP Assets,BoP Liabilities,EoP Assets,EoP Liabilities
    34088,2010-03-31,2010-05-06T17:53:44+00:00,,2010Q1,2010-01-01,2010-03-31,233323000000,117931000000,242748000000,125082000000
    34088,2010-06-30,2010-08-04T19:04:53+00:00,,2010Q2,2010-01-01,2010-06-30,233323000000,117931000000,291068000000,145701000000
    34088,2010-09-30,2010-11-03T19:42:58+00:00,,2010Q3,2010-01-01,2010-09-30,233323000000,117931000000,299994000000,149394000000
    34088,2010-12-31,2011-02-25T21:07:35+00:00,,2010FY,2010-01-01,2010-12-31,233323000000,117931000000,302510000000,149831000000
    34088,2010-12-31,2011-02-28T22:01:32+00:00,,2010FY,2010-01-01,2010-12-31,233323000000,117931000000,302510000000,149831000000
    34088,2011-03-31,2011-05-05T16:53:46+00:00,,2011Q1,2011-01-01,2011-03-31,302510000000,149831000000,319533000000,162002000000
    34088,2011-06-30,2011-08-04T16:19:05+00:00,,2011Q2,2011-01-01,2011-06-30,302510000000,149831000000,326204000000,164369000000
    34088,2011-09-30,2011-11-03T15:41:58+00:00,,2011Q3,2011-01-01,2011-09-30,302510000000,149831000000,323227000000,161015000000
    34088,2011-12-31,2012-02-24T21:08:32+00:00,,2011FY,2011-01-01,2011-12-31,302510000000,149831000000,331052000000,170308000000
    34088,2012-03-31,2012-05-03T18:56:03+00:00,,2012Q1,2012-01-01,2012-03-31,331052000000,170308000000,345152000000,181035000000
    34088,2012-06-30,2012-08-02T17:10:52+00:00,,2012Q2,2012-01-01,2012-06-30,331052000000,170308000000,329645000000,161660000000
    34088,2012-09-30,2012-11-06T17:14:21+00:00,,2012Q3,2012-01-01,2012-09-30,331052000000,170308000000,335191000000,162836000000
    34088,2012-12-31,2013-02-27T21:05:06+00:00,,2012FY,2012-01-01,2012-12-31,331052000000,170308000000,333795000000,162135000000
    34088,2013-03-31,2013-05-02T15:50:47+00:00,,2013Q1,2013-01-01,2013-03-31,333795000000,162135000000,339639000000,166562000000
    34088,2013-06-30,2013-08-06T15:54:46+00:00,,2013Q2,2013-01-01,2013-06-30,333795000000,162135000000,341615000000,170027000000
    34088,2013-09-30,2013-11-05T17:08:04+00:00,,2013Q3,2013-01-01,2013-09-30,333795000000,162135000000,347564000000,172086000000

The result is a nicely formatted csv ready for importing into your 
favorite analysis application.
