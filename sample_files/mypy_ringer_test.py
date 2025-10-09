from typing import Any


# error + info: Incompatible return value type (got "str", expected "int")
def add_numbers(a: int, b: int) -> int:
    return str(a + b)  # wrong return type


# error + info: Missing type annotation for argument
def passthrough(x):  # missing arg type
    return x  # triggers function type annotation error


# error + info: Unused "type: ignore" comment
value: int = 5  # base var
result = value + 10  # ok
result += 1  # ok
result += 1  # type: ignore  # unused ignore comment


# error + info: Undefined variable reference
def missing_var() -> None:
    print(z)  # undefined variable
