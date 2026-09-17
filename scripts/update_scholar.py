#!/usr/bin/env python3

import os
import re
import requests
from pathlib import Path


SCHOLAR_ID = "46cZ1-wAAAAJ"
README = Path("README.md")


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


def get_year(pub):
    """Return publication year as an integer."""
    try:
        return int(pub.get("year") or 0)
    except (TypeError, ValueError):
        return 0


def get_citations(pub):
    """Return citation count as an integer."""
    try:
        value = pub.get("cited_by", {}).get("value")
        return int(value or 0)
    except (TypeError, ValueError, AttributeError):
        return 0


def format_publication(pub):

    title = " ".join(
        str(pub.get("title", "Unknown title")).split()
    )

    journal = " ".join(
        str(pub.get("publication", "")).split()
    )

    year = pub.get("year") or ""
    citations = get_citations(pub)
    link = pub.get("link", "")

    if link:
        title_text = f"[{title}]({link})"
    else:
        title_text = f"**{title}**"

    details = []

    if journal:
        details.append(journal)

    if year:
        details.append(str(year))

    details.append(f"{citations} citations")

    return f"- {title_text}  \n  *{' · '.join(details)}*"


def update_section(readme, start_marker, end_marker, publications):

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

    # ---------------------------------------------------------
    # Latest 3
    # ---------------------------------------------------------

    latest = sorted(
        publications,
        key=get_year,
        reverse=True,
    )[:3]

    # ---------------------------------------------------------
    # Most cited 3
    # ---------------------------------------------------------

    most_cited = sorted(
        publications,
        key=get_citations,
        reverse=True,
    )[:3]

    print(
        "\nLatest 3:",
        flush=True,
    )

    for pub in latest:
        print(
            f"  {get_year(pub)} | "
            f"{get_citations(pub)} citations | "
            f"{pub.get('title', '')}",
            flush=True,
        )

    print(
        "\nMost cited 3:",
        flush=True,
    )

    for pub in most_cited:
        print(
            f"  {get_citations(pub)} citations | "
            f"{pub.get('title', '')}",
            flush=True,
        )

    # ---------------------------------------------------------
    # Update README
    # ---------------------------------------------------------

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
