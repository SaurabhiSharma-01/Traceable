"""
domain_lists.py — Curated domain lists for source classification and primary source detection.
"""
from __future__ import annotations

# Official TLDs and government/academic domain suffixes
OFFICIAL_SUFFIXES = (
    ".gov",
    ".gov.in",
    ".nic.in",
    ".gov.uk",
    ".gov.au",
    ".gov.ca",
    ".edu",
    ".edu.in",
    ".ac.in",
    ".ac.uk",
    ".res.in",
    ".mil",
)

# Known legitimate news outlets
NEWS_DOMAINS = {
    "bbc.com",
    "bbc.co.uk",
    "reuters.com",
    "apnews.com",
    "thehindu.com",
    "ndtv.com",
    "indianexpress.com",
    "hindustantimes.com",
    "timesofindia.indiatimes.com",
    "livemint.com",
    "economictimes.indiatimes.com",
    "news18.com",
    "indiatoday.in",
    "theprint.in",
    "scroll.in",
    "thewire.in",
    "aljazeera.com",
    "theguardian.com",
    "cnn.com",
    "bloomberg.com",
}

# Educational listing / aggregator / coaching portals
AGGREGATOR_DOMAINS = {
    "buddy4study.com",
    "shiksha.com",
    "collegedunia.com",
    "careers360.com",
    "jagranjosh.com",
    "embibe.com",
    "getmyuni.com",
    "collegedekho.com",
    "sarkariresult.com",
    "sarkariresults.info",
    "safalta.com",
    "testbook.com",
    "unacademy.com",
    "byjus.com",
    "adda247.com",
    "freshersworld.com",
    "indgovtjobs.in",
    "scholarshipsads.com",
}

# Generic listicle / aggregator title indicators
AGGREGATOR_TITLE_PATTERNS = [
    "top 10",
    "top 5",
    "list of",
    "all you need to know",
    "complete guide",
    "everything you need",
    "scholarship details, eligibility",
]

# Forums and Q&A communities
FORUM_DOMAINS = {
    "reddit.com",
    "quora.com",
    "stackexchange.com",
    "stackoverflow.com",
    "pagalguy.com",
    "discourse",
    "forum",
}

# User-generated blogging platforms
BLOG_DOMAINS = {
    "blogspot.com",
    "wordpress.com",
    "medium.com",
    "substack.com",
    "tumblr.com",
    "wixsite.com",
    "weebly.com",
}

