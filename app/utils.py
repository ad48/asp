from contextlib import contextmanager

import os
import re
import json
import pickle
import tempfile
# get current y/mo
from datetime import datetime as dt
import feedparser
import requests

import shutil


# Context managers for atomic writes courtesy of
# http://stackoverflow.com/questions/2333872/atomic-writing-to-file-with-python
@contextmanager
def _tempfile(*args, **kws):
    """ Context for temporary file.

    Will find a free temporary filename upon entering
    and will try to delete the file on leaving

    Parameters
    ----------
    suffix : string
        optional file suffix
    """

    fd, name = tempfile.mkstemp(*args, **kws)
    os.close(fd)
    try:
        yield name
    finally:
        try:
            os.remove(name)
        except OSError as e:
            if e.errno == 2:
                pass
            else:
                raise e


@contextmanager
def open_atomic(filepath, *args, **kwargs):
    """ Open temporary file object that atomically moves to destination upon
    exiting.

    Allows reading and writing to and from the same filename.

    Parameters
    ----------
    filepath : string
        the file path to be opened
    fsync : bool
        whether to force write the file to disk
    kwargs : mixed
        Any valid keyword arguments for :code:`open`
    """
    fsync = kwargs.pop('fsync', False)

    with _tempfile(dir=os.path.dirname(filepath)) as tmppath:
        with open(tmppath, *args, **kwargs) as f:
            yield f
            if fsync:
                f.flush()
                os.fsync(file.fileno())  # originally file.fileno() try f.fileno?
        try:
            os.rename(tmppath, filepath)
        except:
            # above doesn't always work - think it's a windows problem.  Shutil seems to solve the problem.
            shutil.move(tmppath, filepath)

def safe_pickle_dump(obj, fname):
    with open_atomic(fname, 'wb') as f:
        pickle.dump(obj, f, -1)


# arxiv utils
# -----------------------------------------------------------------------------

def strip_version(idstr):
    """ identity function if arxiv id has no version, otherwise strips it. """
    parts = idstr.split('v')
    return parts[0]

# "1511.08198v1" is an example of a valid arxiv id that we accept
def isvalidid(pid):
  return re.match('^\d+\.\d+(v\d+)?$', pid)




def pidify(entry):
    entry = entry['id']
    prefix = 'http://arxiv.org/abs/'
    prefix_end =  len(prefix)
    pid = entry[prefix_end:entry.rfind('v')]
    return pid

def check_pid_recent(pid):
    if pid[0].isdigit()==False: # drop anything with old style pid format
        return False
    now = dt.now()
    current_year = int(str(now.year)[-2:])
    current_month = int(now.month)
    y = int(pid[:2])
    m = int(pid[2:4])
    if y > current_year-3 or (y ==current_year-3 and m <= current_month):
        return True
    else:
        return False

def get_recent_work(orcid):
    url = "https://arxiv.org/a/"+orcid+'.atom2'
    r = requests.get(url)
    js = feedparser.parse(r.text)
    entries = js['entries']
    dct = {}
    if len(entries)>0:
        for entry in entries:
            pid = pidify(entry)

            if check_pid_recent(pid)==True:
                try:
                    doi = entry['arxiv_doi']
                except:
                    doi = ''
                dct[pid] = doi
            else:
                pass
    else:
        pass

    return dct
