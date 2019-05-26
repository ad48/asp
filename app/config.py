import os
import json
# basedir = os.path.abspath(os.path.dirname(__file__))
# os.chdir('.') # fixes an odd error?
# -----------------------------------------------------------------------------

def pth(p):
    dirname = os.path.dirname(__file__)
    return os.path.join(dirname, p)

class Config(object):
    # main paper information repo file
    DB_PATH = pth('db.p')
    # intermediate processing folders
    PDF_DIR = pth(os.path.join('data', 'pdf'))
    TXT_DIR = pth(os.path.join('data', 'txt'))
    THUMBS_DIR = pth(os.path.join('static', 'thumbs'))
    # intermediate pickles
    TFIDF_PATH = pth('tfidf.p')
    META_PATH = pth('tfidf_meta.p')
    SIM_PATH = pth('sim_dict.p')

    USER_SIM_PATH = pth('user_sim.p')
    USER_SIM2_PATH = pth('user_sim2.p')
    # sql database file
    DB_SERVE_PATH = pth('db2.p')  # an enriched db.p with various preprocessing info
    DATABASE_PATH = pth('as.db')
    SERVE_CACHE_PATH = pth('serve_cache.p')

    HTTPS = 1  # 1 is on 0 is off
    BEG_FOR_HOSTING_MONEY = 0  # do we beg the active users randomly for money? 0 = no.
    BANNED_PATH = pth('banned.txt')  # for twitter users who are banned
    TMP_DIR = pth('tmp')

    # database configuration
    secret_key_path = pth('secret_key.txt')
    if os.path.isfile(secret_key_path):
        SECRET_KEY = open(secret_key_path, 'r').read()
    else:
        SECRET_KEY = 'devkey, should be in a file'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///as.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # oauth
    orcid_credentials = pth('../orcid_credentials.json')
    with open(orcid_credentials,'r') as f:
        orcid_creds = json.loads(f.read())
    OAUTH_CREDENTIALS = orcid_creds
