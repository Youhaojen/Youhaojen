#!/usr/bin/env python3

import os
import re
import requests
from pathlib import Path


SCHOLAR_ID = "46cZ1-wAAAAJ"
README = Path("README.md")

CROSSREF_API = "https://api.crossref.org/works"


# ---------------------------------------------------------
# Google Scholar
# ---------------------------------------------------------

def get_publications():

    api_key = os.environ.get("SERPAPI_KEY")

    if not api_key:
        raise RuntimeError(
            "SERPAPI_KEY is not set. "
            "Please add it to GitHub Actions Secrets."
        )

    url = "https://serpapi.com/search.json"

    params = {
        "engine": "google_scholar_author",
        "author_id": SCHOLAR_ID,
        "api_key": api_key,
        "hl": "en",
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    return data.get("articles", [])


# ---------------------------------------------------------
# Data processing
# ---------------------------------------------------------

def get_year(pub):

    try:
        return int(pub.get("year") or 0)

    except (TypeError, ValueError):
        return 0


def get_citations(pub):

    try:
        value = pub.get("cited_by", {}).get("value")

        return int(value or 0)

    except (
        TypeError,
        ValueError,
        AttributeError,
    ):
        return 0


# ---------------------------------------------------------
# Title correction
# ---------------------------------------------------------

TITLE_CORRECTIONS = {

    # Google Scholar occasionally loses subscripts,
    # Greek letters, or special characters.

    "Lattice dynamics and thermoelectric transport in (, Y; , Se, Te): Role of anharmonic phonons and Ag-sublattice vibrations":
        "Lattice dynamics and thermoelectric transport in MAgCh2 (M=Sc, Y; Ch=S, Se, Te): Role of anharmonic phonons and Ag-sublattice vibrations",
}


def clean_title(title):

    title = " ".join(
        str(title).split()
    )

    return TITLE_CORRECTIONS.get(
        title,
        title,
    )


# ---------------------------------------------------------
# DOI lookup
# ---------------------------------------------------------

def get_doi(title, year=None):

    params = {
        "query.title": title,
        "rows": 3,
    }

    if year:
        params["filter"] = f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31"

    headers = {
        "User-Agent":
            "Youhaojen-GitHub-Scholar-Updater/1.0 "
            "(mailto:your-email@example.com)"
    }

    try:

        response = requests.get(
            CROSSREF_API,
            params=params,
            headers=headers,
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        items = data.get(
            "message",
            {}
        ).get(
            "items",
            []
        )

        if not items:
            return None

        # Try to find the closest title match
        normalized_title = normalize_title(title)

        for item in items:

            candidate = " ".join(
                item.get("title", [""])[0].split()
            )

            if normalize_title(candidate) == normalized_title:

                doi = item.get("DOI")

                if doi:
                    return doi

        # If exact match is not found,
        # use the first Crossref result.
        doi = items[0].get("DOI")

        return doi

    except Exception as e:

        print(
            f"Warning: DOI lookup failed for '{title}': {e}",
            flush=True,
        )

        return None


def normalize_title(title):

    title = title.lower()

    # Remove punctuation and spaces
    title = re.sub(
        r"[^a-z0-9]",
        "",
        title,
    )

    return title


# ---------------------------------------------------------
# Format publication
# ---------------------------------------------------------

def format_publication(pub):

    raw_title = pub.get(
        "title",
        "Unknown title",
    )

    title = clean_title(raw_title)

    journal = " ".join(
        str(
            pub.get(
                "publication",
                "",
            )
        ).split()
    )

    year = pub.get("year") or ""

    citations = get_citations(pub)

    doi = pub.get("_doi")

    if doi:

        link = f"https://doi.org/{doi}"

    else:

        link = pub.get(
            "link",
            "",
        )

    if link:

        title_text = (
            f"[{title}]({link})"
        )

    else:

        title_text = f"**{title}**"

    details = []

    if journal:
        details.append(journal)

    if year:
        details.append(str(year))

    details.append(
        f"{citations} citations"
    )

    return (
        f"- {title_text}  \n"
        f"  *{' · '.join(details)}*"
    )


# ---------------------------------------------------------
# README
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

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

    # -----------------------------------------------------
    # DOI lookup
    # -----------------------------------------------------

    print(
        "\nLooking up DOIs...",
        flush=True,
    )

    for pub in publications:

        title = clean_title(
            pub.get(
                "title",
                "",
            )
        )

        year = get_year(pub)

        doi = get_doi(
            title,
            year,
        )

        pub["_doi"] = doi

        if doi:

            print(
                f"  DOI found: {doi}",
                flush=True,
            )

        else:

            print(
                f"  DOI not found: {title}",
                flush=True,
            )

    # -----------------------------------------------------
    # Latest 3
    # -----------------------------------------------------

    latest = sorted(
        publications,
        key=get_year,
        reverse=True,
    )[:3]

    # -----------------------------------------------------
    # Most cited 3
    # -----------------------------------------------------

    most_cited = sorted(
        publications,
        key=get_citations,
        reverse=True,
    )[:3]

    # -----------------------------------------------------
    # Update README
    # -----------------------------------------------------

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
        "README updated successfully.",
        flush=True,
    )


if __name__ == "__main__":
    main()
