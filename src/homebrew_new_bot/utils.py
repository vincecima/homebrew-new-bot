import typing


def __tracer(sql: str, params: dict[str, typing.Any]) -> None:
    print("SQL: {} - params: {}".format(sql, params))
