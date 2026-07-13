#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Generate images via OpenAI or Gemini image models.

Standalone uv single-file script — stdlib only (urllib.request), no
third-party dependencies. See `.claude/skills/image-gen/SKILL.md` for the
operator-facing ritual and `README.md` ("Generating images") for setup.

Usage:
    uv run tools/imagegen.py --prompt "a foggy moor" --out moor.png
    uv run tools/imagegen.py --prompt "a" --out a.png --prompt "b" --out b.png
    uv run tools/imagegen.py --batch prompts.json
    uv run tools/imagegen.py --ledger-status

Providers are selected via the IMAGE_MODEL env var (default "openai"),
overridable per-run with --model. Valid values: "openai", "gemini",
"gemini-2.5-flash".

Spend control: IMAGEGEN_MAX_PER_RUN (default 1) caps images per invocation.
IMAGEGEN_SPEND_CAP_USD (default 5.00) refuses to run if cumulative
estimated spend (tracked in .imagegen-ledger.json at the repo root) plus
this run's estimate would exceed it. Cost estimates are rough and
documented in COST_ESTIMATES_USD below — they are not real billing data.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

# Maps an IMAGE_MODEL value to the provider-specific model id used in API
# calls.
MODEL_IDS = {
    "openai": "gpt-image-1.5",
    "gemini": "gemini-3-pro-image-preview",
    "gemini-2.5-flash": "gemini-2.5-flash-image",
}

# Maps an IMAGE_MODEL value to which HTTP backend handles it.
PROVIDER_OF = {
    "openai": "openai",
    "gemini": "gemini",
    "gemini-2.5-flash": "gemini",
}

# Rough per-image cost estimates in USD, used only for the spend ledger and
# cap enforcement below. These are NOT authoritative billing figures —
# check the provider's pricing page for real numbers. Ballpark as of
# writing: gpt-image-1.5 at quality=medium/1024x1024 ~= $0.07; Gemini
# flash image ~= $0.04; Gemini 3 Pro image ~= $0.15.
COST_ESTIMATES_USD = {
    "openai": 0.07,
    "gemini": 0.15,
    "gemini-2.5-flash": 0.04,
}

HTTP_TIMEOUT_SECONDS = 120


class ImageGenError(Exception):
    """A user-facing, expected failure. Caught in main() and printed
    without a traceback — never let this leak past main()."""


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ.

    Existing environment variables always win (a var already set in
    os.environ is never overwritten). Blank lines and lines starting with
    '#' are ignored. Values may be wrapped in matching single or double
    quotes, which are stripped.
    """
    if not path.is_file():
        return
    try:
        text = path.read_text()
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def load_ledger(path: Path) -> list:
    """Return the list of ledger records, or [] if the file is missing,
    unreadable, or not a JSON list."""
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return data


def ledger_total(records: list) -> float:
    return sum(float(r.get("estimated_usd", 0)) for r in records if isinstance(r, dict))


def append_ledger(path: Path, record: dict) -> None:
    records = load_ledger(path)
    records.append(record)
    path.write_text(json.dumps(records, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Env-driven config helpers
# ---------------------------------------------------------------------------

def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ImageGenError(f"{name} must be an integer, got {raw!r}")


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise ImageGenError(f"{name} must be a number, got {raw!r}")


def resolve_model(cli_model: str | None) -> str:
    name = cli_model or os.environ.get("IMAGE_MODEL", "openai")
    if name not in MODEL_IDS:
        raise ImageGenError(
            f"Unknown IMAGE_MODEL {name!r}; expected one of {sorted(MODEL_IDS)}"
        )
    return name


def get_api_key(provider: str) -> str:
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ImageGenError(
                "Missing OPENAI_API_KEY for provider 'openai'. "
                "Set it in .env (see .env.sample) or export it before running."
            )
        return key
    if provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ImageGenError(
                "Missing GEMINI_API_KEY for provider 'gemini'. "
                "Set it in .env (see .env.sample) or export it before running."
            )
        return key
    raise ImageGenError(f"Unknown provider {provider!r}")


# ---------------------------------------------------------------------------
# Spend caps
# ---------------------------------------------------------------------------

def check_max_per_run(num_images: int, max_per_run: int) -> None:
    if num_images > max_per_run:
        raise ImageGenError(
            f"Refusing to generate {num_images} image(s) in one run: "
            f"IMAGEGEN_MAX_PER_RUN is {max_per_run}. Raise IMAGEGEN_MAX_PER_RUN "
            "(env or .env) to generate more per invocation."
        )


def check_spend_cap(current_total: float, added_cost: float, cap: float) -> float:
    """Return the projected total if this run proceeds, or raise
    ImageGenError if it would exceed the cap."""
    projected = current_total + added_cost
    if projected > cap + 1e-9:
        raise ImageGenError(
            f"Refusing to generate: ledger total is ${current_total:.2f}, this run "
            f"would add ~${added_cost:.2f} (est.), bringing the total to "
            f"~${projected:.2f}, over the IMAGEGEN_SPEND_CAP_USD cap of "
            f"${cap:.2f}. Raise IMAGEGEN_SPEND_CAP_USD (env or .env) to proceed."
        )
    return projected


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _extract_error_message(body_text: str) -> str:
    text = body_text.strip()
    if not text:
        return "(empty response body)"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:300]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str) and err:
            return err
    return text[:300]


def _post_json(url: str, headers: dict, payload: dict, provider: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        message = _extract_error_message(body_text)
        if e.code in (401, 403):
            raise ImageGenError(
                f"API key appears invalid for {provider} (HTTP {e.code}): {message}"
            )
        raise ImageGenError(f"{provider} API error (HTTP {e.code}): {message}")
    except urllib.error.URLError as e:
        raise ImageGenError(f"Could not reach {provider} API: {e.reason}")
    except TimeoutError:
        raise ImageGenError(f"{provider} API request timed out")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ImageGenError(f"{provider} API returned an unparseable response")


# ---------------------------------------------------------------------------
# Provider calls (verbatim known-working shapes)
# ---------------------------------------------------------------------------

def call_openai(prompt: str, size: str, api_key: str) -> bytes:
    url = "https://api.openai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-image-1.5",
        "prompt": prompt,
        "size": size,
        "quality": "medium",
        "output_format": "png",
    }
    body = _post_json(url, headers, payload, "openai")
    try:
        b64 = body["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError):
        raise ImageGenError(f"openai response missing image data: {json.dumps(body)[:300]}")
    try:
        return base64.b64decode(b64)
    except Exception:
        raise ImageGenError("openai response image data was not valid base64")


def call_gemini(model_id: str, prompt: str, api_key: str) -> bytes:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_id}:generateContent?key={api_key}"
    )
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    body = _post_json(url, headers, payload, "gemini")
    try:
        parts = body["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        raise ImageGenError(f"gemini response missing candidates: {json.dumps(body)[:300]}")
    for part in parts:
        inline = part.get("inlineData") if isinstance(part, dict) else None
        if inline and str(inline.get("mimeType", "")).startswith("image/"):
            try:
                return base64.b64decode(inline["data"])
            except Exception:
                raise ImageGenError("gemini response image data was not valid base64")
    raise ImageGenError(f"gemini response did not contain an image part: {json.dumps(body)[:300]}")


def generate_image_bytes(model_name: str, prompt: str, size: str, api_key: str) -> bytes:
    provider = PROVIDER_OF[model_name]
    if provider == "openai":
        return call_openai(prompt, size, api_key)
    return call_gemini(MODEL_IDS[model_name], prompt, api_key)


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imagegen.py",
        description="Generate images via OpenAI or Gemini, with a spend ledger and caps.",
    )
    parser.add_argument("--prompt", action="append", default=[],
                        help="Image prompt. Repeat with --out for multiple images.")
    parser.add_argument("--out", action="append", default=[],
                        help="Output PNG path. Pairs with --prompt by position.")
    parser.add_argument("--batch",
                        help='Path to a JSON file: a list of {"prompt": ..., "out": ...} objects.')
    parser.add_argument("--model", choices=list(MODEL_IDS),
                        help="Override IMAGE_MODEL for this run.")
    parser.add_argument("--size", default="1024x1024",
                        help="Image size (OpenAI only; Gemini ignores this).")
    parser.add_argument("--ledger-status", action="store_true",
                        help="Print cumulative ledger spend and exit.")
    return parser


def build_jobs(args) -> list[tuple[str, str]]:
    jobs: list[tuple[str, str]] = []
    if args.batch:
        batch_path = Path(args.batch)
        try:
            raw = batch_path.read_text()
        except OSError as e:
            raise ImageGenError(f"Could not read --batch file {args.batch}: {e}")
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ImageGenError(f"--batch file {args.batch} is not valid JSON: {e}")
        if not isinstance(entries, list):
            raise ImageGenError(f"--batch file {args.batch} must contain a JSON array")
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict) or "prompt" not in entry or "out" not in entry:
                raise ImageGenError(
                    f"--batch entry {i} must be an object with 'prompt' and 'out' keys"
                )
            jobs.append((entry["prompt"], entry["out"]))
    if args.prompt or args.out:
        if len(args.prompt) != len(args.out):
            raise ImageGenError(
                f"Got {len(args.prompt)} --prompt flag(s) but {len(args.out)} --out "
                "flag(s); they must pair up 1:1"
            )
        jobs.extend(zip(args.prompt, args.out))
    return jobs


def main(argv: list[str] | None = None, *, repo_root: Path | None = None) -> int:
    repo_root = repo_root or Path(__file__).resolve().parent.parent
    load_dotenv(repo_root / ".env")

    parser = build_parser()
    args = parser.parse_args(argv)

    ledger_path = repo_root / ".imagegen-ledger.json"

    if args.ledger_status:
        records = load_ledger(ledger_path)
        print(f"imagegen ledger: {len(records)} image(s), ${ledger_total(records):.2f} "
              "total estimated spend")
        return 0

    try:
        jobs = build_jobs(args)
        if not jobs:
            raise ImageGenError(
                "Nothing to generate: pass --prompt/--out pairs or --batch FILE.json"
            )

        model_name = resolve_model(args.model)
        per_image_cost = COST_ESTIMATES_USD[model_name]

        max_per_run = _int_env("IMAGEGEN_MAX_PER_RUN", 1)
        check_max_per_run(len(jobs), max_per_run)

        spend_cap = _float_env("IMAGEGEN_SPEND_CAP_USD", 5.00)
        current_total = ledger_total(load_ledger(ledger_path))
        check_spend_cap(current_total, per_image_cost * len(jobs), spend_cap)

        provider = PROVIDER_OF[model_name]
        api_key = get_api_key(provider)

        running_total = current_total
        for prompt, out in jobs:
            image_bytes = generate_image_bytes(model_name, prompt, args.size, api_key)
            out_path = Path(out)
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(image_bytes)
            except OSError as e:
                raise ImageGenError(f"Could not write {out_path}: {e}")
            append_ledger(ledger_path, {
                "timestamp": time.time(),
                "model": model_name,
                "estimated_usd": per_image_cost,
            })
            running_total += per_image_cost
            print(f"wrote {out_path} ({model_name}, ~${per_image_cost:.2f} est.) "
                  f"— ledger total ~${running_total:.2f}")
        return 0
    except ImageGenError as e:
        print(f"imagegen: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
