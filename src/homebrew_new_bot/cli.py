from collections.abc import Callable

import click

from homebrew_new_bot.enums import PackageType


def package_type_option(
    fn: Callable[..., None],
) -> Callable[..., None]:
    click.argument(
        "package_type", type=click.Choice(list(PackageType), case_sensitive=False)
    )(fn)
    return fn
