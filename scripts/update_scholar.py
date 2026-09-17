#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

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

    return data.get(
        "articles",
        []
    )


# ============================================================
# Google Scholar citation page
# ============================================================

def get_citation_page(citation_id):
    """Get detailed information for one Scholar article."""

    api_key = os.environ.get("SERPAPI_KEY")

    if not api_key:
        raise RuntimeError(
            "SERPAPI_KEY is not set."
        )

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
            f"  Warning: citation lookup failed: {exc}",
            flush=True,
        )

        return {}


# ============================================================
# Basic utilities
# ============================================================

def get_year(pub):
    """Return publication year as integer."""

    try:
        return int(
            pub.get("year") or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0


def get_citations(pub):
    """Return citation count as integer."""

    try:

        value = (
            pub
            .get("cited_by", {})
            .get("value")
        )

        return int(
            value or 0
        )

    except (
        TypeError,
        ValueError,
        AttributeError,
    ):
        return 0


# ============================================================
# Title cleaning
# ============================================================

def clean_title(title):
    """
    Clean common Google Scholar chemical formula formatting.

    No paper-specific title correction is used.
    """

    title = " ".join(
        str(title).split()
    )

    replacements = {

        "PbSnS 2": "PbSnS₂",
        "PbSnS2": "PbSnS₂",

        "Ag 3 XS 3": "Ag₃XS₃",
        "Ag3XS3": "Ag₃XS₃",

        "K 2 Se 2 Te": "K₂Se₂Te",
        "K2Se2Te": "K₂Se₂Te",

        "Sr 2 Si": "Sr₂Si",
        "Sr2Si": "Sr₂Si",

        "Sr 2 Ge": "Sr₂Ge",
        "Sr2Ge": "Sr₂Ge",

        "Ag 2 Se": "Ag₂Se",
        "Ag2Se": "Ag₂Se",

        "CsCuCl 3": "CsCuCl₃",
        "CsCuCl3": "CsCuCl₃",

        "CsCuBr 3": "CsCuBr₃",
        "CsCuBr3": "CsCuBr₃",

        "K 3 SbS 4": "K₃SbS₄",
        "K3SbS4": "K₃SbS₄",

        "K 3 SbTe 3": "K₃SbTe₃",
        "K3SbTe3": "K₃SbTe₃",

        "K 3 BiTe 3": "K₃BiTe₃",
        "K3BiTe3": "K₃BiTe₃",

        "Mg 2 GeO 4": "Mg₂GeO₄",
        "Mg2GeO4": "Mg₂GeO₄",

        "Ca 2 GeO 4": "Ca₂GeO₄",
        "Ca2GeO4": "Ca₂GeO₄",
    }

    for old, new in replacements.items():
        title = title.replace(
            old,
            new,
        )

    return title


# ============================================================
# Conference detection
# ============================================================

def is_conference(pub):
    """Detect conference / presentation records."""

    title = str(
        pub.get(
            "title",
            "",
        )
    )

    publication = str(
        pub.get(
            "publication",
            "",
        )
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
# DOI validation
# ============================================================

DOI_PATTERN = re.compile(
    r"^10\.\d{4,9}/\S+$",
    re.IGNORECASE,
)


def normalize_doi(value):
    """
    Normalize a DOI candidate.

    This function intentionally does NOT assume that every '/'
    after the DOI prefix is invalid, because valid DOI suffixes
    may contain slashes.
    """

    if not value:
        return None

    value = unquote(
        str(value)
    ).strip()

    # Remove common DOI URL prefixes.
    value = re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"^doi:\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )

    # Remove whitespace.
    value = value.strip()

    # Remove trailing punctuation.
    value = value.rstrip(
        ".,;:)]}>\"'"
    )

    # Remove query string / fragment.
    value = value.split(
        "?",
        1,
    )[0]

    value = value.split(
        "#",
        1,
    )[0]

    # DOI must start with 10.xxxx/
    if not re.match(
        r"^10\.\d{4,9}/",
        value,
        re.IGNORECASE,
    ):
        return None

    if not DOI_PATTERN.match(
        value
    ):
        return None

    return value


# ============================================================
# DOI extraction from text
# ============================================================

DOI_REGEX = re.compile(
    r"""
    (?:
        https?://
        (?:dx\.)?doi\.org/
    )?
    (
        10\.\d{4,9}/
        [-._;()/:A-Z0-9]+
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extract_doi_from_text(text):
    """Extract a DOI candidate from arbitrary text."""

    if not text:
        return None

    text = unquote(
        str(text)
    )

    match = DOI_REGEX.search(
        text
    )

    if not match:
        return None

    candidate = match.group(1)

    return normalize_doi(
        candidate
    )


# ============================================================
# URL-specific DOI extraction
# ============================================================

def extract_doi_from_url(url):
    """
    Extract DOI from a URL.

    DOI URLs:
        https://doi.org/10.xxxx/xxxxx

    Publisher URLs are also inspected for embedded DOI.
    """

    if not url:
        return None

    url = unquote(
        str(url)
    ).strip()

    # Direct DOI URL.
    if "doi.org/" in url.lower():

        part = re.split(
            r"doi\.org/",
            url,
            flags=re.IGNORECASE,
        )[1]

        return normalize_doi(
            part
        )

    # Search DOI anywhere inside URL.
    return extract_doi_from_text(
        url
    )


# ============================================================
# Recursive DOI search
# ============================================================

def search_doi_in_object(obj):
    """
    Recursively search a SerpAPI response for a DOI.

    DOI-related fields and URLs are checked first.
    """

    if isinstance(
        obj,
        str,
    ):

        return extract_doi_from_text(
            obj
        )

    if isinstance(
        obj,
        dict,
    ):

        # ----------------------------------------------------
        # DOI-specific fields first
        # ----------------------------------------------------

        preferred_keys = [
            "doi",
            "DOI",
            "doi_url",
            "url",
            "link",
            "resource",
        ]

        for key in preferred_keys:

            if key not in obj:
                continue

            value = obj[key]

            if isinstance(
                value,
                str,
            ):

                doi = extract_doi_from_url(
                    value
                )

            else:

                doi = search_doi_in_object(
                    value
                )

            if doi:
                return doi

        # ----------------------------------------------------
        # Search all remaining values
        # ----------------------------------------------------

        for key, value in obj.items():

            if key in preferred_keys:
                continue

            doi = search_doi_in_object(
                value
            )

            if doi:
                return doi

    elif isinstance(
        obj,
        list,
    ):

        for value in obj:

            doi = search_doi_in_object(
                value
            )

            if doi:
                return doi

    return None


# ============================================================
# Get DOI from Google Scholar
# ============================================================

def get_doi(pub):
    """
    Get DOI from Google Scholar citation page.
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

    doi = search_doi_in_object(
        data
    )

    return doi


# ============================================================
# Format publication
# ============================================================

def format_publication(pub):
    """
    Format publication as Markdown.

    DOI is used when available.

    Google Scholar is NEVER used as a fallback link.
    """

    raw_title = pub.get(
        "title",
        "Unknown title",
    )

    title = clean_title(
        raw_title
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

        title_text = (
            f"[{title}]"
            f"(https://doi.org/{doi})"
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
    """Replace README content between markers."""

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

    # --------------------------------------------------------
    # Fetch Scholar publications
    # --------------------------------------------------------

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
    # Remove conference records
    # --------------------------------------------------------

    journal_publications = []

    print(
        "\nFiltering publications...",
        flush=True,
    )

    for pub in publications:

        title = pub.get(
            "title",
            "",
        )

        if is_conference(pub):

            print(
                f"  Excluding conference: {title}",
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
    # Get DOI for every journal publication
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
                "  DOI: NOT FOUND",
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
    # Most Cited 3
    # --------------------------------------------------------

    most_cited = sorted(
        journal_publications,
        key=get_citations,
        reverse=True,
    )[:3]

    # --------------------------------------------------------
    # Debug output
    # --------------------------------------------------------

    print(
        "\n================ Latest ================",
        flush=True,
    )

    for pub in latest:

        print(
            f"{pub.get('title', '')}",
            flush=True,
        )

        print(
            f"  DOI: {pub.get('_doi') or 'NOT FOUND'}",
            flush=True,
        )

    print(
        "\n================ Most Cited ================",
        flush=True,
    )

    for pub in most_cited:

        print(
            f"{pub.get('title', '')}",
            flush=True,
        )

        print(
            f"  DOI: {pub.get('_doi') or 'NOT FOUND'}",
            flush=True,
        )

    # --------------------------------------------------------
    # Update README
    # --------------------------------------------------------

    print(
        "\nUpdating README...",
        flush=True,
    )

    if not README.exists():

        raise FileNotFoundError(
            f"{README} does not exist."
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


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()
