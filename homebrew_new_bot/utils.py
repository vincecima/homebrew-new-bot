import os

def load_mastodon_config_from_env() -> tuple[str | None, str | None, str | None]:
    mastodon_api_base_url = os.environ.get("MASTODON_API_BASE_URL")
    mastodon_access_token = os.environ.get("MASTODON_ACCESS_TOKEN")
    mastodon_client_secret = os.environ.get("MASTODON_CLIENT_SECRET")

    return mastodon_api_base_url, mastodon_access_token, mastodon_client_secret