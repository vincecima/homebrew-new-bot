from datetime import datetime, timezone
from typing import Any, cast

import click
from sqlite_utils import Database
from sqlite_utils.db import Table
from sqlite_utils.utils import rows_from_file

from homebrew_new_bot.cli import package_type_option
from homebrew_new_bot.enums import PackageType


def extract_id_value(package_type: PackageType, package_info: dict[str, Any]) -> str:
    id_value: str
    if package_type is PackageType.cask:
        id_value = package_info["full_token"]
    else:
        id_value = package_info["name"]
    return id_value


@click.command()
@package_type_option
def dump(package_type: PackageType) -> None:
    db = Database(f"state/{package_type}/packages.db")
    # TODO: Can we just stream directly to file?
    full_sql = "".join(db.iterdump())
    with open(f"state/{package_type}/packages.db.sql", "w") as file:
        file.write(str(full_sql))


@click.command()
@package_type_option
def restore(package_type: PackageType) -> None:
    # TODO: Can we just stream directly to db?
    with open(f"state/{package_type}/packages.db.sql") as file:
        full_sql = file.read()
    db = Database(f"state/{package_type}/packages.db")
    db.executescript(full_sql)


@click.command()
@package_type_option
def update(package_type: PackageType) -> None:
    added_at = datetime.now(timezone.utc)
    try:
        with open(f"state/{package_type}/api.json", "rb") as file:
            # NOTE: typing.IO and io.BaseIO are incompatible https://github.com/python/typeshed/issues/6077
            rows, format = rows_from_file(file)
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
