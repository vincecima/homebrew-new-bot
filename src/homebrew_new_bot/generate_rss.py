import argparse
import feedgen.feed  # type: ignore
import sqlite_utils
from .utils import __tracer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "feed_namespace",
    )
    parser.add_argument(
        "db_path",
    )
    parser.add_argument(
        "feed_path",
    )
    args = parser.parse_args()

    fg = feedgen.feed.FeedGenerator()
    # TODO: Parameterize these values so we can publish one for Casks
    fg.title("Homebrew New Packages")
    fg.link(href="https://botsin.space/@homebrew_new_pkgs", rel="alternate")
    fg.description("New formula added to the Homebrew package manager ")
    # TODO: Add optional values

    db = sqlite_utils.Database(args.db_path, tracer=__tracer)
    for row in db.query(f"select * from {args.feed_namespace}_items"):
        fe = fg.add_entry()
        # TODO: What other fields do we want to set?
        fe.id(row["name"])
        fe.title(row["full_name"])
        fe.link(href=row["homepage"])
        fe.description(row["desc"])
        fe.guid(f"{row["name"]} - {row["added_at"]}")

    fg.rss_file(args.feed_path)
