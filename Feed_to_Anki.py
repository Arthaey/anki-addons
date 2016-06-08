# -*- coding: utf-8 -*-
# Feed to Anki: an Anki addon makes a RSS (or Atom) Feed into Anki cards.
# Version: 0.3.1
# GitHub: https://github.com/luminousspice/anki-addons/
#
# Copyright: 2016 Luminous Spice <luminous.spice@gmail.com>
# License: GNU AGPL, version 3 or later; http://www.gnu.org/copyleft/agpl.html
#
# Third party software used with Feed to Anki.
# Httplib2. Copyright (c) 2006 by Joe Gregorio. Released under the MIT License.
# https://github.com/httplib2/httplib2/blob/master/LICENSE

##### Feeds info (URL, deck, tags) #####
Feeds = [
    {"URL": "http://www.merriam-webster.com/wotd/feed/rss2",
     "DECK": u"Word of the Day::Merriam-Webster",
     "tags": [u"wotd",u"MW"]},
    {"URL": "http://feeds.feedburner.com/OAAD-WordOfTheDay?format=xml",
     "DECK": u"Word of the Day::Oxford",
     "tags": [u"wotd",u"OAAD"]},
]
########################################

import ssl
from functools import wraps
import feed_to_anki.httplib2 as httplib2

from aqt import mw, utils
from aqt.qt import *
from anki.lang import ngettext
from BeautifulSoup import BeautifulStoneSoup

MODEL = u"Feed_to_Anki"
fields = [u"Front", u"Back"]


def sslwrap(func):
    @wraps(func)
    def bar(*args, **kw):
        kw['ssl_version'] = ssl.PROTOCOL_TLSv1
        return func(*args, **kw)
    return bar

ssl.wrap_socket = sslwrap(ssl.wrap_socket)


def addFeedModel(col):
    # add the model for feeds
    mm = col.models
    m = mm.new(MODEL)
    for f in fields:
        fm = mm.newField(f)
        mm.addField(m, fm)
    t = mm.newTemplate(u"Card 1")
    t['qfmt'] = "{{"+fields[0]+"}}"
    t['afmt'] = "{{FrontSide}}\n\n<hr id=answer>\n\n"+"{{"+fields[1]+"}}"
    mm.addTemplate(m, t)
    mm.add(m)
    return m


# iterate decks
def buildCards():
    msg = ""
    for i in range(len(Feeds)):
        msg += Feeds[i]["DECK"] + ":\n"
        msg += buildCard(**Feeds[i]) + "\n"
    utils.showText(msg)


def buildCard(**kw):
    # get deck and model
    deck  = mw.col.decks.get(mw.col.decks.id(kw['DECK']))
    model = mw.col.models.byName(MODEL)
    # if MODEL doesn't exist, create a MODEL
    if model is None:
        model = addFeedModel(mw.col)
        model['name'] = MODEL
    else:
        act_name = set([f['name'] for f in model['flds']])
        std_name = set(fields)
        if not len(act_name & std_name) == 2:
            model['name'] = MODEL + "-" + model['id']
            model = addFeedModel(mw.col)
            model['name'] = MODEL

    # assign model to deck
    mw.col.decks.select(deck['id'])
    mw.col.decks.get(deck)['mid'] = model['id']
    mw.col.decks.save(deck)

    # assign deck to model
    mw.col.models.setCurrent(model)
    mw.col.models.current()['did'] = deck['id']
    mw.col.models.save(model)

    # retrieve rss
    mw.progress.start(immediate=True)
    try:
        h = httplib2.Http(".cache")
        (resp, data) = h.request(kw['URL'], "GET")
    except httplib2.ServerNotFoundError, e:
        errmsg = u"Failed to reach the feed server." + str(e) + "\n"
        utils.tooltip(errmsg)
        return errmsg
    except httplib2.HttpLib2Error, e:
        errmsg = u"The feed server couldn\'t fulfill the request." + str(e) + "\n"
        utils.tooltip(errmsg)
        return errmsg
    else:
        if not str(resp.status) in ("200","304"):
            errmsg = "The feed server couldn\'t return the file." + u" Code: " + str(resp.status) + "\n"
            utils.tooltip(errmsg)
            return errmsg
    finally:
        mw.progress.finish()

    #parse xml
    doc = BeautifulStoneSoup(data, selfClosingTags=['link'], convertEntities=BeautifulStoneSoup.XHTML_ENTITIES)

    if not doc.find('item') is None:
        items = doc.findAll('item')
        feed = "rss"
    elif not doc.find('entry') is None:
        items = doc.findAll('entry')
        feed = "atom"
    else:
        return

    # iterate notes
    dups = 0
    adds = 0
    log = ""
    for item in items:
        note = mw.col.newNote()
        note[fields[0]] = item.title.text
        nounique = note.dupeOrEmpty()
        if nounique:
            if nounique == 2:
                log += "%s \n" % note[_("Front")]
            continue
        if feed == "rss":
            if not item.description is None:
                note[fields[1]] = item.description.text
        if feed == "atom":
            if not item.content is None:
                note[fields[1]] = item.content.text
            elif not item.summary is None:
                note[fields[1]] = item.summary.text
        note.tags = filter(None, kw['tags'])
        mw.col.addNote(note)
        adds += 1

    mw.col.reset()
    mw.reset()

    # show result
    msg = ngettext("%d note added", "%d notes added", adds) % adds
    msg += "\n"
    if len(log) > 0:
        msg += _("duplicate") + ":\n"
        msg += log
    return msg

# create a new menu item
action = QAction("Feed to Anki", mw)
mw.connect(action, SIGNAL("triggered()"), buildCards)
mw.form.menuTools.addAction(action)
