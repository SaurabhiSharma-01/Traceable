from __future__ import annotations

from typing import Literal

# Known news domains (partial match)
_NEWS_DOMAINS = {
    "bbc.com", "bbc.co.uk", "reuters.com", "thehindu.com", "ndtv.com",
    "indiatimes.com", "timesofindia.com", "theguardian.com", "nytimes.com",
    "washingtonpost.com", "aljazeera.com", "hindustantimes.com",
    "theprint.in", "thewire.in", "scroll.in", "livemint.com",
    "financialexpress.com", "indianexpress.com", "deccanherald.com",
    "telegraphindia.com", "tribuneindia.com", "thestatesman.com",
    "businessstandard.com", "moneycontrol.com", "economictimes.indiatimes.com",
}

# Known aggregator / forum domains
_FORUM_DOMAINS = {
    "quora.com", "reddit.com", "stackexchange.com", "stackoverflow.com",
    "answers.yahoo.com", "topix.com", "disqus.com",
}

# Known aggregator content platforms
_AGGREGATOR_DOMAINS = {
    "wikipedia.org", "wikimedia.org", "en.wikipedia.org",
}

# Blog platforms
_BLOG_PLATFORMS = {
    "blogger.com", "blogspot.com", "wordpress.com", "medium.com",
    "substack.com", "ghost.io",
}

# Official TLD suffixes / patterns
_OFFICIAL_TLDS = (".gov", ".gov.in", ".nic.in", ".edu", ".ac.in", ".ac.uk", ".edu.in")

# Explicitly known official domains
_OFFICIAL_DOMAINS = {
    "india.gov.in", "uidai.gov.in", "nsp.gov.in", "ugc.gov.in",
    "aicte-india.org", "sarkariresult.com",
}


def classify_source(domain: str, url: str) -> str:
    """
    Classify a source domain into one of:
    official, news, aggregator, blog, forum.

    Falls back to 'aggregator' if no rule matches.
    """
    domain_lower = domain.lower().strip()
    url_lower = url.lower()

    # Official: TLD-based
    for tld in _OFFICIAL_TLDS:
        if domain_lower.endswith(tld):
            return "official"

    # Official: explicit list
    if domain_lower in _OFFICIAL_DOMAINS:
        return "official"

    # Forum
    for fd in _FORUM_DOMAINS:
        if domain_lower == fd or domain_lower.endswith("." + fd):
            return "forum"

    # News
    for nd in _NEWS_DOMAINS:
        if domain_lower == nd or domain_lower.endswith("." + nd):
            return "news"

    # Aggregator
    for ag in _AGGREGATOR_DOMAINS:
        if domain_lower == ag or domain_lower.endswith("." + ag):
            return "aggregator"

    # Blog
    for bp in _BLOG_PLATFORMS:
        if domain_lower == bp or domain_lower.endswith("." + bp):
            return "blog"
    # Heuristic: path contains /blog/
    if "/blog/" in url_lower:
        return "blog"

    return "aggregator"
