#!/usr/bin/env python3

from scholarly import scholarly
from pathlib import Path
import re


SCHOLAR_ID = "46cZ1-wAAAAJ"
README = Path("README.md")


def format_publication(pub):
    bib = pub["bib"]

    title = bib.get("title", "Unknown title")
    journal = bib.get("venue", "")
    year = bib.get("pub_year", "")
    citations = pub.get("num_citations", 0)
    url = bib.get("url", "")

    # Remove unnecessary whitespace
    title = " ".join(title.split())
    journal = " ".join(journal.split())

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

    content = "\n".join(format_publication(pub) for pub in publications)

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

    print("Fetching Google Scholar profile...")

    author = scholarly.search_author_id(SCHOLAR_ID)
    author = scholarly.fill(author, sections=["publications"])

    publications = author["publications"]

    print(f"Found {len(publications)} publications")

    # Fill publication information
    filled = []

    for pub in publications:
        try:
            pub = scholarly.fill(pub)
            filled.append(pub)
        except Exception as e:
            print(f"Warning: failed to fetch publication: {e}")

    # ---------------------------------------------------------
    # Latest 3
    # ---------------------------------------------------------

    latest = sorted(
        filled,
        key=lambda x: int(
            x["bib"].get("pub_year", 0) or 0
        ),
        reverse=True,
    )[:3]

    # ---------------------------------------------------------
    # Most cited 3
    # ---------------------------------------------------------

    most_cited = sorted(
        filled,
        key=lambda x: x.get("num_citations", 0),
        reverse=True,
    )[:3]

    # ---------------------------------------------------------
    # Update README
    # ---------------------------------------------------------

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

    print("README updated successfully.")


if __name__ == "__main__":
    main()