import json
import logging

import click
import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape
from mastodon import Mastodon  # type: ignore
from sqlite_utils import Database

from homebrew_new_bot.cli import package_type_option
from homebrew_new_bot.commands.database import dump, restore, update
from homebrew_new_bot.enums import PackageType


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


database.add_command(dump)
database.add_command(restore)
database.add_command(update)


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
