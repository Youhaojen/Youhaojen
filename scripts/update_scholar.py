#!/usr/bin/env python3

from scholarly import scholarly
from pathlib import Path
import re


SCHOLAR_ID = "46cZ1-wAAAAJ"
README = Path("README.md")


def format_publication(pub):
    bib = pub["bib"]

    title = " ".join(bib.get("title", "Unknown title").split())
    journal = " ".join(bib.get("venue", "").split())
    year = bib.get("pub_year", "")
    citations = pub.get("num_citations", 0)
    url = bib.get("pub_url", "") or bib.get("url", "")

    if url:
        title_text = f"[{title}]({url})"
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

    print("Fetching Google Scholar profile...", flush=True)

    author = scholarly.search_author_id(SCHOLAR_ID)

    print("Loading publications...", flush=True)

    author = scholarly.fill(
        author,
        sections=["publications"],
    )

    publications = author.get("publications", [])

    print(
        f"Found {len(publications)} publications",
        flush=True,
    )

    # Do NOT call scholarly.fill() for every publication.
    # The author profile already contains citation counts,
    # titles, journals, years, and publication URLs.

    # ---------------------------------------------------------
    # Latest 3
    # ---------------------------------------------------------

    latest = sorted(
        publications,
        key=lambda x: int(
            x["bib"].get("pub_year", 0) or 0
        ),
        reverse=True,
    )[:3]

    # ---------------------------------------------------------
    # Most cited 3
    # ---------------------------------------------------------

    most_cited = sorted(
        publications,
        key=lambda x: x.get("num_citations", 0),
        reverse=True,
    )[:3]

    # ---------------------------------------------------------
    # Update README
    # ---------------------------------------------------------

    print("Updating README...", flush=True)

    readme = README.read_text(encoding="utf-8")

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

    print("README updated successfully.", flush=True)


if __name__ == "__main__":
    main()
