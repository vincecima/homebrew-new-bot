import argparse
import logging
import os
import pathlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlite_utils import Database
from sqlite_utils.utils import rows_from_file


@dataclass
class Package:
    """Class for all the data needed for a Package."""

    description: str
    full_name: str
    homepage: str
    name: str


def main() -> None:
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=LOG_LEVEL)

    MASTODON_API_BASE_URL = os.environ.get("MASTODON_API_BASE_URL")
    MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")
    MASTODON_CLIENT_SECRET = os.environ.get("MASTODON_CLIENT_SECRET")
    MAX_TOOTS_PER_EXECUTION = int(os.environ.get("MAX_TOOTS_PER_EXECUTION", "3"))

    parser = argparse.ArgumentParser()
    parser.add_argument("json", type=pathlib.Path)
    parser.add_argument("cursor", type=pathlib.Path)
    args = parser.parse_args()

    cursor_value = get_cursor_value(args.cursor)
    logging.debug(f"cursor_value = {cursor_value.isoformat()}")

    packages = get_packages(args.json)
    logging.debug(f"packages = {packages}")

    db = Database(memory=True)
    db["packages"].insert_all(packages, pk="name", alter=True)
    # Select all items newer than cursor_value
    # Send out all that match oldest
    # Write cursor value past oldest


def get_cursor_value(cursor_path: pathlib.Path) -> datetime:
    value = datetime.now(timezone.utc)
    if cursor_path.exists():
        try:
            with cursor_path.open() as file:
                value = datetime.fromisoformat(file.read())
        except Exception as ex:
            logging.warning("Using now as value for last_merged")
            logging.error(ex)
    return value


def get_packages(json_path: pathlib.Path) -> list[dict]:
    if json_path.exists():
        try:
            with json_path.open("rb") as file:
                rows, format = rows_from_file(file)
            return list(rows)
        except Exception as ex:
            logging.warning("API JSON not readable")
            # TODO should we eat the error here?
            logging.error(ex)
            return list()
