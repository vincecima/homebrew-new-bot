import email.utils
import logging
from datetime import datetime, timezone
from enum import StrEnum

import click
import requests
from sqlite_utils import Database
from sqlite_utils.utils import rows_from_file


class PackageType(StrEnum):
    cask = "cask"
    formula = "formula"


def package_type_option(fn):
    click.argument(
        "package_type", type=click.Choice(PackageType, case_sensitive=False)
    )(fn)
    return fn


@click.group()
@click.version_option("1.0")
@click.option("--verbose", "-v", is_flag=True, help="Enables verbose mode.")
def cli(verbose):
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)


@cli.command()
@package_type_option
def api(package_type):
    r = requests.get(f"https://formulae.brew.sh/api/{package_type}.json")
    last_modified = email.utils.parsedate_to_datetime(r.headers["last-modified"])
    try:
        with open(f"state/{package_type}/api.json", "w") as file:
            file.write(r.text)
    except Exception as ex:
        return ex


@cli.command()
@package_type_option
def database(package_type):
    added_at = datetime.now(timezone.utc)
    packages = None
    try:
        with open(f"state/{package_type}/api.json", "rb") as file:
            rows, format = rows_from_file(file)
            packages = list(
                map(lambda x: {"id": x["name"], "added_at": added_at, "info": x}, rows)
            )
    except Exception as ex:
        return ex

    db = Database(f"state/{package_type}/packages.db")
    db["packages"].create(
        {"id": str, "added_at": datetime, "info": str}, pk="id", if_not_exists=True
    )
    db["packages"].insert_all(packages, ignore=True)


@cli.command()
@package_type_option
def rss(package_type):
    pass


@cli.command()
@package_type_option
def toot(package_type):
    pass


# def main() -> None:
#     MASTODON_API_BASE_URL = os.environ.get("MASTODON_API_BASE_URL")
#     MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")
#     MASTODON_CLIENT_SECRET = os.environ.get("MASTODON_CLIENT_SECRET")
#     MAX_TOOTS_PER_EXECUTION = int(os.environ.get("MAX_TOOTS_PER_EXECUTION", "3"))


# def get_cursor_value(package_type: PackageType, default_value: datetime) -> datetime:
#     try:
#         with open(f"{package_type}.cursor") as file:
#             return datetime.fromisoformat(file.read())
#     except Exception as ex:
#         # TODO should we eat the error here?
#         logging.warning("Using now as value for last_merged")
#         logging.error(ex)
#     return default_value


# TODO: Use the generation/cache time of the API for added_at
# def get_packages(package_type: PackageType, added_at: datetime) -> list[dict]:
#     try:
#         with open(f"{package_type}.json", "rb") as file:
#             rows, format = rows_from_file(file)
#             return list(
#                 map(lambda x: {"id": x["name"], "added_at": added_at, "info": x}, rows)
#             )
#     except Exception as ex:
#         logging.warning("API JSON not readable")
#         # TODO should we eat the error here?
#         logging.error(ex)
#         return list()
