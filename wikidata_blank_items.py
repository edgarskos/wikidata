#!/usr/bin/env python
"""
Copyright (C) 2013 Legoktm

Licensed as CC-Zero. See https://creativecommons.org/publicdomain/zero/1.0 for more details.
"""
import sys
import os
import oursql
import pywikibot
from wikidata_null_edit import null_edit
site = pywikibot.Site()
repo = site.data_repository()
wikidata = pywikibot.Site('wikidata','wikidata')
query = """
/* SLOW_OK */
SELECT
 page_title
FROM page
WHERE page_namespace=0
AND NOT EXISTS (SELECT * FROM wb_items_per_site WHERE ips_item_id=REPLACE(page_title, "Q","") LIMIT 1)
LIMIT 2000;
"""



def report_dupe(first, second,exact=True,dontdelete=False):
    global REPORT
    global DUPES
    global EMPTY
    if dontdelete:
        REPORT += '\n*[[{0}]] vs [[{1}]] - need to be merged by hand.'.format(first, second)
        return
    first=first.upper()
    if second:
        second=second.upper()
    if first in REPORT:
        print 'Already logged this, skipping.'
        return
    if second:
        if exact:
            reason = 'Exact dupe of [[{0}]]'.format(second)
        else:
            reason = 'Duplicate of [[{0}]]'.format(second)
        DUPES += second + '\n'
    else:
        #empty item
        EMPTY.append(first)
        return
        #reason = 'Item is empty'
    REPORT += '\n' + '*[[{0}]] - {{{{rfd links|{0}|{1}}}}} - {1}'.format(first, reason)


def getSite(sitething):
    lang = sitething.replace('wiki','').replace('_','-') #Haaaaaack
    return pywikibot.Site(lang, 'wikipedia')


def complex_diff(qid1, qid2, sitelinks1, sitelinks2):
    #establish a master item
    if len(sitelinks1) == len(sitelinks2):
        return
        #neither is a master, do it manually
    elif len(sitelinks1) > len(sitelinks2):
        qid = qid1
        sitelinks = sitelinks1
        other = qid2
        other_sl = sitelinks2
    else:
        qid = qid2
        sitelinks = sitelinks2
        other = qid1
        other_sl = sitelinks1
    print qid
    #print sitelinks
    #print other_sl
    errors = False
    for lang in other_sl:
        if lang in sitelinks:
            print 'in'
            if other_sl[lang] != sitelinks[lang]:
                #hmmm lets check if one is a redirect?
                other_page = pywikibot.Page(getSite(lang), other_sl[lang])
                the_page = pywikibot.Page(getSite(lang), sitelinks[lang])
                if other_page.isRedirectPage():
                    #find the target
                    target = other_page.getRedirectTarget()
                    if target != the_page:
                        errors = True
                        break
                elif the_page.isRedirectPage():
                    target = the_page.getRedirectTarget()
                    if target != other_page:
                        errors = True
                        break
                else:
                    errors = True
                    break
        else:
            print 'missing '+lang
            errors = True
            break
    if not errors:
        return qid, other
    return


def check_blist(qid):
    item = pywikibot.ItemPage(repo, qid)
    try:
        item.get()
    except KeyError:
        return False  # grrr
    if 'p31' in item.claims:
        for c in item.claims['p31']:
            if c.getTarget().getID() == 'q2065736':
                return False
    return True


def check_item(qid,null=False):
    print 'Checking {0}'.format(qid)
    qid = qid.lower()
    id = int(qid.replace('q',''))
    if id == 4115189: #wikidata sandbox
        print 'Oops. Lets not delete the sandbox.'
        return
    if not check_blist(qid):
        return  # meets an exemption thingy
    try:
        sitelinks = repo.get_sitelinks(qid)
    except AssertionError,e:
        if 'lacks sitelinks key' in str(e):
            print 'ITEM IS EMPTY'
            report_dupe(qid, None)
        return
    if len(sitelinks) != 1:
        print 'More than one sitelink...'
    link = sitelinks.items()[0][1]
    #get the other item
    print link
    qid2 = repo.get_id(link['site'], link['title'])
    if str(qid2) == '-1' and not null:
        try:
            null_edit(qid)
        except pywikibot.data.api.APIError, e:
            print '!!!!ALARM!!!!'
            #print unicode(e)
            return
        check_item(qid,null=True)
        return
    elif str(qid2) == '-1':
        return
    if qid2 != qid.lower():
        print 'Checking {0} vs {1}'.format(qid, qid2)
    else:
        print "It's the same. Skipping"
        return
    sitelinks2 = repo.get_sitelinks(qid2)
    if sitelinks == sitelinks2:
        print 'OMG EXACT DUPE'
        report_dupe(qid, qid2)
        return
    #lets through it in the complex diff machine
    results = complex_diff(qid, qid2, sitelinks, sitelinks2)
    if results:
        print '{0} is a complex dupe of {1}'.format(results[1], results[0])
        report_dupe(results[1], results[0], exact=False)
        return
    #at this point we probably have a dupe, but not safe enough to delete. lets just report it.
    report_dupe(qid, qid2, dontdelete=True)


REPORT = '{{/Header}}\n'
DUPES = ''
EMPTY = []

def rfd():
    reason = 'Empty item detected by bot'
    global EMPTY
    print 'Thought empty: '+str(len(EMPTY))
    for item in EMPTY[:]:
        i = pywikibot.Page(wikidata, item)
        refs = list(i.getReferences(namespaces=[0]))
        if refs:
            EMPTY.remove(item)
    rfd_page = pywikibot.Page(wikidata, 'Wikidata:Requests for deletions')
    old = rfd_page.get()
    for item in EMPTY[:]:
        if item in old:
            EMPTY.remove(item)
    if not EMPTY: #sbm
        return
    print 'Actually empty: '+str(len(EMPTY))
    #report empty items straight to rfd
    if len(EMPTY) == 1:
        text = "{{{{subst:Request for deletion| itemid ={0}| reason ={1}}}}}".format(EMPTY[0], reason)
    else:
        #{{subst:Rfd group |  |  |  |  |  | reason =  }}
        text = '==Bulk deletion request: Empty items=='
        text += '\n{{subst:Rfd group|' + '|'.join(EMPTY) + '|reason={0}|comment=Empty items detected by bot.}}}}'.format(reason)

    new = old + '\n\n' + text
    rfd_page.put(new, 'Bot: Adding list of empty items for deletion.')


def main():


    db = oursql.connect(db='wikidatawiki_p',
        host="wikidatawiki-p.rrdb.toolserver.org",
        read_default_file=os.path.expanduser("~/.my.cnf"),
        charset=None,
        use_unicode=False
    )


    pywikibot.handleArgs()

    cur = db.cursor()
    cur.execute(query)
    data=cur.fetchall()
    TOTAL = len(data)
    for row in data:
        try:
            check_item(row[0])
        except:
            pass
    global REPORT
    global DUPES
    rfd() #before dupes
    pg = pywikibot.Page(wikidata, 'User:Legobot/Dupes')
    pg.put(REPORT, 'Bot: Updating list of dupes')
    #save dupes locally for null edits
    fname = 'wd_null.txt'
    if os.path.exists(fname):
        with open(fname, 'r') as f:
            old = f.read()
    else:
        old = ''
    new = old + DUPES
    with open(fname, 'w') as f:
        f.write(new)
    print 'Saved dupe file'
    print 'TOTAL: {0}. DUPES: {1}.'

if __name__ == "__main__":
    if '--test' in sys.argv:
        check_item('Q743645')
    else:
        main()