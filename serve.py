# TODO -- separate this into 2 applications (?)  one updates everything, the other runs the webapp
# importantly this means having 2 separate config files
# update files should include updates for all the databases. <- this is a problem because both applications use the same dbs. requires sharing models.py


from app import app, sadb, lm
from app.models import User, Library, Publication

import os
import pickle
import argparse
import pymongo
import ssl
from flask_sslify import SSLify


# -----------------------------------------------------------------------------
# int main
# -----------------------------------------------------------------------------

if __name__ == "__main__":


    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--prod', dest='prod', action='store_true', help='run in prod?')
    parser.add_argument('-r', '--num_results', dest='num_results', type=int, default=200, help='number of results to return per query')
    parser.add_argument('--port', dest='port', type=int, default=5000, help='port to serve on')
    args = parser.parse_args()
    print('Production?',args.prod)

# TODO - fix this!

    # print()
    # print('***** HERE *******')
    # print(args)

    # from app import app, db

    if os.path.exists(app.config['DATABASE_PATH']):

        pass
    else:
        print('DATABASE NOT FOUND.  CREATING EMPTY TABLES')
        sadb.create_all()
        print('databases created...')
    # app.config['ARGS'] = args # TODO supposed to feed into routes.py
    # print()
    # print(app.config)
    # print()
    # from app.models import User, Library, Publication

    if not os.path.isfile(app.config['DATABASE_PATH']):
        print('did not find as.db, trying to create an empty database from schema.sql...')
        print('this needs sqlite3 to be installed!')
        os.system('sqlite3 as.db < schema.sql')

    # print('loading the paper database', app.config['db_serve_path)
    # db2 = pickle.load(open(app.config['db_serve_path, 'rb'))

    # print('loading tfidf_meta', app.config['META_PATH'])
    # meta = pickle.load(open(app.config['META_PATH'], "rb"))
    # vocab = meta['vocab']
    # idf = meta['idf']
    #
    # print('loading paper similarities', app.config['SIM_PATH'])
    # sim_dict = pickle.load(open(app.config['SIM_PATH'], "rb"))
    #
    # print('loading user recommendations', app.config['USER_SIM_PATH'])
    # user_sim = {}
    # if os.path.isfile(app.config['USER_SIM_PATH']):
    #     user_sim = pickle.load(open(app.config['USER_SIM_PATH'], 'rb'))
    #
    # # print('loading serve cache...', app.config['serve_cache_path)
    # # cache = pickle.load(open(app.config['serve_cache_path, "rb"))
    # # DATE_SORTED_PIDS = cache['date_sorted_pids']
    # # TOP_SORTED_PIDS = cache['top_sorted_pids']
    # # SEARCH_DICT = cache['search_dict']
    #
    # print('connecting to mongodb...')
    # client = pymongo.MongoClient()
    # mdb = client.arxiv
    # tweets_top1 = mdb.tweets_top1
    # tweets_top7 = mdb.tweets_top7
    # tweets_top30 = mdb.tweets_top30
    # comments = mdb.comments
    # tags_collection = mdb.tags
    # goaway_collection = mdb.goaway
    # follow_collection = mdb.follow
    # print('mongodb tweets_top1 collection size:', tweets_top1.count())
    # print('mongodb tweets_top7 collection size:', tweets_top7.count())
    # print('mongodb tweets_top30 collection size:', tweets_top30.count())
    # print('mongodb comments collection size:', comments.count())
    # print('mongodb tags collection size:', tags_collection.count())
    # print('mongodb goaway collection size:', goaway_collection.count())
    # print('mongodb follow collection size:', follow_collection.count())
    #
    # TAGS = ['insightful!', 'thank you', 'agree', 'disagree', 'not constructive', 'troll', 'spam']

    # start
    if args.prod:
        # run on Tornado instead, since running raw Flask in prod is not recommended
        print('starting tornado!')
        from tornado.wsgi import WSGIContainer
        from tornado.httpserver import HTTPServer
        from tornado.ioloop import IOLoop
        from tornado.log import enable_pretty_logging
        enable_pretty_logging()

        if app.config['HTTPS'] == 1 :
            import ssl
            from flask_sslify import SSLify
            sslify = SSLify(app)
            # ssl from http://www.tornadoweb.org/en/stable/httpserver.html
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain('/etc/letsencrypt/live/gr-asp.net/cert.pem',
                                    '/etc/letsencrypt/live/gr-asp.net/privkey.pem')
            http_server = HTTPServer(WSGIContainer(app),
                                    protocol = 'https',
                                    ssl_options = ssl_ctx)
            http_server.listen(args.port)
        else:
            http_server = HTTPServer(WSGIContainer(app))
            http_server.listen(args.port) # args.port)  # used to be args.port, but wanted to switch to 443 for https,so hard-coding this
        IOLoop.instance().start()
    else:
        print('starting flask!')
        app.debug = False
    try: # PATH TO SSL KEY FILES ON THE SERVER
        ssl_context=('/etc/letsencrypt/live/gr-asp.net/cert.pem',
                    '/etc/letsencrypt/live/gr-asp.net/privkey.pem')
    except:
        ssl_context=('cert.pem',
                    'key.pem')
    # app.run(ssl_context='adhoc') ## this will work with pyopenssl installed
    app.run(port=args.port,
            host='0.0.0.0',
            debug=True,
            ssl_context=('cert.pem',
                        'key.pem'))
