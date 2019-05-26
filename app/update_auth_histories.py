## TODO see the libtoggle fn in serve.py
# from config import Config as config

from config import Config as config
from flask import Flask

import os
from sqlite3 import dbapi2 as sqlite3
# local imports
from utils import safe_pickle_dump, strip_version, get_recent_work
import time


num_recommendations = 1000 # papers to recommend per user
# -----------------------------------------------------------------------------

if not os.path.isfile(config.DATABASE_PATH):
    print("the database file as.db should exist. You can create an empty database with sqlite3 as.db < schema.sql")
    sys.exit()

sqldb = sqlite3.connect(config.DATABASE_PATH)
sqldb.row_factory = sqlite3.Row # to return dicts rather than tuples


def query_db(query, args=(), one=False):
    """Queries the database and returns a list of dictionaries."""
    cur = sqldb.execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

# -----------------------------------------------------------------------------

# fetch all users
users = query_db('''select * from user''')
print('number of users: ', len(users))
cursor = sqldb.cursor()

##  SQLAlchemy STUFF
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
#
# from models import User, Library, Publication
#
# engine = create_engine('sqlite:///as.db')
# Base.metadata.bind = engine
#
# DBSession = sessionmaker(bind=engine)
# session = DBSession()



for user in users:
    user_id = user[0]
    user_orcid = user[1]
    recent = get_recent_work(user_orcid) #dict of { pid : doi } # where doi not present, get ''
    if recent == {}:
        continue
    else:
        for pid in recent:
            # first check if pid and user_id already exist together in the db
            # TODO is there a need to iterate over the whole thing?  Maybe index paperid col.
            publications = query_db('''select * from publication WHERE paper_id = \'{}\';'''.format(pid))
            present = 'NO'
            for publication in publications:
                if publication['user_id'] == user_id:
                    present = 'YES'
                    break
                else:
                    pass
            if present == 'YES':
                continue
            else:
                # if there are no matches in the db, add a row
                doi = recent[pid]
                update_time = int(time.time())

                sql = """INSERT INTO publication (\
                user_id, paper_id, doi, update_time) \
                VALUES (\
                \'{}\',\'{}\',\'{}\',\'{}\')""".format(user_id, pid, doi, update_time)
                cursor.execute(sql)

sqldb.commit()
sqldb.close()


### part of a script to conver the above to sqlalchemy
#             publication = Publication(user_id = user_id,
#                                         paper_id = pid,
#                                         doi = doi,
#                                         update_time = update_time)
#             sadb.session.add(publication)
#             sadb.session.commit()
# sadb.close()
