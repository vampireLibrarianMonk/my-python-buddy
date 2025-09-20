import json
from typing import Any


def load_user_data(serialized: str) -> Any:
    """
    Safely parse user data from a raw JSON string or hex-encoded JSON.
    Rejects anything that isn't valid JSON.
    """
    # try hex -> bytes -> str, otherwise treat input as plain text
    try:
        # if it's hex-encoded JSON, convert to text
        raw = bytes.fromhex(serialized).decode('utf-8')
    except ValueError:
        raw = serialized

    # parse JSON (safe for untrusted input)
    return json.loads(raw)


if __name__ == "__main__":
    user_input = input("Enter JSON data (or hex-encoded JSON): ").strip()
    try:
        data = load_user_data(user_input)
        print("Loaded data:", data)
    except json.JSONDecodeError as e:
        print("Invalid JSON:", e)
