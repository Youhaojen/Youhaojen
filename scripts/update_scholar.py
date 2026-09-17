import os
import requests
from pathlib import Path
import re


SCHOLAR_ID = "46cZ1-wAAAAJ"
README = Path("README.md")
API_KEY = os.environ["SERPAPI_KEY"]


def get_publications():
    url = "https://serpapi.com/search.json"

    params = {
        "engine": "google_scholar_author",
        "author_id": SCHOLAR_ID,
        "api_key": API_KEY,
        "hl": "en",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()

    return data.get("articles", [])


def format_publication(pub):

    title = pub.get("title", "Unknown title")
    journal = pub.get("publication", "")
    year = pub.get("year", "")
    citations = pub.get("cited_by", {}).get("value", 0)
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


def update_section(readme, start, end, publications):

    pattern = re.escape(start) + r".*?" + re.escape(end)

    content = "\n".join(
        format_publication(pub)
        for pub in publications
    )

    replacement = (
        f"{start}\n"
        f"{content}\n"
        f"{end}"
    )

    return re.sub(
        pattern,
        replacement,
        readme,
        flags=re.DOTALL,
    )


def main():

    print("Fetching Google Scholar...", flush=True)

    publications = get_publications()

    print(
        f"Found {len(publications)} publications",
        flush=True,
    )

    # Latest 3
    latest = sorted(
        publications,
        key=lambda x: int(x.get("year", 0) or 0),
        reverse=True,
    )[:3]

    # Most cited 3
    most_cited = sorted(
        publications,
        key=lambda x: x.get("cited_by", {}).get("value", 0),
        reverse=True,
    )[:3]

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
