#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://app.alice.ws"
CONSOLE_BASE = "https://console.alice.ws"
USER_AGENT = "Mozilla/5.0 AliceFreeTrafficClaimer/1.0"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "alice_config.json"
DEFAULT_TOKEN_CACHE = SCRIPT_DIR / "alice_token.json"


class ApiError(RuntimeError):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response or {}

    def is_auth_error(self):
        text = json.dumps(self.response, ensure_ascii=False).lower()
        message = str(self).lower()
        return any(
            marker in f"{message} {text}"
            for marker in ("unauthorized", "unauthenticated", "invalid token", "token expired", "401")
        )


def api_request(method, path, token=None, body=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": CONSOLE_BASE,
        "Referer": f"{CONSOLE_BASE}/",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")

    request = Request(
        f"{API_BASE}{path}",
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"code": 0, "message": f"HTTP {exc.code}", "body": raw}
    except URLError as exc:
        return {"code": 0, "message": f"Network error: {exc.reason}"}

    return json.loads(raw)


def is_success(response):
    return isinstance(response, dict) and response.get("code") == 1


def login(email, password):
    response = api_request(
        "POST",
        "/api/v1/auth/login",
        body={"email": email, "password": password},
    )
    if not is_success(response):
        message = response.get("message") or response.get("error") or "login failed"
        raise RuntimeError(f"{message}; response={json.dumps(response, ensure_ascii=False)}")

    token = (response.get("data") or {}).get("token")
    if not token:
        raise RuntimeError("login succeeded but response did not contain data.token")

    return token


def read_json(path, default=None):
    try:
        with Path(path).open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, payload):
    with Path(path).open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def load_cached_token(path):
    payload = read_json(path, default={})
    if not payload:
        return None

    token = payload.get("token")
    return token if token else None


def save_cached_token(path, token):
    write_json(path, {
        "token": token,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


def load_config(path):
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"config file not found: {config_path}")

    return read_json(config_path, default={})


def is_free_traffic_package(package):
    amount = str(package.get("amount_display") or "").upper()
    resource_type = package.get("resource_type") or package.get("type")
    return (
        package.get("status") == 1
        and int(package.get("point_price") or 0) == 0
        and (resource_type == "traffic" or "50" in amount)
    )


def choose_free_traffic_packages(packages):
    candidates = [package for package in packages or [] if is_free_traffic_package(package)]

    return sorted(
        candidates,
        key=lambda package: (
            0 if "50" in str(package.get("amount_display") or "").upper() else 1,
            package.get("id") or 0,
        ),
    )


def parse_datetime(value):
    if not value:
        return None

    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    formats = [
        None,
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            if fmt is None:
                dt = datetime.fromisoformat(text)
            else:
                dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    return None


def looks_like_free_traffic_user_package(package):
    amount = str(
        package.get("total_amount_display")
        or package.get("amount_display")
        or package.get("remaining_amount_display")
        or ""
    ).upper()
    remark = str(package.get("remark") or "").lower()
    source = str(package.get("source") or "").lower()
    return (
        package.get("type") == "traffic"
        and ("50" in amount or "50gb" in remark or "50 gb" in remark)
        and (source in ("", "gift", "free") or "free" in remark)
    )


def get_active_free_traffic_package(token):
    response = api_request("GET", "/api/v1/user/packages?status=active", token=token)
    if not is_success(response):
        raise ApiError(response.get("message") or "failed to load active user packages", response)

    packages = (response.get("data") or {}).get("packages") or []
    now = datetime.now(timezone.utc)
    active_packages = [
        (parse_datetime(package.get("expires_at")), package)
        for package in packages
        if looks_like_free_traffic_user_package(package)
    ]
    active_packages = [
        (expires_at, package)
        for expires_at, package in active_packages
        if expires_at is None or expires_at > now
    ]

    if not active_packages:
        return None

    active_packages.sort(key=lambda item: item[0] or datetime.max.replace(tzinfo=timezone.utc))
    return active_packages[0][1]


def describe_user_package(package):
    package_id = package.get("id")
    amount = package.get("total_amount_display") or package.get("amount_display") or "unknown amount"
    remaining = package.get("remaining_amount_display") or "unknown remaining"
    expires_at = package.get("expires_at") or "unknown expiry"
    return f"id={package_id}, amount={amount}, remaining={remaining}, expires_at={expires_at}"


def claim_free_traffic(token, dry_run=False, claim_all=False, force=False):
    if not force:
        active_package = get_active_free_traffic_package(token)
        if active_package:
            print(f"Skip claim: active free traffic package still valid ({describe_user_package(active_package)})")
            return 0

    query = urlencode({"type": "traffic", "is_free": "1"})
    response = api_request("GET", f"/api/v1/resource-packages?{query}", token=token)
    if not is_success(response):
        raise ApiError(response.get("message") or "failed to load free packages", response)

    packages = choose_free_traffic_packages(response.get("data"))
    if not packages:
        print("No active free traffic package found.")
        return 0

    targets = packages if claim_all else packages[:1]
    failures = 0

    for package in targets:
        package_id = package.get("id")
        name = package.get("name") or f"Package #{package_id}"
        amount = package.get("amount_display") or "unknown amount"

        if dry_run:
            print(f"Would claim: {name} ({amount}), id={package_id}")
            continue

        claim_response = api_request(
            "POST",
            f"/api/v1/resource-packages/{package_id}/claim",
            token=token,
            body={},
        )
        if is_success(claim_response):
            print(f"Claimed: {name} ({amount}), id={package_id}")
        else:
            failures += 1
            message = claim_response.get("message") or "unknown error"
            print(f"Claim failed: {name} ({amount}), id={package_id}, message={message}")

    return failures


def main():
    parser = argparse.ArgumentParser(description="Claim Alice Networks monthly free traffic package.")
    parser.add_argument(
        "-c",
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Path to config JSON. Default: {DEFAULT_CONFIG}",
    )
    parser.add_argument("--email", help="Alice account email. Overrides config file.")
    parser.add_argument("--password", help="Alice account password. Overrides config file.")
    parser.add_argument("--dry-run", action="store_true", help="Show package without claiming it.")
    parser.add_argument("--claim-all", action="store_true", help="Claim all matching free packages.")
    parser.add_argument("--force", action="store_true", help="Claim without checking active package expiry first.")
    parser.add_argument(
        "--token-cache",
        default=str(DEFAULT_TOKEN_CACHE),
        help=f"Path to token cache JSON. Default: {DEFAULT_TOKEN_CACHE}",
    )
    parser.add_argument("--no-token-cache", action="store_true", help="Do not read or write token cache.")
    args = parser.parse_args()

    if not args.no_token_cache:
        cached_token = load_cached_token(args.token_cache)
        if cached_token:
            try:
                print("Using cached token.")
                return claim_free_traffic(
                    cached_token,
                    dry_run=args.dry_run,
                    claim_all=args.claim_all,
                    force=args.force,
                )
            except ApiError as exc:
                if not exc.is_auth_error():
                    raise
                print("Cached token is invalid or expired. Logging in again.")

    config = {}
    if not args.email or not args.password:
        config = load_config(args.config)

    email = args.email or config.get("email")
    password = args.password or config.get("password")

    if not email or not password:
        raise RuntimeError("missing email/password; set them in config or pass --email/--password")

    token = login(email, password)
    if not args.no_token_cache:
        save_cached_token(args.token_cache, token)
        print(f"Saved token cache: {args.token_cache}")

    return claim_free_traffic(
        token,
        dry_run=args.dry_run,
        claim_all=args.claim_all,
        force=args.force,
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
