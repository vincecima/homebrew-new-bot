import click
import requests

from homebrew_new_bot.cli import package_type_option
from homebrew_new_bot.enums import PackageType


@click.command()
@package_type_option
def update(package_type: PackageType) -> None:
    r = requests.get(f"https://formulae.brew.sh/api/{package_type}.json")
    # TODO: use last-modified for added_at and to short circuit full API request (via HEAD)
    # last_modified = email.utils.parsedate_to_datetime(r.headers["last-modified"])
    try:
        with open(f"state/{package_type}/api.json", "w") as file:
            file.write(r.text)
    except Exception as ex:
        raise ex
