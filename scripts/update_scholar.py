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

CROSSREF_TITLE_THRESHOLD = 0.70
CROSSREF_DELAY = 0.2

LATEST_N = 3
MOST_CITED_N = 3

SUBSCRIPT_DIGITS = str.maketrans(
    "0123456789",
    "₀₁₂₃₄₅₆₇₈₉"
)

SUPERSCRIPT_DIGITS = str.maketrans(
    "0123456789",
    "⁰¹²³⁴⁵⁶⁷⁸⁹"
)


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
# Google Scholar author search
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


# ============================================================
# Basic publication information
# ============================================================

def get_year(pub):
    try:
        return int(
            pub.get(
                "year",
                0
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def get_citations(pub):
    cited_by = pub.get(
        "cited_by",
        {}
    )

    if isinstance(
        cited_by,
        dict,
    ):
        value = cited_by.get(
            "value",
            0
        )
    else:
        value = 0

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0


# ============================================================
# MathML cleanup
# ============================================================

def clean_mathml(title):

    if not title:
        return title

    # HTML entities
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

    subscript_table = str.maketrans(
        "0123456789",
        "₀₁₂₃₄₅₆₇₈₉"
    )

    superscript_table = str.maketrans(
        "0123456789",
        "⁰¹²³⁴⁵⁶⁷⁸⁹"
    )

    # --------------------------------------------------------
    # msub / msup (generalized)
    #
    # Rather than requiring the exact two-child pattern
    # <mi>base</mi><mn>number</mn>, strip whatever tags are
    # nested inside <msub>/<msup> and treat the trailing run
    # of digits as the subscript/superscript number. This
    # also handles a grouped base such as <mrow>(Ag,Cu)</mrow>.
    # --------------------------------------------------------

    def _mathml_script(match, digit_table):

        inner = re.sub(
            r"<[^>]+>",
            "",
            match.group(1),
            flags=re.DOTALL,
        ).strip()

        digit_match = re.search(
            r"(\d+)\s*$",
            inner,
        )

        if not digit_match:
            return inner

        base = inner[:digit_match.start()].strip()

        return base + digit_match.group(1).translate(
            digit_table
        )

    title = re.sub(
        r"<(?:mml:)?msub>\s*(.*?)\s*</(?:mml:)?msub>",
        lambda m: _mathml_script(m, subscript_table),
        title,
        flags=re.IGNORECASE | re.DOTALL,
    )

    title = re.sub(
        r"<(?:mml:)?msup>\s*(.*?)\s*</(?:mml:)?msup>",
        lambda m: _mathml_script(m, superscript_table),
        title,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # --------------------------------------------------------
    # Plain HTML <sub>/<sup> tags
    #
    # Crossref titles commonly carry simple HTML-style
    # subscript/superscript tags (e.g. "Sr<sub>2</sub>Si")
    # rather than full presentation MathML. These were
    # previously left for the generic tag stripper below,
    # which dropped the tags but left the digits as plain
    # text (no subscript conversion).
    # --------------------------------------------------------

    title = re.sub(
        r"<sub>(.*?)</sub>",
        lambda m: m.group(1).translate(subscript_table),
        title,
        flags=re.IGNORECASE | re.DOTALL,
    )

    title = re.sub(
        r"<sup>(.*?)</sup>",
        lambda m: m.group(1).translate(superscript_table),
        title,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # --------------------------------------------------------
    # Remove XML tags
    # --------------------------------------------------------

    title = re.sub(
        r"<[^>]+>",
        "",
        title,
        flags=re.DOTALL,
    )

    # --------------------------------------------------------
    # Remove escaped namespace
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
    # NOTE: an earlier version of this function also removed
    # any standalone occurrence of the words "math", "mrow",
    # "mi", "mo", "mn", "msub", "msup", "mfrac", "mtext"
    # anywhere in the title, to mop up leftover MathML element
    # names. That regex has no way to tell a leftover tag name
    # apart from a real word/element symbol that happens to
    # match one of those tokens -- in particular it silently
    # deleted the chemical symbols "Mo" (molybdenum) and "Mn"
    # (manganese) whenever they appeared on their own. The tag
    # stripper above already removes actual tags, so this
    # extra step was removed rather than made "smarter".
    # --------------------------------------------------------

    title = title.replace(
        "\\",
        ""
    )

    return title


# ============================================================
# Title cleanup
# ============================================================

def clean_title(title):

    if not title:
        return title

    title = clean_mathml(
        title
    )

    title = unicodedata.normalize(
        "NFKC",
        title
    )

    # Remove invisible characters
    title = re.sub(
        r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]",
        "",
        title,
    )

    sub_map = SUBSCRIPT_DIGITS

    # --------------------------------------------------------
    # Chemical-formula subscripting (general rule, not a
    # hand-maintained list of known formulas)
    #
    # A "formula run" here is two or more consecutive
    # element-like tokens: an uppercase letter, optionally one
    # lowercase letter, optionally 1-2 digits -- e.g. "Sr2Si",
    # "K2Se2Te", "PbSnS2". We only subscript a run if at least
    # one of its tokens contains a lowercase letter, which real
    # two-letter element symbols almost always do (Sr, Se, Te,
    # Pb, Sn, Mg, Ca, Cs, Cu, ...). That keeps the rule from
    # firing on unrelated all-caps-plus-number text (e.g. an
    # acronym followed by a year) that isn't a formula at all.
    # New formulas in future papers are picked up automatically
    # -- nothing to add to a list by hand.
    # --------------------------------------------------------

    def _subscript_formula_run(match):

        run = match.group(0)

        if not any(c.islower() for c in run):
            return run

        return re.sub(
            r"([A-Z][a-z]?)(\d{1,2})",
            lambda m:
                m.group(1)
                + m.group(2).translate(sub_map),
            run,
        )

    title = re.sub(
        r"(?:[A-Z][a-z]?\d{0,2}){2,}",
        _subscript_formula_run,
        title,
    )

    # Same idea for a formula with a stray space before its
    # trailing subscript number (a spacing quirk sometimes
    # introduced upstream), e.g. "PbSnS 2" -> "PbSnS₂".

    def _subscript_spaced_formula(match):

        letters, digits = match.group(1), match.group(2)

        if not any(c.islower() for c in letters):
            return match.group(0)

        return letters + digits.translate(sub_map)

    title = re.sub(
        r"\b((?:[A-Z][a-z]?){2,})\s+([0-9]{1,2})\b",
        _subscript_spaced_formula,
        title,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    title = re.sub(
        r"\s+([,;:)])",
        r"\1",
        title,
    )

    title = re.sub(
        r"\(\s+",
        "(",
        title,
    )

    return title.strip()


# ============================================================
# Title normalization
# ============================================================

def normalize_title(title):

    if not title:
        return ""

    title = clean_mathml(
        title
    )

    title = unicodedata.normalize(
        "NFKC",
        title
    )

    sub_map = str.maketrans(
        "₀₁₂₃₄₅₆₇₈₉",
        "0123456789"
    )

    super_map = str.maketrans(
        "⁰¹²³⁴⁵⁶⁷⁸⁹",
        "0123456789"
    )

    title = title.translate(
        sub_map
    )

    title = title.translate(
        super_map
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


def title_similarity(
    title1,
    title2,
):
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
# Recursive DOI extraction
# ============================================================

def search_doi_in_object(obj):

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

        # First search DOI-related fields
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

        # Then recurse
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
# Crossref metadata
# ============================================================

def get_crossref_metadata(doi):

    if not doi:
        return None

    # IMPORTANT:
    # Keep "/" unescaped in DOI path.
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

            return None

        data = response.json()

        return data.get(
            "message"
        )

    except Exception:

        return None


# ============================================================
# Crossref title search
# ============================================================

def search_crossref(pub):

    title = pub.get(
        "title",
        ""
    ).strip()

    if not title:
        return None

    year = get_year(
        pub
    )

    # Use cleaned title for Crossref query
    query_title = clean_title(
        title
    )

    params = {
        "query.title": query_title,
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

        titles = item.get(
            "title",
            []
        )

        if not titles:
            continue

        crossref_title = titles[0]

        similarity = title_similarity(
            title,
            crossref_title,
        )

        if similarity < CROSSREF_TITLE_THRESHOLD:
            continue

        # ----------------------------------------------------
        # Year
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
# DOI lookup
# ============================================================

def get_doi(pub):

    title = pub.get(
        "title",
        ""
    )

    print()
    print(
        f"DOI lookup: {title}"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Do NOT call view_citation.
    #
    # The citation_id returned by the author engine is not
    # reliable with the current SerpAPI configuration.
    #
    # Instead, search the article object itself.
    # --------------------------------------------------------

    scholar_doi = search_doi_in_object(
        pub
    )

    if scholar_doi:

        print(
            f"  Scholar article DOI: "
            f"{scholar_doi}"
        )

        # ----------------------------------------------------
        # Verify DOI through Crossref
        # ----------------------------------------------------

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
                    f"  Canonical DOI: "
                    f"{canonical_doi}"
                )

                return canonical_doi

        else:

            print(
                "  Scholar DOI could not be "
                "verified by Crossref."
            )

    else:

        print(
            "  No DOI found in Scholar article."
        )

    # --------------------------------------------------------
    # Crossref fallback
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

    scholar_title = pub.get(
        "title",
        ""
    ).strip()

    if not scholar_title:
        return scholar_title

    # --------------------------------------------------------
    # Crossref title
    # --------------------------------------------------------

    if doi:

        metadata = get_crossref_metadata(
            doi
        )

        if metadata:

            titles = metadata.get(
                "title",
                []
            )

            if titles:

                crossref_title = titles[0]

                similarity = title_similarity(
                    scholar_title,
                    crossref_title,
                )

                malformed = any(
                    re.search(
                        pattern,
                        scholar_title,
                        flags=re.IGNORECASE,
                    )
                    for pattern in [
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
                )

                if (
                    similarity >= 0.60
                    or malformed
                ):

                    return clean_title(
                        crossref_title
                    )

    # --------------------------------------------------------
    # Scholar title
    # --------------------------------------------------------

    return clean_title(
        scholar_title
    )


# ============================================================
# Markdown
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
# README update
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

    if not README.exists():

        raise FileNotFoundError(
            f"{README} not found."
        )

    readme_text = README.read_text(
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # Scholar
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
    # DOI
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
    # README
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
