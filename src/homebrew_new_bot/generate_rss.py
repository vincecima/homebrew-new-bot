import argparse
import datetime
import feedgen.feed  # type: ignore
import sqlite_utils
from .utils import __tracer

FEED_ITEMS_QUERY = """
SELECT *
FROM feed_items
WHERE namespace = ? 
AND added_at >= ?
ORDER BY added_at DESC
LIMIT 100
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("feed_namespace")
    parser.add_argument("db_path")
    parser.add_argument("feed_path")
    parser.add_argument("start_date", type=datetime.date.fromisoformat)
    args = parser.parse_args()

    fg = feedgen.feed.FeedGenerator()
    # TODO: Parameterize these values so we can publish one for Casks
    fg.title("Homebrew New Packages")
    fg.link(href="https://botsin.space/@homebrew_new_pkgs", rel="alternate")
    fg.description("New formula added to the Homebrew package manager ")
    # TODO: Add optional values

    db = sqlite_utils.Database(args.db_path, tracer=__tracer)
    for row in db.query(FEED_ITEMS_QUERY, [args.feed_namespace, args.start_date]):
        fe = fg.add_entry()
        # TODO: What other fields do we want to set?
        fe.id(row["name"])
        fe.title(row["full_name"])
        fe.link(href=row["homepage"])
        fe.description(row["desc"])
        fe.guid(f"{row["name"]}-{args.feed_namespace}")

    fg.rss_file(args.feed_path)
