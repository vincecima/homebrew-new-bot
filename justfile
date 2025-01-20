fmt:
    uv run ruff check --select I --fix .
    uv run ruff format .
    uv run yamlfix .

typecheck:
    uv run mypy --strict src/homebrew_new_bot
