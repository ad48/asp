"""Manage the routes and associated fns for asp app"""

from app import app, sadb, lm
from app.models import User, Library, Publication
from app.utils import safe_pickle_dump, strip_version, isvalidid


import os
import json
import time
import pickle
import argparse
import dateutil.parser
from random import shuffle, randrange, uniform

import numpy as np
from sqlite3 import dbapi2 as sqlite3
from hashlib import md5
from flask import Flask, request, session, url_for, redirect, \
     render_template, abort, g, flash, _app_ctx_stack
from flask_limiter import Limiter
from werkzeug import check_password_hash, generate_password_hash
import pymongo

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user,\
    current_user
from .oauth import OAuthSignIn
# from bs4 import BeautifulSoup as bsoup

import ssl
from flask_sslify import SSLify


print('loading serve cache...', app.config['SERVE_CACHE_PATH'])
cache = pickle.load(open(app.config['SERVE_CACHE_PATH'], "rb"))
DATE_SORTED_PIDS = cache['date_sorted_pids']
TOP_SORTED_PIDS = cache['top_sorted_pids']
SEARCH_DICT = cache['search_dict']


print('loading the paper database', app.config['DB_PATH'])
db = pickle.load(open(app.config['DB_PATH'], 'rb'))
print('loading the paper database', app.config['DB_SERVE_PATH'])
db2 = pickle.load(open(app.config['DB_SERVE_PATH'], 'rb'))


lm.login_view = 'index'


print('loading tfidf_meta', app.config['META_PATH'])
meta = pickle.load(open(app.config['META_PATH'], "rb"))
vocab = meta['vocab']
idf = meta['idf']

print('loading paper similarities', app.config['SIM_PATH'])
sim_dict = pickle.load(open(app.config['SIM_PATH'], "rb"))

print('loading user recommendations', app.config['USER_SIM_PATH'])
user_sim = {}
if os.path.isfile(app.config['USER_SIM_PATH']):
    user_sim = pickle.load(open(app.config['USER_SIM_PATH'], 'rb'))

print('loading user recommendations2', app.config['USER_SIM2_PATH'])
user_sim2 = {}
if os.path.isfile(app.config['USER_SIM2_PATH']):
    user_sim2 = pickle.load(open(app.config['USER_SIM2_PATH'], 'rb'))

# print('loading serve cache...', app.config['serve_cache_path)
# cache = pickle.load(open(app.config['serve_cache_path, "rb"))
# DATE_SORTED_PIDS = cache['date_sorted_pids']
# TOP_SORTED_PIDS = cache['top_sorted_pids']
# SEARCH_DICT = cache['search_dict']

print('connecting to mongodb...')
client = pymongo.MongoClient()
mdb = client.arxiv
tweets_top1 = mdb.tweets_top1
tweets_top7 = mdb.tweets_top7
tweets_top30 = mdb.tweets_top30
comments = mdb.comments
tags_collection = mdb.tags
goaway_collection = mdb.goaway
follow_collection = mdb.follow
print('mongodb tweets_top1 collection size:', tweets_top1.count())
print('mongodb tweets_top7 collection size:', tweets_top7.count())
print('mongodb tweets_top30 collection size:', tweets_top30.count())
print('mongodb comments collection size:', comments.count())
print('mongodb tags collection size:', tags_collection.count())
print('mongodb goaway collection size:', goaway_collection.count())
print('mongodb follow collection size:', follow_collection.count())

TAGS = ['insightful!', 'thank you', 'agree', 'disagree',
        'not constructive', 'troll', 'spam']



# args = app.config['ARGS']
# TODO - supposed to import CLI args from serve.py.  Doesn't work.

# --------------------------------------------
# Adam's fns
# ----------------------------------------------
@app.before_request
def https_redirect():
    try:
        redirect('https://' + self.request.host, permanent=False)
    except:
        pass

@app.before_request
def force_https():
    if request.endpoint in app.view_functions and not request.is_secure:
        return redirect(request.url.replace('http://', 'https://'))


# -----------------------------------------------------------------------------
# connection handlers
# -----------------------------------------------------------------------------

@app.before_request
def before_request():
    # this will always request database connection, even if we dont end up using it ;\
    g.db2 = connect_db()
    # retrieve user object from the database if user_id is set
    g.user = None
    if 'user_id' in session:
        g.user = query_db('select * from user where id = ?',
                          [session['user_id']], one=True)


@app.teardown_request
def teardown_request(exception):
    db2 = getattr(g, 'db2', None)
    if db2 is not None:
        db2.close()

@lm.user_loader
def load_user(id):
    """Load user from database using their user id."""
    return User.query.get(int(id))


# -----------------------------------------------------------------------------
# utilities for database interactions
# -----------------------------------------------------------------------------
# to initialize the database: sqlite3 as.db < schema.sql
def connect_db():
    sqlite_db = sqlite3.connect(app.config['DATABASE_PATH'])
    sqlite_db.row_factory = sqlite3.Row  # to return dicts rather than tuples
    return sqlite_db

def query_db(query, args=(), one=False):
    """Queries the database and returns a list of dictionaries."""
    cur = g.db2.execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def get_user_id(username):
    """Convenience method to look up the id for a username."""
    rv = query_db('select id from user where orcid_name = ?',
                      [username], one=True)
    return rv[0] if rv else None

def get_username(user_id):
    """Convenience method to look up the username for a user."""
    rv = query_db('select orcid_name from user where id = ?',
                [user_id], one=True)
    return rv[0] if rv else None

# -----------------------------------------------------------------------------
# search/sort functionality
# -----------------------------------------------------------------------------

def papers_search(qraw):
    qparts = qraw.lower().strip().split() # split by spaces
    # use reverse index and accumulate scores
    scores = []
    for pid,p in db.items():
        score = sum(SEARCH_DICT[pid].get(q,0) for q in qparts)
        if score == 0:
            continue # no match whatsoever, dont include
        # give a small boost to more recent papers
        # TODO - added this try/ex because tscore is not defined for some entries. Not sure why...
        try:
            score += 0.0001*p['tscore']
        except:
            pass
        scores.append((score, p))
    scores.sort(reverse=True, key=lambda x: x[0]) # descending
    out = [x[1] for x in scores if x[0] > 0]
    return out

def papers_similar(pid):
    rawpid = strip_version(pid)

    # check if we have this paper at all, otherwise return empty list
    if not rawpid in db2:
        return []

    # check if we have distances to this specific version of paper id (includes version)
    if pid in sim_dict:
        # good, simplest case: lets return the papers
        return [db2[strip_version(k)] for k in sim_dict[pid]]
    else:
        # ok we don't have this specific version. could be a stale URL that points to,
        # e.g. v1 of a paper, but due to an updated version of it we only have v2 on file
        # now. We want to use v2 in that case.
        # lets try to retrieve the most recent version of this paper we do have
        kok = [k for k in sim_dict if rawpid in k]
        if kok:
            # ok we have at least one different version of this paper, lets use it instead
            id_use_instead = kok[0]
            return [db2[strip_version(k)] for k in sim_dict[id_use_instead]]
        else:
            # return just the paper. we dont have similarities for it for some reason
            return [db2[rawpid]]

def papers_from_library():
    out = []
    if g.user:
        # user is logged in, lets fetch their saved library data
        uid = session['user_id']
        user_library = query_db('''select * from library where user_id = ?''', [uid])
        libids = [strip_version(x['paper_id']) for x in user_library]
        out = [db2[x] for x in libids]
        out = sorted(out, key=lambda k: k['updated'], reverse=True)
    return out

def papers_from_svm(recent_days=None):
    out = []
    if g.user:

        uid = int(session['user_id'])

        if not uid in user_sim:
            return []

        # we want to exclude papers that are already in user library from the result, so fetch them.
        user_library = query_db('''select * from library where user_id = ?''', [uid])
        libids = {strip_version(x['paper_id']) for x in user_library}

        plist = user_sim[uid]
        out = [db2[x] for x in plist if not x in libids]

        if recent_days is not None:
            # filter as well to only most recent papers
            curtime = int(time.time())  # in seconds
            out = [x for x in out if curtime - x['time_published'] < recent_days*24*60*60]

    return out


def papers_from_svm2(recent_days=None):
    out = []
    if g.user:

        uid = int(session['user_id'])

        if not uid in user_sim2:
            return []

        # we want to exclude papers that are already in user library from the result, so fetch them.
        user_publications = query_db('''select * from publication where user_id = ?''', [uid])
        libids = {strip_version(x['paper_id']) for x in user_publications}
        plist = user_sim2[uid]
        out = [db2[x] for x in plist if not x in libids]
        # if recent_days is not None:
        #     # filter as well to only most recent papers
        #     curtime = int(time.time())  # in seconds
        #     out = [x for x in out if curtime - x['time_published'] < recent_days*24*60*60]
        print('OUT', out[0])
    return out


def papers_filter_version(papers, v):
    if v != '1':
        return papers # noop
    intv = int(v)
    filtered = [p for p in papers if p['_version'] == intv]
    return filtered

def encode_json(ps, n=10, send_images=True, send_abstracts=True):

    libids = set()
    if g.user:
        # user is logged in, lets fetch their saved library data
        uid = session['user_id']
        user_library = query_db('''select * from library where user_id = ?''', [uid])
        libids = {strip_version(x['paper_id']) for x in user_library}

    ret = []
    for i in range(min(len(ps),n)):
        p = ps[i]
        idvv = '%sv%d' % (p['_rawid'], p['_version'])
        struct = {}
        struct['title'] = p['title']
        struct['pid'] = idvv
        struct['rawpid'] = p['_rawid']
        struct['category'] = p['arxiv_primary_category']['term']
        struct['authors'] = [a['name'] for a in p['authors']]
        struct['link'] = p['link']
        struct['in_library'] = 1 if p['_rawid'] in libids else 0
        if send_abstracts:
            struct['abstract'] = p['summary']
        if send_images:
            struct['img'] = '/static/thumbs/' + idvv + '.pdf.jpg'
        struct['tags'] = [t['term'] for t in p['tags']]

        # render time information nicely
        timestruct = dateutil.parser.parse(p['updated'])
        struct['published_time'] = '%s/%s/%s' % (timestruct.month, timestruct.day, timestruct.year)
        timestruct = dateutil.parser.parse(p['published'])
        struct['originally_published_time'] = '%s/%s/%s' % (timestruct.month, timestruct.day, timestruct.year)

        # fetch amount of discussion on this paper
        struct['num_discussion'] = comments.count({ 'pid': p['_rawid'] })

        # arxiv comments from the authors (when they submit the paper)
        cc = p.get('arxiv_comment', '')
        if len(cc) > 100:
            cc = cc[:100] + '...' # crop very long comments
        struct['comment'] = cc

        ret.append(struct)
    return ret




###########################################
## ROUTES for OAUTH
###########################################

# @app.route('/')
# def index():
#         return render_template('index.html')


@app.route('/logout')
def logout():
    logout_user()
    flash('You were logged out')
    return redirect(url_for('intmain'))


@app.route('/authorize/<provider>')
def oauth_authorize(provider):
    if not current_user.is_anonymous:
        return redirect(url_for('intmain'))
    oauth = OAuthSignIn.get_provider(provider)
    return oauth.authorize()


@app.route('/callback/<provider>')
def oauth_callback(provider):
    if not current_user.is_anonymous:
        return redirect(url_for('intmain'))
    oauth = OAuthSignIn.get_provider(provider) # should simply return 'orcid'
    print('OAUTH', oauth)
    print('PROVIDER', provider)
    try:
        response = oauth.callback()
        print('RESPONSE', response)
        # parse response
        orcid = response['orcid']
        orcid_name = response['name']
        access_token = response["access_token"]
        refresh_token = response["refresh_token"]
        retrieved = int(time.time())
        expires_in = response['expires_in']

        # parse record # TODO - move this to a separate fn
        # soup = bsoup(record,'lxml')
        # fname = soup.find('personal-details:given-names').text
        # lname = soup.find('personal-details:family-name').text

    except:
        flash('Authentication failed.')
        return redirect(url_for('intmain'))
    user = User.query.filter_by(orcid=orcid).first()
    if not user: # if user not in db, then create.
        user = User(orcid=orcid,
                    orcid_name = orcid_name,
                    username = orcid_name,
                    access_token = access_token,
                    refresh_token = refresh_token,
                    retrieved = retrieved,
                    expires_in = expires_in)
        sadb.session.add(user)
        sadb.session.commit()
    login_user(user, True)
    return redirect(url_for('intmain'))


# -----------------------------------------------------------------------------
# flask request handling
# -----------------------------------------------------------------------------

def default_context(papers, **kws):
    top_papers = encode_json(papers, 200) #args.num_results)

    # prompt logic
    show_prompt = 'no'
    try:
        if app.config['BEG_FOR_HOSTING_MONEY'] and g.user and uniform(0,1) < 0.05:
            uid = session['user_id']
            entry = goaway_collection.find_one({ 'uid':uid })
            if not entry:
                lib_count = query_db('''select count(*) from library where user_id = ?''', [uid], one=True)
                lib_count = lib_count['count(*)']
                if lib_count > 0: # user has some items in their library too
                    show_prompt = 'yes'
    except Exception as e:
        print(e)

    credentials = app.config['OAUTH_CREDENTIALS']['orcid']

    ans = dict(papers=top_papers, numresults=len(papers),
            client_id=credentials['id'],
            redirect_uri=url_for('oauth_callback', provider='orcid',_external=True),
            totpapers=len(db2), tweets=[], msg='',
            show_prompt=show_prompt, pid_to_users={})
    ans.update(kws)
    return ans

@app.route('/goaway', methods=['POST'])    # this bit stops the begging thing from popping up
def goaway():
    https_redirect()
    if not g.user: return
    uid = session['user_id']
    entry = goaway_collection.find_one({ 'uid':uid })
    if not entry: # ok record this user wanting it to stop
        username = get_username(session['user_id'])
        print('adding', uid, username, 'to goaway.')
        goaway_collection.insert_one({ 'uid':uid, 'time':int(time.time()) })
    return 'OK'

@app.route("/")
@app.route("/index")
def intmain():
    https_redirect()
    """ return user's svm sorted list """
    ttstr = request.args.get('timefilter', 'week') # default is week
    vstr = request.args.get('vfilter', 'all') # default is all (no filter)
    legend = {'day':1, '3days':3, 'week':7, 'month':30, 'year':365}
    tt = legend.get(ttstr, None)
    if g.user:
        papers = [x for x in papers_from_svm2(recent_days=tt)]
        papers += [db2[pid] for pid in DATE_SORTED_PIDS if db2[pid] not in papers]
        ctx = default_context(papers, render_format='recent',
                            msg='Recent papers relevant to your interests')
    else:
        papers = [db2[pid] for pid in DATE_SORTED_PIDS] # precomputed
        ctx = default_context(papers, render_format='recent',
                            msg='Log in with ORCID to see recommendations based on your publication history.')
    papers = papers_filter_version(papers, vstr)
    return render_template('main.html', **ctx)

@app.route("/<request_pid>")
def rank(request_pid=None):
    https_redirect()
    if not isvalidid(request_pid):
        return '' # these are requests for icons, things like robots.txt, etc
    papers = papers_similar(request_pid)
    ctx = default_context(papers, render_format='paper')
    return render_template('main.html', **ctx)

@app.route('/discuss', methods=['GET'])
def discuss():
    https_redirect()
    """ return discussion related to a paper """
    pid = request.args.get('id', '') # paper id of paper we wish to discuss
    papers = [db2[pid]] if pid in db2 else []

    # fetch the comments
    comms_cursor = comments.find({ 'pid':pid }).sort([('time_posted', pymongo.DESCENDING)])
    comms = list(comms_cursor)
    for c in comms:
        c['_id'] = str(c['_id']) # have to convert these to strs from ObjectId, and backwards later http://api.mongodb.com/python/current/tutorial.html

    # fetch the counts for all tags
    tag_counts = []
    for c in comms:
        cc = [tags_collection.count({ 'comment_id':c['_id'], 'tag_name':t }) for t in TAGS]
        tag_counts.append(cc);

    # and render
    ctx = default_context(papers, render_format='default', comments=comms, gpid=pid, tags=TAGS, tag_counts=tag_counts)
    return render_template('discuss.html', **ctx)

@app.route('/comment', methods=['POST'])
def comment():
    https_redirect()
    """ user wants to post a comment """
    anon = int(request.form['anon'])

    if g.user and (not anon):
        username = get_username(session['user_id'])
    else:
        # generate a unique username if user wants to be anon, or user not logged in.
        username = 'anon-%s-%s' % (str(int(time.time())), str(randrange(1000)))

    # process the raw pid and validate it, etc
    try:
        pid = request.form['pid']
        if not pid in db2: raise Exception("invalid pid")
        version = db[pid]['_version'] # most recent version of this paper
    except Exception as e:
        print(e)
        return 'bad pid. This is most likely Andrej\'s fault.'

    # create the entry
    entry = {
        'user': username,
        'pid': pid, # raw pid with no version, for search convenience
        'version': version, # version as int, again as convenience
        'conf': request.form['conf'],
        'anon': anon,
        'time_posted': time.time(),
        'text': request.form['text'],
    }

    # enter into database
    print(entry)
    comments.insert_one(entry)
    return 'OK'

@app.route("/discussions", methods=['GET'])
def discussions():
    https_redirect()
    # return most recently discussed papers
    comms_cursor = comments.find().sort([('time_posted', pymongo.DESCENDING)]).limit(100)

    # get the (unique) set of papers.
    papers = []
    have = set()
    for e in comms_cursor:
        pid = e['pid']
        if pid in db and not pid in have:
            have.add(pid)
            papers.append(db[pid])

    ctx = default_context(papers, render_format="discussions")
    return render_template('main.html', **ctx)

@app.route('/toggletag', methods=['POST'])
def toggletag():
    https_redirect()
    if not g.user:
        return 'You have to be logged in to tag. Sorry - otherwise things could get out of hand FAST.'

    # get the tag and validate it as an allowed tag
    tag_name = request.form['tag_name']
    if not tag_name in TAGS:
        print('tag name %s is not in allowed tags.' % (tag_name, ))
        return "Bad tag name. This is most likely Andrej's fault."

    pid = request.form['pid']
    comment_id = request.form['comment_id']
    username = get_username(session['user_id'])
    time_toggled = time.time()
    entry = {
        'username': username,
        'pid': pid,
        'comment_id': comment_id,
        'tag_name': tag_name,
        'time': time_toggled,
    }

    # remove any existing entries for this user/comment/tag
    result = tags_collection.delete_one({ 'username':username, 'comment_id':comment_id, 'tag_name':tag_name })
    if result.deleted_count > 0:
        print('cleared an existing entry from database')
    else:
        print('no entry existed, so this is a toggle ON. inserting:')
        print(entry)
        tags_collection.insert_one(entry)

    return 'OK'

@app.route("/search", methods=['GET'])
def search():
    https_redirect()
    q = request.args.get('q', '') # get the search request
    papers = papers_search(q) # perform the query and get sorted documents
    ctx = default_context(papers, render_format="search")
    return render_template('main.html', **ctx)

@app.route('/recommend', methods=['GET'])
def recommend():
    https_redirect()
    """ return user's svm sorted list """
    ttstr = request.args.get('timefilter', 'week') # default is week
    vstr = request.args.get('vfilter', 'all') # default is all (no filter)
    legend = {'day':1, '3days':3, 'week':7, 'month':30, 'year':365}
    tt = legend.get(ttstr, None)
    papers = papers_from_svm(recent_days=tt)
    papers = papers_filter_version(papers, vstr)
    ctx = default_context(papers, render_format='recommend',
                        msg='Recommended papers: (based on SVM trained on tfidf of papers in your library, refreshed every day or so)'
                        if g.user
                        else 'You must be logged in and have some papers saved in your library.')
    return render_template('main.html', **ctx)

@app.route('/top', methods=['GET'])
def top():
    https_redirect()
    """ return top papers """
    ttstr = request.args.get('timefilter', 'week') # default is week
    vstr = request.args.get('vfilter', 'all') # default is all (no filter)
    legend = {'day':1, '3days':3, 'week':7, 'month':30, 'year':365, 'alltime':10000}
    tt = legend.get(ttstr, 7)
    curtime = int(time.time()) # in seconds
    top_sorted_papers = [db2[p] for p in TOP_SORTED_PIDS]
    papers = [p for p in top_sorted_papers if curtime - p['time_published'] < tt*24*60*60]
    papers = papers_filter_version(papers, vstr)
    ctx = default_context(papers, render_format='top',
                                msg='Top papers based on people\'s libraries:')
    return render_template('main.html', **ctx)

@app.route('/toptwtr', methods=['GET'])
def toptwtr():
    https_redirect()
    """ return top papers """
    ttstr = request.args.get('timefilter', 'day') # default is day
    tweets_top = {'day':tweets_top1, 'week':tweets_top7, 'month':tweets_top30}[ttstr]
    cursor = tweets_top.find().sort([('vote', pymongo.DESCENDING)]).limit(100)
    papers, tweets = [], []
    for rec in cursor:
        if rec['pid'] in db2:
            papers.append(db2[rec['pid']])
            tweet = {k:v for k,v in rec.items() if k != '_id'}
            tweets.append(tweet)
    ctx = default_context(papers, render_format='toptwtr', tweets=tweets,
                        msg='Top papers mentioned on Twitter over last ' + ttstr + ':')
    return render_template('main.html', **ctx)

@app.route('/library')
def library():
    https_redirect()
    """ render user's library """
    papers = papers_from_library()
    ret = encode_json(papers, 500) # cap at 500 papers in someone's library. that's a lot!
    if g.user:
        msg = '%d papers in your library:' % (len(ret), )
    else:
        msg = 'You must be logged in. Once you are, you can save papers to your library (with the save icon on the right of each paper) and they will show up here.'
    ctx = default_context(papers, render_format='library', msg=msg)
    return render_template('main.html', **ctx)

@app.route('/libtoggle', methods=['POST'])
def review():
    https_redirect()
    """ user wants to toggle a paper in her library """
    # make sure user is logged in
    if not g.user:
        print('Not logged in')
        return 'NO' # fail... (not logged in). JS should prevent from us getting here.

    idvv = request.form['pid'] # includes version
    if not isvalidid(idvv):
        print('Invalid id')
        return 'NO' # fail, malformed id. weird.
    pid = strip_version(idvv)
    if not pid in db2:
        print('pid does not exist')
        return 'NO' # we don't know this paper. wat

    uid = session['user_id'] # id of logged in user

    # check this user already has this paper in library
    record = query_db('''select * from library where
                    user_id = ? and paper_id = ?''', [uid, pid], one=True)

    ret = 'NO'
    if record:
        # record exists, erase it.
        g.db2.execute('''delete from library where user_id = ? and paper_id = ?''', [uid, pid])
        g.db2.commit()
        #print('removed %s for %s' % (pid, uid))
        ret = 'OFF'
    else:
        # record does not exist, add it.
        rawpid = strip_version(pid)
        g.db2.execute('''insert into library (paper_id, user_id, update_time) values (?, ?, ?)''',
                [rawpid, uid, int(time.time())])
        g.db2.commit()
        #print('added %s for %s' % (pid, uid))
        ret = 'ON'

    return ret

@app.route('/friends', methods=['GET'])
def friends():
    https_redirect()
    ttstr = request.args.get('timefilter', 'week') # default is week
    legend = {'day':1, '3days':3, 'week':7, 'month':30, 'year':365}
    tt = legend.get(ttstr, 7)

    papers = []
    pid_to_users = {}
    if g.user:
        # gather all the people we are following
        username = get_username(session['user_id'])
        edges = list(follow_collection.find({ 'who':username }))
        # fetch all papers in all of their libraries, and count the top ones
        counts = {}
        for edict in edges:
            whom = edict['whom']
            uid = get_user_id(whom)
            user_library = query_db('''select * from library where user_id = ?''', [uid])
            libids = [strip_version(x['paper_id']) for x in user_library]
            for lid in libids:
                if not lid in counts:
                    counts[lid] = []
                counts[lid].append(whom)

        keys = list(counts.keys())
        keys.sort(key=lambda k: len(counts[k]), reverse=True) # descending by count
        papers = [db2[x] for x in keys]
        # finally filter by date
        curtime = int(time.time()) # in seconds
        papers = [x for x in papers if curtime - x['time_published'] < tt*24*60*60]
        # trim at like 100
        if len(papers) > 100: papers = papers[:100]
        # trim counts as well correspondingly
        pid_to_users = { p['_rawid'] : counts.get(p['_rawid'], []) for p in papers }

    if not g.user:
        msg = "You must be logged in and follow some people to enjoy this tab."
    else:
        if len(papers) == 0:
            msg = "No friend papers present. Try to extend the time range, or add friends by clicking on your account name (top, right)"
        else:
            msg = "Papers in your friend's libraries:"

    ctx = default_context(papers, render_format='friends', pid_to_users=pid_to_users, msg=msg)
    return render_template('main.html', **ctx)

@app.route('/account')
def account():
    https_redirect

    ctx = { 'totpapers':len(db)}

    followers = []
    following = []
    # fetch all followers/following of the logged in user
    if g.user:
        username = get_username(session['user_id'])

        following_db = list(follow_collection.find({ 'who':username }))
        for e in following_db:
            following.append({ 'user':e['whom'], 'active':e['active'] })

        followers_db = list(follow_collection.find({ 'whom':username }))
        for e in followers_db:
            followers.append({ 'user':e['who'], 'active':e['active'] })

    ctx['followers'] = followers
    ctx['following'] = following
    return render_template('account.html', **ctx)

@app.route('/requestfollow', methods=['POST'])
def requestfollow():
    https_redirect()
    if request.form['newf'] and g.user:
        # add an entry: this user is requesting to follow a second user
        who = get_username(session['user_id'])
        whom = request.form['newf']
        # make sure whom exists in our database
        whom_id = get_user_id(whom)
        if whom_id is not None:
            e = { 'who':who, 'whom':whom, 'active':0, 'time_request':int(time.time()) }
            print('adding request follow:')
            print(e)
            follow_collection.insert_one(e)

    return redirect(url_for('account'))

@app.route('/removefollow', methods=['POST'])
def removefollow():
    https_redirect()
    user = request.form['user']
    lst = request.form['lst']
    if user and lst:
        username = get_username(session['user_id'])
        if lst == 'followers':
            # user clicked "X" in their followers list. Erase the follower of this user
            who = user
            whom = username
        elif lst == 'following':
            # user clicked "X" in their following list. Stop following this user.
            who = username
            whom = user
        else:
            return 'NOTOK'

        delq = { 'who':who, 'whom':whom }
        print('deleting from follow collection:', delq)
        follow_collection.delete_one(delq)
        return 'OK'
    else:
        return 'NOTOK'

@app.route('/addfollow', methods=['POST'])
def addfollow():
    https_redirect()
    user = request.form['user']
    lst = request.form['lst']
    if user and lst:
        username = get_username(session['user_id'])
        if lst == 'followers':
            # user clicked "OK" in the followers list, wants to approve some follower. make active.
            who = user
            whom = username
            delq = { 'who':who, 'whom':whom }
            print('making active in follow collection:', delq)
            follow_collection.update_one(delq, {'$set':{'active':1}})
            return 'OK'

    return 'NOTOK'
