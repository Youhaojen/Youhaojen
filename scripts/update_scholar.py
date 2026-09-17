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

CROSSREF_TITLE_THRESHOLD = 0.88
CROSSREF_DELAY = 0.2

LATEST_N = 3
MOST_CITED_N = 3


# ============================================================
# HTTP session
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140.0 Safari/537.36"
        )
    }
)


# ============================================================
# Conference filtering
# ============================================================

CONFERENCE_KEYWORDS = [
    "conference",
    "symposium",
    "workshop",
    "meeting",
    "proceedings",
    "summit",
    "international conference",
    "conference proceedings",
    "conference paper",
]


def is_conference(pub):
    """
    Detect conference / symposium / workshop papers.
    """

    text_parts = [
        pub.get("title", ""),
        pub.get("publication", ""),
        pub.get("snippet", ""),
    ]

    text = " ".join(text_parts).lower()

    return any(
        keyword in text
        for keyword in CONFERENCE_KEYWORDS
    )


# ============================================================
# Google Scholar
# ============================================================

def get_publications():
    api_key = os.environ.get("SERPAPI_KEY")

    if not api_key:
        raise RuntimeError(
            "SERPAPI_KEY is not set."
        )

    params = {
        "engine": "google_scholar_author",
        "author_id": SCHOLAR_ID,
        "hl": "en",
        "api_key": api_key,
    }

    response = session.get(
        SERPAPI_URL,
        params=params,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    publications = data.get(
        "articles",
        []
    )

    print(
        f"Google Scholar publications: "
        f"{len(publications)}"
    )

    return publications


def get_citation_page(citation_id):
    """
    Retrieve Google Scholar citation page
    through SerpAPI.
    """

    api_key = os.environ.get(
        "SERPAPI_KEY"
    )

    if not api_key or not citation_id:
        return {}

    params = {
        "engine": "google_scholar",
        "view_op": "view_citation",
        "citation_id": citation_id,
        "hl": "en",
        "api_key": api_key,
    }

    try:

        response = session.get(
            SERPAPI_URL,
            params=params,
            timeout=60,
        )

        response.raise_for_status()

        return response.json()

    except Exception as exc:

        print(
            f"  Scholar citation page failed: "
            f"{type(exc).__name__}: {exc}"
        )

        return {}


# ============================================================
# Basic publication information
# ============================================================

def get_year(pub):
    year = pub.get("year")

    try:
        return int(year)
    except (TypeError, ValueError):
        return 0


def get_citations(pub):
    cited_by = pub.get(
        "cited_by",
        {}
    )

    if isinstance(
        cited_by,
        dict
    ):
        value = cited_by.get(
            "value",
            0
        )
    else:
        value = 0

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ============================================================
# MathML / XML cleanup
# ============================================================

def clean_mathml(title):
    """
    Convert common MathML/XML fragments
    into normal readable text.

    Example:

        <mml:msub>
            <mml:mi>h</mml:mi>
            <mml:mn>2</mml:mn>
        </mml:msub>

    becomes:

        h₂
    """

    if not title:
        return title

    # --------------------------------------------------------
    # Decode common HTML entities
    # --------------------------------------------------------

    title = title.replace(
        "&lt;",
        "<"
    )

    title = title.replace(
        "&gt;",
        ">"
    )

    title = title.replace(
        "&quot;",
        '"'
    )

    title = title.replace(
        "&#34;",
        '"'
    )

    title = title.replace(
        "&amp;",
        "&"
    )

    # --------------------------------------------------------
    # Subscript / superscript tables
    # --------------------------------------------------------

    subscript_table = str.maketrans(
        "0123456789",
        "₀₁₂₃₄₅₆₇₈₉"
    )

    superscript_table = str.maketrans(
        "0123456789",
        "⁰¹²³⁴⁵⁶⁷⁸⁹"
    )

    # --------------------------------------------------------
    # MathML msub
    #
    # <msub><mi>h</mi><mn>2</mn></msub>
    # -> h₂
    # --------------------------------------------------------

    title = re.sub(
        r"<(?:mml:)?msub>\s*"
        r"<(?:mml:)?mi[^>]*>\s*(.*?)\s*"
        r"</(?:mml:)?mi>\s*"
        r"<(?:mml:)?mn[^>]*>\s*(.*?)\s*"
        r"</(?:mml:)?mn>\s*"
        r"</(?:mml:)?msub>",
        lambda m: (
            m.group(1).strip()
            + m.group(2).strip().translate(
                subscript_table
            )
        ),
        title,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # --------------------------------------------------------
    # MathML msup
    #
    # <msup><mi>x</mi><mn>2</mn></msup>
    # -> x²
    # --------------------------------------------------------

    title = re.sub(
        r"<(?:mml:)?msup>\s*"
        r"<(?:mml:)?mi[^>]*>\s*(.*?)\s*"
        r"</(?:mml:)?mi>\s*"
        r"<(?:mml:)?mn[^>]*>\s*(.*?)\s*"
        r"</(?:mml:)?mn>\s*"
        r"</(?:mml:)?msup>",
        lambda m: (
            m.group(1).strip()
            + m.group(2).strip().translate(
                superscript_table
            )
        ),
        title,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # --------------------------------------------------------
    # Remove remaining XML / MathML tags
    # --------------------------------------------------------

    title = re.sub(
        r"<[^>]+>",
        "",
        title,
        flags=re.DOTALL,
    )

    # --------------------------------------------------------
    # Remove escaped MathML namespace
    # --------------------------------------------------------

    title = re.sub(
        r"mml\\:",
        "",
        title,
        flags=re.IGNORECASE,
    )

    title = re.sub(
        r"xmlns\\:mml\s*=\s*\"[^\"]*\"",
        "",
        title,
        flags=re.IGNORECASE,
    )

    title = re.sub(
        r"mathvariant\s*=\s*\"[^\"]*\"",
        "",
        title,
        flags=re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Remove remaining MathML element names
    # --------------------------------------------------------

    title = re.sub(
        r"\b(?:"
        r"math|"
        r"mrow|"
        r"mi|"
        r"mo|"
        r"mn|"
        r"msub|"
        r"msup|"
        r"mfrac|"
        r"mtext"
        r")\b",
        "",
        title,
        flags=re.IGNORECASE,
    )

    # Remove stray backslashes
    title = title.replace(
        "\\",
        ""
    )

    return title


# ============================================================
# Title normalization
# ============================================================

def normalize_title(title):
    """
    Normalize title for similarity comparison.
    """

    if not title:
        return ""

    title = clean_mathml(
        title
    )

    title = unicodedata.normalize(
        "NFKC",
        title
    )

    subscript_map = str.maketrans(
        "₀₁₂₃₄₅₆₇₈₉",
        "0123456789"
    )

    superscript_map = str.maketrans(
        "⁰¹²³⁴⁵⁶⁷⁸⁹",
        "0123456789"
    )

    title = title.translate(
        subscript_map
    )

    title = title.translate(
        superscript_map
    )

    title = re.sub(
        r"[^a-zA-Z0-9]+",
        " ",
        title,
    )

    title = title.lower()

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip()


def title_similarity(title1, title2):
    a = normalize_title(
        title1
    )

    b = normalize_title(
        title2
    )

    if not a or not b:
        return 0.0

    return SequenceMatcher(
        None,
        a,
        b,
    ).ratio()


# ============================================================
# Display title cleanup
# ============================================================

def clean_title(title):
    if not title:
        return title

    # --------------------------------------------------------
    # MathML / XML
    # --------------------------------------------------------

    title = clean_mathml(
        title
    )

    # --------------------------------------------------------
    # Unicode normalization
    # --------------------------------------------------------

    title = unicodedata.normalize(
        "NFKC",
        title
    )

    # Remove invisible Unicode characters
    title = re.sub(
        r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]",
        "",
        title,
    )

    # --------------------------------------------------------
    # Chemical formula subscripts
    # --------------------------------------------------------

    sub_map = str.maketrans(
        "0123456789",
        "₀₁₂₃₄₅₆₇₈₉"
    )

    formulas = [
        "PbSnS2",
        "Ag3XS3",
        "K2Se2Te",
        "Sr2Si",
        "Sr2Ge",
        "Ag2Se",
        "CsCuCl3",
        "CsCuBr3",
        "K3SbS4",
        "K3SbTe3",
        "K3BiTe3",
        "Mg2GeO4",
        "Ca2GeO4",
    ]

    for formula in formulas:

        converted = re.sub(
            r"([A-Za-z]+)(\d+)",
            lambda m: (
                m.group(1)
                + m.group(2).translate(
                    sub_map
                )
            ),
            formula,
        )

        title = title.replace(
            formula,
            converted,
        )

    # --------------------------------------------------------
    # Generic spacing before chemical subscripts
    #
    # Example:
    # PbSnS 2 -> PbSnS₂
    # --------------------------------------------------------

    title = re.sub(
        r"\b(PbSnS|Ag3XS|K2Se2Te|Sr2Si|"
        r"Sr2Ge|Ag2Se)\s+([0-9])\b",
        lambda m: (
            m.group(1)
            + m.group(2).translate(
                sub_map
            )
        ),
        title,
    )

    # --------------------------------------------------------
    # Normalize whitespace
    # --------------------------------------------------------

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    # Remove spaces before punctuation
    title = re.sub(
        r"\s+([,;:)])",
        r"\1",
        title,
    )

    # Remove spaces after "("
    title = re.sub(
        r"\(\s+",
        "(",
        title,
    )

    return title.strip()


# ============================================================
# DOI handling
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


def normalize_doi(value):
    """
    Normalize DOI.

    Important:
    Do NOT remove arbitrary DOI suffixes here.
    Canonical DOI verification is handled by Crossref.
    """

    if not value:
        return None

    value = unquote(
        str(value)
    ).strip()

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

    value = value.split(
        "?",
        1
    )[0]

    value = value.split(
        "#",
        1
    )[0]

    value = value.rstrip(
        ".,;:)]}>\"'"
    )

    if not re.match(
        r"^10\.\d{4,9}/",
        value,
        flags=re.IGNORECASE,
    ):
        return None

    if re.search(
        r"\s",
        value,
    ):
        return None

    return value


def extract_doi_from_text(text):
    if not text:
        return None

    match = DOI_REGEX.search(
        str(text)
    )

    if not match:
        return None

    return normalize_doi(
        match.group(1)
    )


# ============================================================
# Recursive DOI search
# ============================================================

def search_doi_in_object(obj):
    """
    Recursively search SerpAPI JSON
    for DOI-related fields.
    """

    preferred_keys = {
        "doi",
        "DOI",
        "doi_url",
        "url",
        "link",
        "resource",
    }

    if isinstance(
        obj,
        dict,
    ):

        # Search DOI-related fields first
        for key, value in obj.items():

            if key in preferred_keys:

                if isinstance(
                    value,
                    str,
                ):

                    doi = extract_doi_from_text(
                        value
                    )

                    if doi:
                        return doi

        # Search nested objects
        for value in obj.values():

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

    elif isinstance(
        obj,
        str,
    ):

        return extract_doi_from_text(
            obj
        )

    return None


# ============================================================
# Scholar author handling
# ============================================================

def get_scholar_authors(pub):

    authors = pub.get(
        "authors",
        []
    )

    if isinstance(
        authors,
        str,
    ):
        authors = [authors]

    result = []

    for author in authors:

        if isinstance(
            author,
            dict,
        ):
            name = author.get(
                "name",
                ""
            )
        else:
            name = str(author)

        name = name.strip()

        if not name:
            continue

        surname = name.split()[-1]

        result.append(
            surname.lower()
        )

    return result


def crossref_author_match(
    pub,
    metadata,
):
    """
    Compare Scholar first author
    with Crossref first author.
    """

    scholar_authors = get_scholar_authors(
        pub
    )

    if not scholar_authors:
        return True

    scholar_first = scholar_authors[0]

    authors = metadata.get(
        "author",
        []
    )

    if not authors:
        return True

    first_author = authors[0]

    family = first_author.get(
        "family",
        ""
    ).lower()

    if not family:
        return True

    return (
        scholar_first == family
        or scholar_first in family
        or family in scholar_first
    )


# ============================================================
# Crossref metadata
# ============================================================

def get_crossref_metadata(doi):
    """
    Retrieve Crossref metadata for a DOI.

    Important:
    The slash in the DOI is preserved.
    """

    if not doi:
        return None

    url = (
        CROSSREF_URL
        + "/"
        + requests.utils.quote(
            doi,
            safe="/",
        )
    )

    try:

        response = session.get(
            url,
            timeout=60,
        )

        if response.status_code != 200:

            print(
                f"  Crossref metadata failed "
                f"({response.status_code}): "
                f"{doi}"
            )

            return None

        data = response.json()

        return data.get(
            "message"
        )

    except Exception as exc:

        print(
            f"  Crossref metadata error: "
            f"{type(exc).__name__}: {exc}"
        )

        return None


# ============================================================
# Crossref title search
# ============================================================

def search_crossref(pub):
    """
    Search Crossref by title.

    Validation:
      - title similarity
      - publication year
      - first author
    """

    title = pub.get(
        "title",
        ""
    ).strip()

    if not title:
        return None

    year = get_year(
        pub
    )

    params = {
        "query.title": title,
        "rows": 10,
        "select": (
            "DOI,title,author,"
            "published,published-print,"
            "published-online"
        ),
    }

    try:

        response = session.get(
            CROSSREF_URL,
            params=params,
            timeout=60,
        )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:

        print(
            f"  Crossref search failed: "
            f"{type(exc).__name__}: {exc}"
        )

        return None

    items = (
        data.get(
            "message",
            {}
        ).get(
            "items",
            []
        )
    )

    best = None

    for item in items:

        doi = normalize_doi(
            item.get(
                "DOI"
            )
        )

        if not doi:
            continue

        crossref_titles = item.get(
            "title",
            []
        )

        if not crossref_titles:
            continue

        crossref_title = crossref_titles[0]

        similarity = title_similarity(
            title,
            crossref_title,
        )

        if similarity < CROSSREF_TITLE_THRESHOLD:
            continue

        # ----------------------------------------------------
        # Year check
        # ----------------------------------------------------

        crossref_year = None

        for field in (
            "published",
            "published-print",
            "published-online",
        ):

            date_info = item.get(
                field
            )

            if not date_info:
                continue

            parts = date_info.get(
                "date-parts",
                []
            )

            if parts and parts[0]:

                crossref_year = parts[0][0]

                break

        if (
            year
            and crossref_year
            and abs(
                year - crossref_year
            ) > 1
        ):
            continue

        # ----------------------------------------------------
        # Author check
        # ----------------------------------------------------

        if not crossref_author_match(
            pub,
            item,
        ):
            continue

        candidate = {
            "doi": doi,
            "title": crossref_title,
            "similarity": similarity,
            "metadata": item,
        }

        if (
            best is None
            or similarity > best["similarity"]
        ):
            best = candidate

    if best:

        print(
            f"  Crossref match: "
            f"{best['doi']} "
            f"(similarity="
            f"{best['similarity']:.3f})"
        )

        return best

    print(
        "  Crossref: no reliable match"
    )

    return None


# ============================================================
# DOI resolution
# ============================================================

def get_doi(pub):
    """
    DOI resolution:

    1. Google Scholar citation page
    2. Validate Scholar DOI through Crossref
    3. Crossref title search

    This automatically fixes malformed DOI
    candidates such as:

        10.1039/d6ta01797e/1267418

    if Crossref identifies the canonical DOI as:

        10.1039/d6ta01797e
    """

    title = pub.get(
        "title",
        ""
    )

    print()
    print(
        f"DOI lookup: {title}"
    )

    # --------------------------------------------------------
    # 1. Google Scholar
    # --------------------------------------------------------

    citation_id = pub.get(
        "citation_id"
    )

    scholar_doi = None

    if citation_id:

        citation_data = get_citation_page(
            citation_id
        )

        scholar_doi = search_doi_in_object(
            citation_data
        )

        if scholar_doi:

            print(
                f"  Scholar DOI candidate: "
                f"{scholar_doi}"
            )

    # --------------------------------------------------------
    # 2. Verify Scholar DOI through Crossref
    # --------------------------------------------------------

    if scholar_doi:

        metadata = get_crossref_metadata(
            scholar_doi
        )

        if metadata:

            canonical_doi = normalize_doi(
                metadata.get(
                    "DOI"
                )
            )

            if canonical_doi:

                print(
                    f"  Crossref verified DOI: "
                    f"{canonical_doi}"
                )

                return canonical_doi

        print(
            "  Scholar DOI could not be "
            "verified by Crossref."
        )

    # --------------------------------------------------------
    # 3. Crossref title search
    # --------------------------------------------------------

    result = search_crossref(
        pub
    )

    if result:

        doi = normalize_doi(
            result.get(
                "doi"
            )
        )

        if doi:

            print(
                f"  Crossref title DOI: "
                f"{doi}"
            )

            return doi

    print(
        "  DOI not found."
    )

    return None


# ============================================================
# Best title
# ============================================================

def get_best_title(
    pub,
    doi,
):
    """
    Select the best title.

    Crossref title is preferred when:
      - similarity is sufficiently high
      - Scholar title contains MathML/XML corruption
    """

    scholar_title = pub.get(
        "title",
        ""
    ).strip()

    if not scholar_title:
        return scholar_title

    # --------------------------------------------------------
    # No DOI
    # --------------------------------------------------------

    if not doi:

        return clean_title(
            scholar_title
        )

    # --------------------------------------------------------
    # Crossref metadata
    # --------------------------------------------------------

    metadata = get_crossref_metadata(
        doi
    )

    if not metadata:

        return clean_title(
            scholar_title
        )

    crossref_titles = metadata.get(
        "title",
        []
    )

    if not crossref_titles:

        return clean_title(
            scholar_title
        )

    crossref_title = crossref_titles[0]

    similarity = title_similarity(
        scholar_title,
        crossref_title,
    )

    # --------------------------------------------------------
    # Crossref title is sufficiently similar
    # --------------------------------------------------------

    if similarity >= 0.60:

        return clean_title(
            crossref_title
        )

    # --------------------------------------------------------
    # Scholar title contains MathML/XML corruption
    # --------------------------------------------------------

    malformed_patterns = [
        r"<mml:",
        r"</mml:",
        r"mml\\:",
        r"xmlns:mml",
        r"xmlns\\:mml",
        r"<math",
        r"</math",
        r"\bmml:math\b",
        r"\bmml:mrow\b",
        r"\bmml:mi\b",
        r"\bmml:msub\b",
    ]

    if any(
        re.search(
            pattern,
            scholar_title,
            flags=re.IGNORECASE,
        )
        for pattern in malformed_patterns
    ):

        return clean_title(
            crossref_title
        )

    # --------------------------------------------------------
    # Otherwise use Scholar title
    # --------------------------------------------------------

    return clean_title(
        scholar_title
    )


# ============================================================
# Markdown formatting
# ============================================================

def format_publication(pub):

    doi = pub.get(
        "_doi"
    )

    title = get_best_title(
        pub,
        doi,
    )

    year = get_year(
        pub
    )

    citations = get_citations(
        pub
    )

    publication = pub.get(
        "publication",
        ""
    ).strip()

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    if doi:

        title_text = (
            f"[{title}]"
            f"(https://doi.org/{doi})"
        )

    else:

        # No Google Scholar fallback
        title_text = (
            f"**{title}**"
        )

    # --------------------------------------------------------
    # Publication metadata
    # --------------------------------------------------------

    metadata = []

    if publication:
        metadata.append(
            publication
        )

    if year:
        metadata.append(
            str(year)
        )

    metadata_text = ", ".join(
        metadata
    )

    metadata_text += (
        f" · {citations} citations"
    )

    return (
        f"- {title_text}\n"
        f"  *{metadata_text}*"
    )


# ============================================================
# README section update
# ============================================================

def update_section(
    readme_text,
    section_name,
    content,
):

    start_marker = (
        f"<!-- SCHOLAR-{section_name}:START -->"
    )

    end_marker = (
        f"<!-- SCHOLAR-{section_name}:END -->"
    )

    pattern = (
        re.escape(start_marker)
        + r".*?"
        + re.escape(end_marker)
    )

    replacement = (
        start_marker
        + "\n"
        + content
        + "\n"
        + end_marker
    )

    new_text, count = re.subn(
        pattern,
        replacement,
        readme_text,
        flags=re.DOTALL,
    )

    if count == 0:

        raise RuntimeError(
            f"README markers not found "
            f"for section: {section_name}"
        )

    return new_text


# ============================================================
# Main
# ============================================================

def main():

    # --------------------------------------------------------
    # README
    # --------------------------------------------------------

    if not README.exists():

        raise FileNotFoundError(
            f"{README} not found."
        )

    readme_text = README.read_text(
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Google Scholar
    # --------------------------------------------------------

    publications = get_publications()

    # --------------------------------------------------------
    # Filter conferences
    # --------------------------------------------------------

    journal_publications = []

    for pub in publications:

        title = pub.get(
            "title",
            ""
        )

        if is_conference(pub):

            print(
                f"Excluded conference: "
                f"{title}"
            )

            continue

        journal_publications.append(
            pub
        )

    print()
    print(
        f"Journal publications: "
        f"{len(journal_publications)}"
    )

    # --------------------------------------------------------
    # DOI resolution
    # --------------------------------------------------------

    for pub in journal_publications:

        doi = get_doi(
            pub
        )

        pub["_doi"] = doi

        if doi:

            print(
                f"  Final DOI: {doi}"
            )

        else:

            print(
                "  Final DOI: not found"
            )

        time.sleep(
            CROSSREF_DELAY
        )

    # --------------------------------------------------------
    # Latest
    # --------------------------------------------------------

    latest = sorted(
        journal_publications,
        key=lambda p: (
            get_year(p),
            get_citations(p),
        ),
        reverse=True,
    )[:LATEST_N]

    # --------------------------------------------------------
    # Most cited
    # --------------------------------------------------------

    most_cited = sorted(
        journal_publications,
        key=lambda p: (
            get_citations(p),
            get_year(p),
        ),
        reverse=True,
    )[:MOST_CITED_N]

    # --------------------------------------------------------
    # Format
    # --------------------------------------------------------

    latest_text = "\n".join(
        format_publication(pub)
        for pub in latest
    )

    cited_text = "\n".join(
        format_publication(pub)
        for pub in most_cited
    )

    # --------------------------------------------------------
    # Update README
    # --------------------------------------------------------

    readme_text = update_section(
        readme_text,
        "LATEST",
        latest_text,
    )

    readme_text = update_section(
        readme_text,
        "CITED",
        cited_text,
    )

    README.write_text(
        readme_text,
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Debug
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("Latest")
    print("=" * 70)

    for pub in latest:

        print(
            clean_title(
                pub.get(
                    "title",
                    ""
                )
            )
        )

        print(
            f"  DOI: "
            f"{pub.get('_doi')}"
        )

    print()
    print("=" * 70)
    print("Most Cited")
    print("=" * 70)

    for pub in most_cited:

        print(
            clean_title(
                pub.get(
                    "title",
                    ""
                )
            )
        )

        print(
            f"  DOI: "
            f"{pub.get('_doi')}"
        )

    print()
    print(
        "README updated successfully."
    )


if __name__ == "__main__":
    main()
