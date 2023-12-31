import logging
import json
import os
import requests
from dataclasses import dataclass
from deepdiff import DeepDiff
from homebrew_new_bot.utils import load_mastodon_config_from_env

HOMEBREW_CASK_JSON_API_URL = "https://formulae.brew.sh/api/cask.json"
API_SNAPSHOT_PATH = "state/snapshots/cask.json"


@dataclass
class Cask:
    """Class for all the data needed from a Brew cask."""

    name: str
    description: str
    homepage: str


def get_metadata_for_all_casks() -> str:
    try:
        r = requests.get(HOMEBREW_CASK_JSON_API_URL)
        r.raise_for_status()
        body = r.text
        logging.debug(f"Homebrew API response = {body}")

        return body
    except Exception as err:
        logging.warning(f"Request for {HOMEBREW_CASK_JSON_API_URL} failed")
        logging.error(err)
        exit(1)


def get_metadata_snapshot() -> str | None:
    snapshot = None
    try:
        with open(API_SNAPSHOT_PATH) as file:
            snapshot = file.read()
    except FileNotFoundError:
        logging.warning("Cask API snapshot not found")
    except Exception as ex:
        logging.warning("Failed to read cask API snapshot")
        logging.error(ex)

    return snapshot


def set_metadata_snapshot(snapshot: str) -> None:
    try:
        with open(API_SNAPSHOT_PATH, "w") as file:
            file.write(snapshot)
    except Exception as ex:
        logging.warning("Failed to write cask API snapshot")
        logging.error(ex)

    return


def collect_new_casks(latest_payload: str, snapshot_payload: str) -> list[Cask]:
    lastest_casks = json.loads(latest_payload)
    snapshot_casks = json.loads(snapshot_payload)
    diff = DeepDiff(
        snapshot_casks, lastest_casks, group_by="token", view="tree", verbose_level=0
    )

    items_added = diff.get("dictionary_item_added", [])
    if len(items_added) == 0:
        return []
    else:
        return list(
            map(
                lambda item: Cask(
                    item.t2["name"][0],
                    item.t2["desc"],  # Might be None
                    item.t2["homepage"],
                ),
                items_added,
            )
        )


def main() -> None:
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=LOG_LEVEL)

    (
        mastodon_api_base_url,
        mastodon_access_token,
        mastodon_client_secret,
    ) = load_mastodon_config_from_env()
    if not all([mastodon_api_base_url, mastodon_access_token, mastodon_client_secret]):
        logging.error(
            "MASTODON_API_BASE_URL, MASTODON_ACCESS_TOKEN and MASTODON_CLIENT_SECRET\
             must be set"
        )
        exit(1)
    # TODO: load local configuration

    latest_payload = get_metadata_for_all_casks()
    snapshot_payload = get_metadata_snapshot()

    if isinstance(snapshot_payload, str):
        logging.info("Existing snapshot found, looking for new casks")
        new_casks = collect_new_casks(latest_payload, snapshot_payload)

    set_metadata_snapshot(latest_payload)

    exit(0)
