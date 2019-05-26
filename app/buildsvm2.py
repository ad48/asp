# ## TODO - add orcid history grab here.
# # from .. import app
#
#
# # standard imports
# import os
# import sys
# import pickle
# # non-standard imports
# import numpy as np
# from sklearn import svm
# from sqlite3 import dbapi2 as sqlite3
#
# from config import Config as config
# # local imports
#
# from app.utils import safe_pickle_dump, strip_version
#
# num_recommendations = 1000 # papers to recommend per user
# # -----------------------------------------------------------------------------
#
# if not os.path.isfile(config.DATABASE_PATH']):
#     print("the database file as.db should exist. You can create an empty database with sqlite3 as.db < schema.sql")
#     sys.exit()
#
# sqldb = sqlite3.connect(config.DATABASE_PATH'])
# sqldb.row_factory = sqlite3.Row # to return dicts rather than tuples
#
# def query_db(query, args=(), one=False):
#     """Queries the database and returns a list of dictionaries."""
#     cur = sqldb.execute(query, args)
#     rv = cur.fetchall()
#     return (rv[0] if rv else None) if one else rv
#
# # -----------------------------------------------------------------------------
#
# # fetch all users
# users = query_db('''select * from user''')
# print('number of users: ', len(users))
#
# # load the tfidf matrix and meta
# meta = pickle.load(open(config.META_PATH'], 'rb'))
# out = pickle.load(open(config.tfidf_path'], 'rb'))
# X = out['X']
# X = X.todense()
#
# xtoi = { strip_version(x):i for x,i in meta['ptoi'].items() }
#
# user_sim = {}
# for ii,u in enumerate(users):
#     print("%d/%d building an SVM for %s" % (ii, len(users), u['username'].encode('utf-8')))
#     uid = u['user_id']
#     lib = query_db('''select * from library where user_id = ?''', [uid])
#     pids = [x['paper_id'] for x in lib] # raw pids without version
#     posix = [xtoi[p] for p in pids if p in xtoi]
#
#     if not posix:
#         continue # empty library for this user maybe?
#
#     print(pids)
#     y = np.zeros(X.shape[0])
#     for ix in posix: y[ix] = 1
#
#     clf = svm.LinearSVC(class_weight='balanced', verbose=False, max_iter=10000, tol=1e-6, C=0.1)
#     clf.fit(X,y)
#     s = clf.decision_function(X)
#
#     sortix = np.argsort(-s)
#     sortix = sortix[:min(num_recommendations, len(sortix))] # crop paper recommendations to save space
#     user_sim[uid] = [strip_version(meta['pids'][ix]) for ix in list(sortix)]
#
# print('writing', config.USER_SIM2_PATH)
# safe_pickle_dump(user_sim, config.USER_SIM2_PATH)
