import argparse
import email.utils
import requests
import sqlite_utils
import typing


def ingest() -> None:
    # TODO: refactor to have a CLI wrapper to extract args
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "feed_namespace",
    )
    parser.add_argument(
        "db_path",
    )
    parser.add_argument(
        "json_api_url",
    )
    args = parser.parse_args()

    # TODO: make tracer optional (along with log level?)
    db = sqlite_utils.Database(args.db_path, tracer=__tracer)
    table = typing.cast(sqlite_utils.db.Table, db[f"{args.feed_namespace}_items"])
    # Get JSON from API endpoint
    # TODO: use latest added_at from DB and HEAD to check if its even worth getting full thing?
    r = requests.get("https://formulae.brew.sh/api/formula.json")
    last_modified = email.utils.parsedate_to_datetime(r.headers["last-modified"])
    # TODO: is there a shorter syntax to do this?
    packages = list(
        map(
            lambda x: {
                "name": x["name"],
                "full_name": x["full_name"],
                "desc": x["desc"],
                "homepage": x["homepage"],
                "added_at": last_modified,
            },
            r.json(),
        )
    )
    # TODO: Use http://www.sqlite.org/c3ref/changes.html or http://www.sqlite.org/c3ref/total_changes.html to report the number of actual inserts
    table.insert_all(
        packages,
        # TODO: Confirm that name is the true primary key
        # TODO: How can we generalize this for formula and casks?
        pk="name",
        column_order=["name", "full_name", "desc", "homepage", "added_at"],
        ignore=True,
    )
    return


def __tracer(sql: str, params: dict[str, typing.Any]) -> None:
    print("SQL: {} - params: {}".format(sql, params))
