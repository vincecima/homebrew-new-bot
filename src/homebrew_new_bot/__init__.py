import argparse
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from sqlite_utils import Database
from sqlite_utils.utils import rows_from_file


class PackageType(StrEnum):
    cask = "cask"
    formula = "formula"


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
    # TODO: How do we define the choices dynamically
    parser.add_argument("package_type", choices=[PackageType.cask, PackageType.formula])
    args = parser.parse_args()

    now = datetime.now(timezone.utc)

    cursor_value = get_cursor_value(args.package_type, now)
    logging.debug(f"cursor_value = {cursor_value.isoformat()}")

    packages = get_packages(args.package_type, now)
    logging.debug(f"packages = {packages}")

    db = Database(f"{args.package_type}.db")
    db["packages"].insert_all(packages, pk="name", alter=True, ignore=True)
    # Select all items newer than cursor_value
    # Send out all that match oldest
    # Write cursor value past oldest


def get_cursor_value(package_type: PackageType, default_value: datetime) -> datetime:
    try:
        with open(f"{package_type}.cursor") as file:
            return datetime.fromisoformat(file.read())
    except Exception as ex:
        # TODO should we eat the error here?
        logging.warning("Using now as value for last_merged")
        logging.error(ex)
    return default_value


# TODO: Use the generation/cache time of the API for added_at
def get_packages(package_type: PackageType, added_at: datetime) -> list[dict]:
    try:
        with open(f"{package_type}.json", "rb") as file:
            rows, format = rows_from_file(file)
            for r in rows:
                r.update({"added_at": added_at})
            return rows
    except Exception as ex:
        logging.warning("API JSON not readable")
        # TODO should we eat the error here?
        logging.error(ex)
        return list()
