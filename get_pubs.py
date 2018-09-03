#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function

import json
from operator import itemgetter
import re
import ads
from utf8totex import utf8totex
from titlecase import titlecase
from tqdm import tqdm
import numpy as np
import time

__all__ = ["get_papers"]


def title_callback(word, **kwargs):
    if '\\' in word:
        return word
    else:
        return None


def format_title(arg):
    '''
    Customized!

    '''

    # Do the conversion
    arg = utf8totex(arg)

    # Handle subscripts
    arg = re.sub('<SUB>(.*?)</SUB>', r'$_\1$', arg)

    # Fudge O2 paper
    arg = re.sub('O2Buildup', r'O$_2$ Buildup', arg)

    # Capitalize!
    arg = titlecase(arg, callback=title_callback)

    return arg


def format_authors(authors):
    '''
    Customized!

    '''

    # Do the conversion
    authors = list(map(utf8totex, authors))

    # Abbreviate names. This drops middle
    # initials -- should eventually fix this.
    for i, author in enumerate(authors):
        match = re.match('^(.*?),\s(.*?)$', author)
        if match is not None:
            first, last = match.groups()
            authors[i] = '%s, %s.' % (first, last[0])

    return authors


def manual_exclude(paper):
    """Manual exclusions."""
    # Remove DDS talks
    if paper.pub == "LPI Contributions":
        return True

    # Remove Vikki's astrobio paper duplicate
    '''
    if paper.author[0].startswith("Meadows") and \
       paper.title[0].startswith("The Habitability of Proxima"):
        if paper.pub == "Astrobiology":
            return True
        else:
            paper.id = "25657744"
            paper.pub = "Astrobiology"
            paper.year = "2018"
            paper.doctype = "article"
            paper.doi = ["10.1089/ast.2016.1589"]
            paper.page = ["133"]
            paper.pubdate = "2018-02-00"
            paper.bibcode = "2018AsBio..18..133M"
            paper.volume = "18"
    '''

    return False


def get_papers(author):
    papers = list(ads.SearchQuery(
        author=author,
        fl=["id", "title", "author", "doi", "year", "pubdate", "pub",
            "volume", "page", "identifier", "doctype", "citation_count",
            "bibcode", "citation"],
        max_pages=100,
    ))
    dicts = []

    # Count the citations as a function of time every 30 days
    last_updated = np.loadtxt('citedates.txt')[0]
    if (time.time() - last_updated) > (86400 * 30):
        citedates = []
        last_updated = time.time()
        count_cites = True
    else:
        citedates = np.loadtxt('citedates.txt')[1:]
        count_cites = False

    for paper in papers:

        if not (("Luger, Rodrigo" in paper.author) or
                ("Luger, R." in paper.author) or
                ("Luger, R" in paper.author)):
            continue

        if manual_exclude(paper):
            continue

        aid = [":".join(t.split(":")[1:]) for t in paper.identifier
               if t.startswith("arXiv:")]
        for t in paper.identifier:
            if len(t.split(".")) != 2:
                continue
            try:
                list(map(int, t.split(".")))
            except ValueError:
                pass
            else:
                aid.append(t)
        try:
            page = int(paper.page[0])
        except ValueError:
            page = None
            if paper.page[0].startswith("arXiv:"):
                aid.append(":".join(paper.page[0].split(":")[1:]))
        except TypeError:
            page = None

        # Get citation dates
        if count_cites and paper.citation is not None:
            for i, bibcode in tqdm(enumerate(paper.citation),
                                   total=len(paper.citation)):
                cite = list(ads.SearchQuery(bibcode=bibcode,
                                            fl=["pubdate"]))[0]
                date = int(cite.pubdate[:4]) + int(cite.pubdate[5:7]) / 12.
                citedates.append(date)

        dicts.append(dict(
            doctype=paper.doctype,
            authors=format_authors(paper.author),
            year=paper.year,
            pubdate=paper.pubdate,
            doi=paper.doi[0] if paper.doi is not None else None,
            title=format_title(paper.title[0]),
            pub=paper.pub,
            volume=paper.volume,
            page=page,
            arxiv=aid[0] if len(aid) else None,
            citations=paper.citation_count,
            url="http://adsabs.harvard.edu/abs/" + paper.bibcode,
        ))

    # Sort the cite dates and prepend the date
    # they were last updated
    citedates = [last_updated] + sorted(citedates)

    return sorted(dicts, key=itemgetter("pubdate"), reverse=True), citedates


if __name__ == "__main__":
    papers, citedates = get_papers("Luger, R")
    np.savetxt('citedates.txt', citedates, fmt='%.3f')
    with open("pubs.json", "w") as f:
        json.dump(papers, f, sort_keys=True, indent=2, separators=(",", ": "))
