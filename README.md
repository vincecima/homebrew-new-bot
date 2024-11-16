## GitHub Actions Environment Setup

```shell
 gh variable set mastodon_api_base_url --body "https://fosstodon.org"
 gh variable set max_toots_per_execution --body 1
 gh secret set --app actions --body REDACTED mastodon_access_token
 gh secret set --app actions --body REDACTED mastodon_client_secret
```
