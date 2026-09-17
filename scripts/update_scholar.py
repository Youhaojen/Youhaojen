#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import unquote

import requests


# ============================================================
# Configuration
# ============================================================

SCHOLAR_ID = "46cZ1-wAAAAJ"
README = Path("README.md")

SERPAPI_URL = "https://serpapi.com/search.json"
CROSSREF_URL = "https://api.crossref.org/works"

# Crossref matching threshold.
# Higher = stricter title matching.
CROSSREF_TITLE_THRESHOLD = 0.88

# Small delay between Crossref requests.
CROSSREF_DELAY = 0.2


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
        "Youhaojen-GitHub-Scholar-Updater/1.0 "
        "(mailto:youhaojen@example.com)"
    )
})


# ============================================================
# Google Scholar Author
# ============================================================

def get_publications():
    """
    Get publications from Google Scholar author profile.
    """

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
    """
    Get detailed Google Scholar citation information
    for one publication.
    """

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
            f"  Warning: citation lookup failed: "
            f"{exc}",
            flush=True,
        )

        return {}


# ============================================================
# Basic utilities
# ============================================================

def get_year(pub):
    """
    Return publication year as integer.
    """

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
    """
    Return citation count as integer.
    """

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
# Title normalization
# ============================================================

def normalize_title(title):
    """
    Normalize a title for Crossref matching.

    This is NOT a title correction.
    It only removes formatting differences.
    """

    if not title:
        return ""

    title = str(title)

    # Unicode normalization.
    title = unicodedata.normalize(
        "NFKD",
        title,
    )

    # Remove combining marks.
    title = "".join(
        char
        for char in title
        if not unicodedata.combining(char)
    )

    title = title.lower()

    # Replace common unicode symbols.
    replacements = {
        "₂": "2",
        "₃": "3",
        "₄": "4",
        "₅": "5",
        "₆": "6",
        "₇": "7",
        "₈": "8",
        "₉": "9",
        "₀": "0",
        "−": "-",
        "–": "-",
        "—": "-",
        "α": "alpha",
        "β": "beta",
        "γ": "gamma",
    }

    for old, new in replacements.items():
        title = title.replace(
            old,
            new,
        )

    # Normalize punctuation to spaces.
    title = re.sub(
        r"[^a-z0-9]+",
        " ",
        title,
    )

    # Collapse whitespace.
    title = " ".join(
        title.split()
    )

    return title


def title_similarity(title_a, title_b):
    """
    Calculate normalized title similarity.
    """

    a = normalize_title(
        title_a
    )

    b = normalize_title(
        title_b
    )

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


# ============================================================
# Title display cleaning
# ============================================================

def clean_title(title):
    """
    Clean common Google Scholar chemical formula formatting.

    No publication-specific title corrections are used.
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
    """
    Detect conference / presentation records.
    """

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
# DOI normalization
# ============================================================

def normalize_doi(value):
    """
    Normalize a DOI string.

    This function does not arbitrarily remove slash-separated
    DOI suffixes because '/' can legitimately occur in DOI
    suffixes.
    """

    if not value:
        return None

    value = unquote(
        str(value)
    ).strip()

    # Remove DOI URL prefix.
    value = re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "",
        value,
        flags=re.IGNORECASE,
    )

    # Remove "doi:" prefix.
    value = re.sub(
        r"^doi:\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = value.strip()

    # Remove URL query / fragment.
    value = value.split(
        "?",
        1,
    )[0]

    value = value.split(
        "#",
        1,
    )[0]

    # Remove trailing punctuation.
    value = value.rstrip(
        ".,;:)]}>\"'"
    )

    # DOI prefix validation.
    if not re.match(
        r"^10\.\d{4,9}/",
        value,
        flags=re.IGNORECASE,
    ):
        return None

    # DOI suffix must not contain whitespace.
    if re.search(
        r"\s",
        value,
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
    """
    Extract DOI-like strings from arbitrary text.
    """

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

    return normalize_doi(
        match.group(1)
    )


# ============================================================
# Recursive Scholar DOI search
# ============================================================

def search_doi_in_object(obj):
    """
    Recursively search a SerpAPI response for DOI.
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

        preferred_keys = [
            "doi",
            "DOI",
            "doi_url",
            "url",
            "link",
            "resource",
        ]

        # Search DOI-related fields first.
        for key in preferred_keys:

            if key not in obj:
                continue

            value = obj[key]

            if isinstance(
                value,
                str,
            ):

                doi = extract_doi_from_text(
                    value
                )

            else:

                doi = search_doi_in_object(
                    value
                )

            if doi:
                return doi

        # Search remaining values.
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
# Crossref author matching
# ============================================================

def get_scholar_authors(pub):
    """
    Extract author surnames from Google Scholar record.
    """

    authors = pub.get(
        "authors",
        "",
    )

    if not authors:
        return []

    # SerpAPI usually returns a string such as:
    #
    # "Hao-Jen You, Hsin Lin, ..."
    #
    # Split conservatively.
    if isinstance(
        authors,
        str,
    ):

        names = [
            x.strip()
            for x in authors.split(",")
            if x.strip()
        ]

    elif isinstance(
        authors,
        list,
    ):

        names = [
            str(x).strip()
            for x in authors
            if str(x).strip()
        ]

    else:

        names = []

    surnames = []

    for name in names:

        parts = name.split()

        if parts:
            surnames.append(
                normalize_title(
                    parts[-1]
                )
            )

    return surnames


def crossref_author_match(
    scholar_authors,
    crossref_authors,
):
    """
    Check whether the first author is reasonably consistent.
    """

    if not scholar_authors:
        return True

    if not crossref_authors:
        return False

    scholar_first = scholar_authors[0]

    crossref_first = normalize_title(
        crossref_authors[0].get(
            "family",
            "",
        )
    )

    if not scholar_first or not crossref_first:
        return False

    return (
        scholar_first == crossref_first
    )


# ============================================================
# Crossref search
# ============================================================

def search_crossref(pub):
    """
    Search Crossref using publication title.

    DOI is accepted only when:
      1. title similarity is sufficiently high
      2. publication year is reasonably consistent
      3. first author is consistent when available
    """

    title = pub.get(
        "title",
        "",
    )

    year = get_year(
        pub
    )

    scholar_authors = get_scholar_authors(
        pub
    )

    if not title:
        return None

    params = {
        "query.title": title,
        "rows": 10,
        "select": (
            "DOI,title,author,published,"
            "published-print,published-online"
        ),
    }

    try:

        response = session.get(
            CROSSREF_URL,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:

        print(
            f"  Crossref search failed: {exc}",
            flush=True,
        )

        return None

    items = (
        data
        .get("message", {})
        .get("items", [])
    )

    if not items:
        return None

    candidates = []

    for item in items:

        crossref_titles = item.get(
            "title",
            [],
        )

        if not crossref_titles:
            continue

        crossref_title = crossref_titles[0]

        similarity = title_similarity(
            title,
            crossref_title,
        )

        # ----------------------------------------------------
        # Year
        # ----------------------------------------------------

        crossref_year = None

        for field in [
            "published",
            "published-print",
            "published-online",
        ]:

            date_parts = (
                item
                .get(field, {})
                .get("date-parts", [])
            )

            if date_parts:

                try:
                    crossref_year = int(
                        date_parts[0][0]
                    )
                    break

                except (
                    TypeError,
                    ValueError,
                    IndexError,
                ):
                    pass

        # ----------------------------------------------------
        # Year compatibility
        # ----------------------------------------------------

        year_ok = True

        if year and crossref_year:

            # Allow online / print publication date
            # differences of up to one year.
            year_ok = (
                abs(
                    year - crossref_year
                ) <= 1
            )

        if not year_ok:
            continue

        # ----------------------------------------------------
        # Author compatibility
        # ----------------------------------------------------

        crossref_authors = item.get(
            "author",
            [],
        )

        author_ok = crossref_author_match(
            scholar_authors,
            crossref_authors,
        )

        if not author_ok:
            continue

        doi = normalize_doi(
            item.get("DOI")
        )

        if not doi:
            continue

        candidates.append(
            (
                similarity,
                doi,
                crossref_title,
                crossref_year,
            )
        )

    if not candidates:
        return None

    # Highest title similarity first.
    candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    best = candidates[0]

    similarity = best[0]
    doi = best[1]
    crossref_title = best[2]
    crossref_year = best[3]

    print(
        "  Crossref candidate:",
        flush=True,
    )

    print(
        f"    Title: {crossref_title}",
        flush=True,
    )

    print(
        f"    Similarity: {similarity:.3f}",
        flush=True,
    )

    print(
        f"    Year: {crossref_year}",
        flush=True,
    )

    print(
        f"    DOI: {doi}",
        flush=True,
    )

    if similarity < CROSSREF_TITLE_THRESHOLD:

        print(
            "  Crossref match rejected "
            f"(similarity < {CROSSREF_TITLE_THRESHOLD})",
            flush=True,
        )

        return None

    return doi


# ============================================================
# Get DOI
# ============================================================

def get_doi(pub):
    """
    DOI lookup pipeline:

        1. Google Scholar citation page
        2. Crossref title/author/year matching
    """

    title = pub.get(
        "title",
        "",
    )

    # --------------------------------------------------------
    # Method 1: Google Scholar
    # --------------------------------------------------------

    doi = None

    citation_id = pub.get(
        "citation_id"
    )

    if citation_id:

        data = get_citation_page(
            citation_id
        )

        if data:

            doi = search_doi_in_object(
                data
            )

    if doi:

        print(
            f"  DOI from Google Scholar: {doi}",
            flush=True,
        )

        return doi

    # --------------------------------------------------------
    # Method 2: Crossref
    # --------------------------------------------------------

    print(
        "  DOI not found in Google Scholar.",
        flush=True,
    )

    print(
        "  Searching Crossref...",
        flush=True,
    )

    doi = search_crossref(
        pub
    )

    if doi:

        print(
            f"  DOI from Crossref: {doi}",
            flush=True,
        )

        return doi

    print(
        f"  DOI NOT FOUND: {title}",
        flush=True,
    )

    return None


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
    # DOI link
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
    """
    Replace content between README markers.
    """

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
    # Fetch Google Scholar
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
    # Filter conference publications
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
    # Get DOI
    # --------------------------------------------------------

    print(
        "\nGetting DOIs...",
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

        # Small delay to avoid unnecessary Crossref load.
        time.sleep(
            CROSSREF_DELAY
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
            pub.get(
                "title",
                "",
            ),
            flush=True,
        )

        print(
            f"  DOI: "
            f"{pub.get('_doi') or 'NOT FOUND'}",
            flush=True,
        )

    print(
        "\n================ Most Cited ================",
        flush=True,
    )

    for pub in most_cited:

        print(
            pub.get(
                "title",
                "",
            ),
            flush=True,
        )

        print(
            f"  DOI: "
            f"{pub.get('_doi') or 'NOT FOUND'}",
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
