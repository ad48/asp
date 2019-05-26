
# arxiv sanity preserver

This project has been adapted from a version of Andrej Karpathy's _ArXiv Sanity Preserver_: a web interface that attempts to tame the overwhelming flood of papers on Arxiv. I used _ArXiv Sanity_ as a template to teach myself Flask apps - along with Miguel Grinberg's excellent book on this subject. This app served for several months at gr-asp.net.  However, at the time of writing the app is no longer serving.

This app differs from the original ArXiv Sanity in a number of ways:
- app serves with https instead of http
- Users now log in with ORCID. This is safer than sending passwords over an http connection and also allows unambiguous identification of individuals.
- ORCID records are used to find an author's publication history.  Those articles are classified using an SVM.  This SVM is used to identify related new articles and serve them to the user.
- Some organisational changes have been made to the code to bring it more in-line with advice in Miguel Grinberg's book.
- There hasn't been much in the way of testing and debugging, so if these changes have caused new bugs to arise, I haven't checked thoroughly for that.

This app allows researchers to keep track of recent papers, search for papers, sort papers by similarity to any paper, see recent popular papers, to add papers to a personal library, and to get personalized recommendations of (new or old) Arxiv papers. This code is currently running live at [www.arxiv-sanity.com/](http://www.arxiv-sanity.com/), where it's serving 25,000+ Arxiv papers from Machine Learning (cs.[CV|AI|CL|LG|NE]/stat.ML) over the last ~3 years. With this code base you could replicate the website to any of your favorite subsets of Arxiv by simply changing the categories in `fetch_papers.py`.

![user interface](https://raw.github.com/karpathy/arxiv-sanity-preserver/master/ui.jpeg)



### Code layout

There are two large parts of the code:

**Indexing code**. Uses Arxiv API to download the most recent papers in any categories you like, and then downloads all papers, extracts all text, creates tfidf vectors based on the content of each paper. This code is therefore concerned with the backend scraping and computation: building up a database of arxiv papers, calculating content vectors, creating thumbnails, computing SVMs for people, etc.

**User interface**. Then there is a web server (based on Flask/Tornado/sqlite) that allows searching through the database and filtering papers by similarity, etc.

### Dependencies

Several: You will need numpy, feedparser (to process xml files), scikit learn (for tfidf vectorizer, training of SVM), flask (for serving the results), flask_limiter, and tornado (if you want to run the flask server in production). Also dateutil, and scipy. And sqlite3 for database (accounts, library support, etc.). Most of these are easy to get through `pip`, e.g.:

```bash
$ virtualenv env                # optional: use virtualenv
$ source env/bin/activate       # optional: use virtualenv
$ pip install -r requirements.txt
```

You will also need [ImageMagick](http://www.imagemagick.org/script/index.php) and [pdftotext](https://poppler.freedesktop.org/), which you can install on Ubuntu as `sudo apt-get install imagemagick poppler-utils`. Bleh, that's a lot of dependencies isn't it.

### Processing pipeline

The processing pipeline requires you to run a series of scripts, and at this stage I really encourage you to manually inspect each script, as they may contain various inline settings you might want to change. In order, the processing pipeline is:

1. Run `fetch_papers.py` to query arxiv API and create a file `db.p` that contains all information for each paper. This script is where you would modify the **query**, indicating which parts of arxiv you'd like to use. Note that if you're trying to pull too many papers arxiv will start to rate limit you. You may have to run the script multiple times, and I recommend using the arg `--start-index` to restart where you left off when you were last interrupted by arxiv.
2. Run `download_pdfs.py`, which iterates over all papers in parsed pickle and downloads the papers into folder `pdf`
3. Run `parse_pdf_to_text.py` to export all text from pdfs to files in `txt`
4. Run `thumb_pdf.py` to export thumbnails of all pdfs to `thumb`
5. Run `analyze.py` to compute tfidf vectors for all documents based on bigrams. Saves a `tfidf.p`, `tfidf_meta.p` and `sim_dict.p` pickle files.
6. Run `buildsvm.py` to train SVMs for all users (if any), exports a pickle `user_sim.p`
7. Run `make_cache.py` for various preprocessing so that server starts faster (and make sure to run `sqlite3 as.db < schema.sql` if this is the very first time ever you're starting arxiv-sanity, which initializes an empty database).
8. Run the flask server with `serve.py`. Visit localhost:5000 and enjoy sane viewing of papers!

Optionally you can also run the `twitter_daemon.py` in a screen session, which uses your Twitter API credentials (stored in `twitter.txt`) to query Twitter periodically looking for mentions of papers in the database, and writes the results to the pickle file `twitter.p`.

I have a simple shell script that runs these commands one by one, and every day I run this script to fetch new papers, incorporate them into the database, and recompute all tfidf vectors/classifiers. More details on this process below.

**protip: numpy/BLAS**: The script `analyze.py` does quite a lot of heavy lifting with numpy. I recommend that you carefully set up your numpy to use BLAS (e.g. OpenBLAS), otherwise the computations will take a long time. With ~25,000 papers and ~5000 users the script runs in several hours on my current machine with a BLAS-linked numpy.

### Running online

Due to the adaptations in this version of the app, there are a few differences in how it is run online.
- https certification can be done in a number of ways.  I used AWS and followed these guidelines https://blog.miguelgrinberg.com/post/running-your-flask-application-over-https (this took some time for me to get right, more detailed instrucitons on https are below)
- ORCID authentication can be done by registering at the ORCID site. https://members.orcid.org/api/oauth2 Note that, for large applications, ORCID membership may be required. I stored my orcid credentials in a json file `orcid_credentials.json`.  However, it may be better to put the credentials in environment variables.

If you'd like to run the flask server online (e.g. AWS) run it as `python serve.py --prod`.

You also want to create a `secret_key.txt` file and fill it with random text (see top of `serve.py`).

### Current workflow

Running the site live is not currently set up for a fully automatic plug and play operation. Instead it's a bit of a manual process and I thought I should document how I'm keeping this code alive right now. I have a script that performs the following update early morning after arxiv papers come out (~midnight PST):

```bash
python fetch_papers.py
python download_pdfs.py
python parse_pdf_to_text.py
python thumb_pdf.py
python analyze.py
python buildsvm.py
python make_cache.py
```

I run the server in a screen session, so `screen -S serve` to create it (or `-r` to reattach to it) and run:

```bash
python serve.py --prod --port 80
```

The server will load the new files and begin hosting the site. Note that on some systems you can't use port 80 without `sudo`. Your two options are to use `iptables` to reroute ports or you can use [setcap](http://stackoverflow.com/questions/413807/is-there-a-way-for-non-root-processes-to-bind-to-privileged-ports-1024-on-l) to elavate the permissions of your `python` interpreter that runs `serve.py`. In this case I'd recommend careful permissions and maybe virtualenv, etc.

### Running with HTTPS
1. Obtain a certificate from a certificate authority
$ sudo apt-get install software-properties-common
$ sudo add-apt-repository ppa:certbot/certbot
$ sudo apt-get update
$ sudo apt-get install certbot
$ sudo certbot certonly --manual -d gr-asp.net --email INSERTYOUREMAILHERE --preferred-challenges dns-01

Note that this command requires following some manual steps and then you need to update the DNS settings in Route 53.  Remember to wait a few minutes between updating Route 53 and completing the test since AWS takes a few minutes to update.

2. Modify serve.py to serve https over port 443.  Remember that there are some new dependecies: flask_sslify  

<!-- if Config.https==1:
    import ssl
    from flask_sslify import SSLify
    sslify = SSLify(app)
    # ssl from http://www.tornadoweb.org/en/stable/httpserver.html
    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain('/etc/letsencrypt/live/[DOMAIN]/cert.pem',
                        '/etc/letsencrypt/live/[DOMAIN]/privkey.pem')

    http_server = HTTPServer(WSGIContainer(app),
                            protocol = 'https',
                            ssl_options = ssl_ctx)
    http_server.listen(args.port) -->

3. launch the server differently.
$ sudo venv/bin/python --prod --port 443

Note that it can take a while for the page to load after you start the server.
