import json
import logging
from datetime import datetime, timezone
from enum import StrEnum

import click
import requests
from mastodon import Mastodon
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
    # TODO: use last-modified for added_at and to short circuit full API request (via HEAD)
    # last_modified = email.utils.parsedate_to_datetime(r.headers["last-modified"])
    try:
        with open(f"state/{package_type}/api.json", "w") as file:
            file.write(r.text)
    except Exception as ex:
        return ex


@cli.command()
@package_type_option
def database(package_type):
    added_at = datetime.now(timezone.utc)
    try:
        with open(f"state/{package_type}/api.json", "rb") as file:
            rows, format = rows_from_file(file)
            packages = list(
                map(
                    lambda x: {
                        "id": x["name"],
                        "added_at": added_at.isoformat(),
                        "info": x,
                    },
                    rows,
                )
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


def validate_mastodon_config(ctx, param, value):
    if value is None:
        raise click.BadParameter("required")
    else:
        return value


@cli.command()
@package_type_option
@click.option(
    "--mastodon_api_base_url",
    envvar="MASTODON_API_BASE_URL",
    show_envvar=True,
    callback=validate_mastodon_config,
)
@click.option(
    "--mastodon_access_token",
    envvar="MASTODON_ACCESS_TOKEN",
    show_envvar=True,
    callback=validate_mastodon_config,
)
@click.option(
    "--mastodon_client_secret",
    envvar="MASTODON_CLIENT_SECRET",
    show_envvar=True,
    callback=validate_mastodon_config,
)
@click.option("--max_toots_per_execution", default=1)
# TODO: Break this method up with helpers
def toot(
    package_type,
    mastodon_api_base_url,
    mastodon_access_token,
    mastodon_client_secret,
    max_toots_per_execution,
):
    mastodon = Mastodon(
        api_base_url=mastodon_api_base_url,
        access_token=mastodon_access_token,
        client_secret=mastodon_client_secret,
    )

    with open(f"state/{package_type}/cursor.txt") as file:
        cursor = int(file.read().strip())
        logging.info(f"Existing cursor value: {cursor}")
        new_cursor = cursor

    with open(f"state/{package_type}/template.txt") as file:
        template = file.read()

    # TODO: Factor out loading from correct state folder
    db = Database(f"state/{package_type}/packages.db")
    # TODO: Load data into dataclass
    # TODO: Move query out of inline?
    packages = list(
        db.query(
            "select id, added_at, info, ROWID from packages where ROWID > :cursor order by ROWID ASC",
            {"cursor": cursor},
        )
    )

    if not packages:
        logging.info(f"No packages found with cursor after {cursor}")
        return
    logging.info(
        f"Found {len(packages)} packages to be posted, {packages[0]['id']}...{packages[-1]['id']}"
    )
    # TODO: Is this idiomatic Python?
    for i, package in enumerate(packages):
        if (i) >= max_toots_per_execution:
            break
        else:
            package_info = json.loads(package["info"])
            # TODO: Remove dictionary reference
            template_output = template.format(**package_info)
            # TOOD: Handle failure (backoff cursor)
            mastodon.status_post(status=template_output)
            new_cursor = package["rowid"]

    with open(f"state/{package_type}/cursor.txt", "w") as file:
        # TODO: Do atomic write and replace
        logging.info(f"New cursor value: {new_cursor}")
        file.write(str(new_cursor))
