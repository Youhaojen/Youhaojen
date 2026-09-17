#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path
from urllib.parse import unquote

import requests


# ============================================================
# Configuration
# ============================================================

SCHOLAR_ID = "46cZ1-wAAAAJ"
README = Path("README.md")

SERPAPI_URL = "https://serpapi.com/search.json"


# ============================================================
# Conference filtering
# ============================================================

CONFERENCE_KEYWORDS = [
    "conference",
    "symposium",
    "summit",
    "workshop",
    "meeting",
    "proceedings",
    "abstract",
    "poster",
    "presentation",
]


# ============================================================
# HTTP session
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; Youhaojen-GitHub-Scholar-Updater/1.0)"
    )
})


# ============================================================
# Google Scholar Author
# ============================================================

def get_publications():
    """Get publications from Google Scholar author profile."""

    api_key = os.environ.get("SERPAPI_KEY")

    if not api_key:
        raise RuntimeError(
            "SERPAPI_KEY is not set."
        )

    params = {
        "engine": "google_scholar_author",
        "author_id": SCHOLAR_ID,
        "api_key": api_key,
        "hl": "en",
        "num": 100,
        "sort": "pubdate",
    }

    response = session.get(
        SERPAPI_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(
            f"SerpAPI error: {data['error']}"
        )

    return data.get("articles", [])


# ============================================================
# Google Scholar citation page
# ============================================================

def get_citation_page(citation_id):
    """
    Get Google Scholar citation information for one article.
    """

    api_key = os.environ.get("SERPAPI_KEY")

    params = {
        "engine": "google_scholar_author",
        "author_id": SCHOLAR_ID,
        "view_op": "view_citation",
        "citation_id": citation_id,
        "api_key": api_key,
        "hl": "en",
    }

    try:
        response = session.get(
            SERPAPI_URL,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if "error" in data:
            print(
                f"  Scholar citation error: "
                f"{data['error']}",
                flush=True,
            )
            return {}

        return data

    except Exception as exc:
        print(
            f"  Warning: citation lookup failed: "
            f"{exc}",
            flush=True,
        )
        return {}


# ============================================================
# Basic utilities
# ============================================================

def get_year(pub):
    try:
        return int(pub.get("year") or 0)
    except (TypeError, ValueError):
        return 0


def get_citations(pub):
    try:
        value = (
            pub
            .get("cited_by", {})
            .get("value")
        )
        return int(value or 0)
    except (
        TypeError,
        ValueError,
        AttributeError,
    ):
        return 0


# ============================================================
# Conference detection
# ============================================================

def is_conference(pub):
    title = str(
        pub.get("title", "")
    )

    publication = str(
        pub.get("publication", "")
    )

    text = (
        f"{title} {publication}"
        .lower()
    )

    return any(
        keyword in text
        for keyword in CONFERENCE_KEYWORDS
    )


# ============================================================
# DOI extraction
# ============================================================

DOI_REGEX = re.compile(
    r"""
    (?:
        https?://
        (?:dx\.)?doi\.org/
    )?
    (10\.\d{4,9}/[-._;()/:A-Z0-9]+)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extract_doi_from_text(text):
    if not text:
        return None

    text = unquote(
        str(text)
    )

    match = DOI_REGEX.search(text)

    if not match:
        return None

    doi = match.group(1)

    return doi.rstrip(
        ".,;:)]}>\"'"
    )


def search_doi_in_object(obj):
    """
    Recursively search the SerpAPI response
    for a DOI.
    """

    if isinstance(obj, str):
        return extract_doi_from_text(obj)

    if isinstance(obj, dict):
        for value in obj.values():
            doi = search_doi_in_object(value)

            if doi:
                return doi

    elif isinstance(obj, list):
        for value in obj:
            doi = search_doi_in_object(value)

            if doi:
                return doi

    return None


# ============================================================
# Get DOI from Google Scholar
# ============================================================

def get_doi(pub):
    """
    Get DOI from the Google Scholar citation page.
    """

    citation_id = pub.get(
        "citation_id"
    )

    if not citation_id:
        return None

    data = get_citation_page(
        citation_id
    )

    if not data:
        return None

    return search_doi_in_object(
        data
    )


# ============================================================
# Format publication
# ============================================================

def format_publication(pub):

    title = pub.get(
        "title",
        "Unknown title",
    )

    publication = " ".join(
        str(
            pub.get(
                "publication",
                "",
            )
        ).split()
    )

    citations = get_citations(
        pub
    )

    doi = pub.get(
        "_doi"
    )

    # --------------------------------------------------------
    # Link
    # --------------------------------------------------------

    if doi:
        link = (
            f"https://doi.org/{doi}"
        )
    else:
        link = pub.get(
            "link",
            "",
        )

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    if link:
        title_text = (
            f"[{title}]({link})"
        )
    else:
        title_text = (
            f"**{title}**"
        )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    details = []

    if publication:
        details.append(
            publication
        )

    details.append(
        f"{citations} citations"
    )

    return (
        f"- {title_text}  \n"
        f"  *{' · '.join(details)}*"
    )


# ============================================================
# README updater
# ============================================================

def update_section(
    readme,
    start_marker,
    end_marker,
    publications,
):

    pattern = (
        re.escape(start_marker)
        + r".*?"
        + re.escape(end_marker)
    )

    content = "\n".join(
        format_publication(pub)
        for pub in publications
    )

    replacement = (
        f"{start_marker}\n"
        f"{content}\n"
        f"{end_marker}"
    )

    return re.sub(
        pattern,
        replacement,
        readme,
        flags=re.DOTALL,
    )


# ============================================================
# Main
# ============================================================

def main():

    print(
        "Fetching Google Scholar...",
        flush=True,
    )

    publications = get_publications()

    print(
        f"Found {len(publications)} publications",
        flush=True,
    )

    # --------------------------------------------------------
    # Filter conference publications
    # --------------------------------------------------------

    journal_publications = []

    print(
        "\nFiltering publications...",
        flush=True,
    )

    for pub in publications:

        if is_conference(pub):

            print(
                f"  Excluding conference: "
                f"{pub.get('title', '')}",
                flush=True,
            )

            continue

        journal_publications.append(
            pub
        )

    print(
        f"Journal publications: "
        f"{len(journal_publications)}",
        flush=True,
    )

    # --------------------------------------------------------
    # Get DOI from Google Scholar
    # --------------------------------------------------------

    print(
        "\nGetting DOIs from Google Scholar...",
        flush=True,
    )

    for pub in journal_publications:

        title = pub.get(
            "title",
            "",
        )

        print(
            f"\n  {title}",
            flush=True,
        )

        doi = get_doi(
            pub
        )

        pub["_doi"] = doi

        if doi:

            print(
                f"  DOI: {doi}",
                flush=True,
            )

        else:

            print(
                "  DOI: not found",
                flush=True,
            )

    # --------------------------------------------------------
    # Latest 3
    # --------------------------------------------------------

    latest = sorted(
        journal_publications,
        key=get_year,
        reverse=True,
    )[:3]

    # --------------------------------------------------------
    # Most cited 3
    # --------------------------------------------------------

    most_cited = sorted(
        journal_publications,
        key=get_citations,
        reverse=True,
    )[:3]

    # --------------------------------------------------------
    # Update README
    # --------------------------------------------------------

    print(
        "\nUpdating README...",
        flush=True,
    )

    readme = README.read_text(
        encoding="utf-8"
    )

    readme = update_section(
        readme,
        "<!-- SCHOLAR-LATEST:START -->",
        "<!-- SCHOLAR-LATEST:END -->",
        latest,
    )

    readme = update_section(
        readme,
        "<!-- SCHOLAR-CITED:START -->",
        "<!-- SCHOLAR-CITED:END -->",
        most_cited,
    )

    README.write_text(
        readme,
        encoding="utf-8",
    )

    print(
        "\nREADME updated successfully.",
        flush=True,
    )


if __name__ == "__main__":
    main()
