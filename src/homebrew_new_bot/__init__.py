import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, BinaryIO, cast

import click
import requests
from mastodon import Mastodon  # type: ignore
from sqlite_utils import Database
from sqlite_utils.db import Table
from sqlite_utils.utils import rows_from_file


class PackageType(StrEnum):
    cask = "cask"
    formula = "formula"


def package_type_option(
    fn: Callable[..., None],
) -> Callable[..., None]:
    click.argument(
        "package_type", type=click.Choice(list(PackageType), case_sensitive=False)
    )(fn)
    return fn


def extract_id_value(package_type: PackageType, package_info: dict[str, Any]) -> str:
    id_value: str
    if package_type is PackageType.cask:
        id_value = package_info["full_token"]
    else:
        id_value = package_info["name"]
    return id_value


@click.group()
@click.version_option("1.0")
@click.option("--verbose", "-v", is_flag=True, help="Enables verbose mode.")
def cli(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)


@cli.command()
@package_type_option
def api(package_type: PackageType) -> None:
    r = requests.get(f"https://formulae.brew.sh/api/{package_type}.json")
    # TODO: use last-modified for added_at and to short circuit full API request (via HEAD)
    # last_modified = email.utils.parsedate_to_datetime(r.headers["last-modified"])
    try:
        with open(f"state/{package_type}/api.json", "w") as file:
            file.write(r.text)
    except Exception as ex:
        raise ex


# NOTE: Create database parent for subcommands
@cli.group()
def database() -> None:
    return


@database.command()
@package_type_option
def dump(package_type: PackageType) -> None:
    db = Database(f"state/{package_type}/packages.db")
    # TODO: Can we just stream directly to file?
    full_sql = "".join(db.iterdump())
    with open(f"state/{package_type}/packages.db.sql", "w") as file:
        file.write(str(full_sql))


@database.command()
@package_type_option
def restore(package_type: PackageType) -> None:
    # TODO: Can we just stream directly to db?
    with open(f"state/{package_type}/packages.db.sql") as file:
        full_sql = file.read()
    db = Database(f"state/{package_type}/packages.db")
    db.executescript(full_sql)


@database.command()
@package_type_option
def update(package_type: PackageType) -> None:
    added_at = datetime.now(timezone.utc)
    try:
        with open(f"state/{package_type}/api.json") as file:
            # NOTE: typing.IO and io.BaseIO are incompatible https://github.com/python/typeshed/issues/6077
            rows, format = rows_from_file(cast(BinaryIO, file))
            packages = list(
                map(
                    lambda x: {
                        "id": extract_id_value(package_type, x),
                        "added_at": added_at.isoformat(),
                        "info": x,
                    },
                    rows,
                )
            )
    except Exception as ex:
        raise ex

    db = Database(f"state/{package_type}/packages.db")
    packages_table = cast(Table, db.table("packages")).create(
        {"id": str, "added_at": datetime, "info": str}, pk="id", if_not_exists=True
    )
    packages_table.insert_all(packages, ignore=True)


@cli.command()
@package_type_option
def rss(package_type: PackageType) -> None:
    pass


def validate_mastodon_config(
    ctx: click.Context, param: click.ParamType, value: str
) -> str:
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
    package_type: PackageType,
    mastodon_api_base_url: str,
    mastodon_access_token: str,
    mastodon_client_secret: str,
    max_toots_per_execution: int,
) -> None:
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
            "select id, added_at, info, insert_order from packages where insert_order > :cursor order by insert_order ASC",
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
            new_cursor = package["insert_order"]

    with open(f"state/{package_type}/cursor.txt", "w") as file:
        # TODO: Do atomic write and replace
        logging.info(f"New cursor value: {new_cursor}")
        file.write(str(new_cursor))
