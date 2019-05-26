import os

commands = [
        'python fetch_papers.py',
        'python download_pdfs.py',
        'python app/parse_pdf_to_text.py',
        'python app/thumb_pdf.py & python analyze.py',
        'python app/buildsvm.py',
        'python app/make_cache.py'
        ]


for command in commands:
    os.system(command)
