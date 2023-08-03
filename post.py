import logging
import json
import os
import random
import re
import requests
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from mastodon import Mastodon

HOMEBREW_GET_FORMULA_URL = "https://formulae.brew.sh/api/formula/{}.json"
PR_TITLE_PATTERN = re.compile(r"([0-9,a-z,\-,\\,\/]+)", re.IGNORECASE)


@dataclass
class PR:
    """Class for all the data needed from a GH PR."""

    merged_at: datetime
    title: str


@dataclass
class Formula:
    """Class for all the data needed from a Brew formula."""

    description: str
    full_name: str
    homepage: str
    name: str


def get_last_merged_state_value() -> datetime:
    merged_after = datetime.now(timezone.utc)

    try:
        with open("state/cursor") as file:
            merged_after = datetime.fromisoformat(file.read())
    except Exception as ex:
        logging.warning("Using now as value for last_merged")
        logging.error(ex)

    logging.debug(f"Loaded merged_after = {merged_after.isoformat()}")
    return merged_after


def set_last_merged_state_value(merged_at: datetime):
    logging.debug(f"Writing merged_after = {merged_at.isoformat()}")

    try:
        with open("state/cursor", "w") as file:
            file.write(merged_at.isoformat())
    except Exception as ex:
        logging.warning(
            f"Failed to write last_merged state value of {merged_at.isoformat()}"
        )
        logging.error(ex)

    return


def get_newly_merged_prs(merged_after: datetime) -> list[PR]:
    search_query = f'q=is:pr is:merged owner:Homebrew repo:homebrew-core label:"new formula"\
                merged:>{merged_after.isoformat()}'
    logging.debug(f"Search query = {search_query}")

    completed_process = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "GET",
            "search/issues",
            "-f",
            search_query,
        ],
        capture_output=True,
    )
    if completed_process.returncode > 0:
        logging.error(completed_process.stderr)
        exit(1)

    response = json.loads(completed_process.stdout)
    logging.debug(f"GH API response = {response}")

    return list(
        map(
            lambda item: PR(
                datetime.fromisoformat(item["pull_request"]["merged_at"]), item["title"]
            ),
            response["items"],
        )
    )


def parse_pr_title(title: str) -> str:
    match = PR_TITLE_PATTERN.match(title)
    logging.debug(f"Parsing PR title = {title}")

    if match is None:
        logging.warning(f"PR title '{title}' did not match expected pattern")
        return None
    elif len(match.groups()) > 1:
        logging.warning(f"PR title '{title}' resulted in > 1 match")
        return None
    else:
        logging.debug(f"Parsed PR title group 1 = {match.group(0)}")
        return match.group(0)


def get_metadata_for_formula(formula_title: str) -> Formula:
    try:
        full_url = HOMEBREW_GET_FORMULA_URL.format(formula_title)
        logging.debug(f"Homebrew API URL = {full_url}")

        r = requests.get(full_url)
        r.raise_for_status()
        response = r.json()
        logging.debug(f"Homebrew API response = {response}")

        return Formula(
            response["desc"],
            response["full_name"],
            response["homepage"],
            response["name"],
        )
    except Exception as err:
        logging.warning(f"Request for {full_url} failed")
        logging.error(err)


def schedule_toot(formula: Formula, scheduled_at: datetime, mastodon: Mastodon):
    toot_content = f"""
🍻 {formula.name} 🍻

{formula.description}

🔗 {formula.homepage}

#homebrew #newpkg #macos #linux
    """
    logging.debug(f"toot_content = {toot_content}")

    logging.info(f"Posting new toot for {formula.name} @ {scheduled_at.isoformat()}")

    try:
        scheduled_post = mastodon.status_post(
            status=toot_content, scheduled_at=scheduled_at
        )
        logging.debug(f"scheduled_post = {scheduled_post}")
    except Exception as ex:
        logging.warning(f"Scheduling status for {formula.name} failed")
        logging.error(ex)
        exit(1)

    return


def main():
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=LOG_LEVEL)

    MASTODON_API_BASE_URL = os.environ.get("MASTODON_API_BASE_URL")
    MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")
    MASTODON_CLIENT_SECRET = os.environ.get("MASTODON_CLIENT_SECRET")
    MAX_TOOTS_PER_EXECUTION = int(os.environ.get("MAX_TOOTS_PER_EXECUTION", "3"))

    if not all([MASTODON_API_BASE_URL, MASTODON_ACCESS_TOKEN, MASTODON_CLIENT_SECRET]):
        logging.error(
            "MASTODON_API_BASE_URL, MASTODON_ACCESS_TOKEN and MASTODON_CLIENT_SECRET must be set"
        )
        exit(1)

    logging.info(
        f"""
Environment variables =
 LOG_LEVEL={LOG_LEVEL},
 MAX_TOOTS_PER_EXECUTION={MAX_TOOTS_PER_EXECUTION},
 MASTODON_API_BASE_URL={MASTODON_API_BASE_URL}
        """
    )

    merged_after = get_last_merged_state_value()
    prs = get_newly_merged_prs(merged_after)
    if len(prs) == 0:
        logging.info("No new PRs found")
        set_last_merged_state_value(merged_after)
        exit(0)
    else:
        logging.info(f"Found {len(prs)} new formula to toot")

    scheduled_at = datetime.now(timezone.utc)
    mastodon = Mastodon(
        api_base_url=MASTODON_API_BASE_URL,
        access_token=MASTODON_ACCESS_TOKEN,
        client_secret=MASTODON_CLIENT_SECRET,
    )
    prs.sort(key=lambda pr: pr.merged_at)

    for i, pr in enumerate(prs):
        if (i) >= MAX_TOOTS_PER_EXECUTION:
            logging.info(
                "Ending run early because we have posted MAX_TOOTS_PER_EXECUTION toots"
            )
            exit(0)

        formula_title = parse_pr_title(pr.title)
        formula = get_metadata_for_formula(formula_title)
        scheduled_at = scheduled_at + timedelta(minutes=random.randint(10, 25))
        schedule_toot(formula, scheduled_at, mastodon)
        set_last_merged_state_value(pr.merged_at)

    exit(0)


if __name__ == "__main__":
    main()
