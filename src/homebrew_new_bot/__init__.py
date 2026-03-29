import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

import click
import requests
from atproto import Client  # type: ignore
from jinja2 import Environment, FileSystemLoader, select_autoescape
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
    return click.argument(
        "package_type", type=click.Choice(list(PackageType), case_sensitive=False)
    )(fn)


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
    r = requests.get(
        f"https://formulae.brew.sh/api/{package_type}.json", timeout=60
    )
    r.raise_for_status()
    # TODO: use last-modified for added_at and to short circuit full API request (via HEAD)
    # last_modified = email.utils.parsedate_to_datetime(r.headers["last-modified"])
    with open(f"state/{package_type}/api.json", "w") as file:
        file.write(r.text)


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
    with open(f"state/{package_type}/api.json", "rb") as file:
        # NOTE: typing.IO and io.BaseIO are incompatible https://github.com/python/typeshed/issues/6077
        rows, _fmt = rows_from_file(file)
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

    db = Database(f"state/{package_type}/packages.db")
    packages_table = cast(Table, db.table("packages")).create(
        {"id": str, "added_at": datetime, "info": str}, pk="id", if_not_exists=True
    )
    packages_table.insert_all(packages, ignore=True)


@cli.command()
@package_type_option
def rss(package_type: PackageType) -> None:
    pass


@cli.command()
@click.option("--output", default="docs/index.html", show_default=True)
def status(output: str) -> None:
    type_data = {}
    for pkg_type in PackageType:
        db = Database(f"state/{pkg_type}/packages.db")
        row = next(
            db.query(
                "SELECT COUNT(*) as total, MAX(insert_order) as max_order FROM packages"
            )
        )
        total, max_order = row["total"], row["max_order"]

        services = {}
        for service in ("mastodon", "bsky"):
            with open(f"state/{pkg_type}/{service}.cursor") as f:
                cursor = int(f.read().strip())
            pending = max_order - cursor
            pct = round(cursor / max_order * 100, 1) if max_order else 0.0
            services[service] = {
                "cursor": cursor,
                "pending": pending,
                "progress_pct": pct,
            }

        recent = []
        for pkg in db.query(
            "SELECT insert_order, id, added_at, info FROM packages ORDER BY insert_order DESC LIMIT 10"
        ):
            recent.append({**pkg, "info": json.loads(pkg["info"])})

        type_data[pkg_type] = {
            "total": total,
            "max_order": max_order,
            "services": services,
            "recent": recent,
        }

    template_env = Environment(
        loader=FileSystemLoader("state"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
    )
    html = template_env.get_template("status.html.j2").render(
        types=type_data,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    logging.info(f"Status page written to {output}")


def validate_required(ctx: click.Context, param: click.ParamType, value: str) -> str:
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
    callback=validate_required,
)
@click.option(
    "--mastodon_access_token",
    envvar="MASTODON_ACCESS_TOKEN",
    show_envvar=True,
    callback=validate_required,
)
@click.option(
    "--mastodon_client_secret",
    envvar="MASTODON_CLIENT_SECRET",
    show_envvar=True,
    callback=validate_required,
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

    with open(f"state/{package_type}/mastodon.cursor") as file:
        cursor = int(file.read().strip())
        logging.info(f"Existing cursor value: {cursor}")
        new_cursor = cursor

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
    template_env = Environment(
        loader=FileSystemLoader(f"state/{package_type}"),
        autoescape=select_autoescape(),
        trim_blocks=True,
    )
    template = template_env.get_template("template.j2")
    # TODO: Is this idiomatic Python?
    for i, package in enumerate(packages):
        if (i) >= max_toots_per_execution:
            break
        else:
            package_info = json.loads(package["info"])
            # TODO: Remove dictionary reference
            template_output = template.render(**package_info)
            # TODO: Handle failure (backoff cursor)
            mastodon.status_post(status=template_output)
            new_cursor = package["insert_order"]

    with open(f"state/{package_type}/mastodon.cursor", "w") as file:
        # TODO: Do atomic write and replace
        logging.info(f"New cursor value: {new_cursor}")
        file.write(str(new_cursor))


@cli.command()
@package_type_option
@click.option(
    "--bsky_username",
    envvar="BSKY_USERNAME",
    show_envvar=True,
    callback=validate_required,
)
@click.option(
    "--bsky_password",
    envvar="BSKY_PASSWORD",
    show_envvar=True,
    callback=validate_required,
)
@click.option("--max_skeets_per_execution", default=1)
# TODO: Break this method up with helpers
def skeet(
    package_type: PackageType,
    bsky_username: str,
    bsky_password: str,
    max_skeets_per_execution: int,
) -> None:
    bsky = Client()
    bsky.login(bsky_username, bsky_password)

    with open(f"state/{package_type}/bsky.cursor") as file:
        cursor = int(file.read().strip())
        logging.info(f"Existing cursor value: {cursor}")
        new_cursor = cursor

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
    template_env = Environment(
        loader=FileSystemLoader(f"state/{package_type}"),
        autoescape=select_autoescape(),
        trim_blocks=True,
    )
    template = template_env.get_template("template.j2")
    # TODO: Is this idiomatic Python?
    for i, package in enumerate(packages):
        if (i) >= max_skeets_per_execution:
            break
        else:
            package_info = json.loads(package["info"])
            # TODO: Remove dictionary reference
            template_output = template.render(**package_info)
            # TODO: Handle failure (backoff cursor)
            bsky.send_post(template_output)
            new_cursor = package["insert_order"]

    with open(f"state/{package_type}/bsky.cursor", "w") as file:
        # TODO: Do atomic write and replace
        logging.info(f"New cursor value: {new_cursor}")
        file.write(str(new_cursor))
