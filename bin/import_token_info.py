#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import token name/symbol/icon metadata into Blockscout via /api/v2/import/token-info."
    )
    parser.add_argument(
        "json_path",
        nargs="?",
        default="../tokens.json",
        help="Path to the tokens.json file. Default: ../tokens.json",
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Explorer base URL, for example https://bitonscan.com",
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="Value for both the x-api-key header and the api_key JSON field.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds. Default: 20",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print requests without sending them.",
    )
    return parser.parse_args()


def load_tokens(json_path):
    path = Path(json_path)
    data = json.loads(path.read_text())

    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")

    return path, data


def normalize_token(raw_token, index):
    if not isinstance(raw_token, dict):
        raise ValueError(f"Token #{index} must be an object")

    address = raw_token.get("address")
    icon_url = raw_token.get("icon")
    symbol = raw_token.get("symbol", "")
    name = raw_token.get("name", "")

    missing = [key for key, value in [("address", address), ("icon", icon_url)] if not isinstance(value, str) or not value.strip()]
    if missing:
        raise ValueError(f"Token #{index} missing required fields: {', '.join(missing)}")

    return {
        "token_address": address.strip(),
        "token_symbol": symbol.strip() if isinstance(symbol, str) else "",
        "token_name": name.strip() if isinstance(name, str) else "",
        "icon_url": icon_url.strip(),
    }


def post_token(base_url, api_key, payload, timeout):
    base_url = base_url.rstrip("/")
    url = f"{base_url}/api/v2/import/token-info"
    body = json.dumps(
        {
            "tokenAddress": payload["token_address"],
            "tokenSymbol": payload["token_symbol"],
            "tokenName": payload["token_name"],
            "iconUrl": payload["icon_url"],
            "api_key": api_key,
        }
    ).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "content-type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw_response = response.read().decode() or "{}"
        parsed = json.loads(raw_response)
        return response.status, parsed


def main():
    args = parse_args()

    try:
        path, tokens = load_tokens(args.json_path)
    except Exception as exc:
        print(f"Failed to load tokens file: {exc}", file=sys.stderr)
        return 1

    print(f"Loaded {len(tokens)} tokens from {path}")

    success_count = 0

    for index, raw_token in enumerate(tokens, start=1):
        try:
            payload = normalize_token(raw_token, index)
        except Exception as exc:
            print(f"[{index}/{len(tokens)}] skip: {exc}", file=sys.stderr)
            continue

        print(
            f"[{index}/{len(tokens)}] {payload['token_symbol'] or '-'} "
            f"{payload['token_address']} -> {payload['icon_url']}"
        )

        if args.dry_run:
            continue

        try:
            status, response = post_token(args.base_url, args.api_key, payload, args.timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            print(f"  HTTP {exc.code}: {body}", file=sys.stderr)
            continue
        except Exception as exc:
            print(f"  request failed: {exc}", file=sys.stderr)
            continue

        if status == 200 and response.get("message") == "Success":
            success_count += 1
            print("  ok")
        else:
            print(f"  unexpected response: HTTP {status} {response}", file=sys.stderr)

    if args.dry_run:
        print("Dry run finished.")
        return 0

    print(f"Imported {success_count}/{len(tokens)} tokens successfully.")
    return 0 if success_count == len(tokens) else 2


if __name__ == "__main__":
    raise SystemExit(main())
