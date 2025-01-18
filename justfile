fmt:
    uv run ruff check --select I --fix .
    uv run ruff format .

typecheck:
    uv run mypy --strict src/homebrew_new_bot
