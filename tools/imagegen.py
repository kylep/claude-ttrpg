#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Generate images from text prompts via OpenAI, Google (Gemini/Imagen), or
Black Forest Labs (FLUX). Standalone uv single-file script — stdlib only
(urllib), no third-party dependencies. See `.claude/skills/image-gen/SKILL.md`
for the operator ritual and `README.md` ("Generating images") for setup.

Keys: reads OPENAI_API_KEY / GEMINI_API_KEY / BFL_API_KEY from the environment.
If a needed key isn't already exported it falls back to parsing `exports.sh`
(then `.env`) at the repo root. So either works:
    source exports.sh && uv run tools/imagegen.py --prompt "a red dragon" --out d.png
    uv run tools/imagegen.py --prompt "a red dragon" --out d.png     # auto-reads exports.sh/.env

Usage:
    uv run tools/imagegen.py --prompt "a foggy moor" --out moor.png
    uv run tools/imagegen.py --prompt "a" --out a.png --prompt "b" --out b.png
    uv run tools/imagegen.py --batch prompts.json
    uv run tools/imagegen.py --prompt "x" --out x.png --model nano-banana-pro
    uv run tools/imagegen.py --list-models
    uv run tools/imagegen.py --ledger-status

Model is chosen with --model (or the IMAGE_MODEL env var); default is the
strongest general-purpose flagship (DEFAULT_MODEL). Any id or alias from
--list-models works, spanning all four backends.

Spend control: IMAGEGEN_MAX_PER_RUN (default 1) caps images per invocation.
IMAGEGEN_SPEND_CAP_USD (default 5.00) refuses to run if cumulative estimated
spend (tracked in .imagegen-ledger.json at the repo root) plus this run's
estimate would exceed it. The per-image `cost` figures below are rough
over-estimates for the cap, NOT real billing.

=============================================================================
MODELS & PRICES — researched 2026-07-18 from each provider's pricing/docs.
Rough per-image, text-to-image at ~1024px; they DRIFT. OpenAI bills per-token
so its per-image numbers are estimates from OpenAI's own calculator. Sources
at the bottom of this file. `cost` = conservative USD estimate used only for
the spend ledger/cap; `price` = human-readable orientation.
=============================================================================
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
# Model registry (keyed by the real API model id; prices as of 2026-07-18)
# ---------------------------------------------------------------------------
# provider selects the HTTP backend + key:
#   "openai" -> OPENAI_API_KEY, POST /v1/images/generations
#   "gemini" -> GEMINI_API_KEY, :generateContent (the "Nano Banana" family)
#   "imagen" -> GEMINI_API_KEY, :predict (Google's dedicated Imagen models)
#   "bfl"    -> BFL_API_KEY, async submit + poll (Black Forest Labs FLUX)
MODELS: dict[str, dict] = {
    # -- OpenAI (per-image is an estimate; billed per-token). GPT Image 2 is the
    #    2026 flagship; gpt-image-1 deprecates 2026-10-23 so it's omitted.
    "gpt-image-2":      {"provider": "openai", "cost": 0.20, "price": "~$0.005–0.21/img (low–high)"},
    "gpt-image-1.5":    {"provider": "openai", "cost": 0.19, "price": "~$0.009–0.20/img"},
    "gpt-image-1-mini": {"provider": "openai", "cost": 0.05, "price": "~$0.005–0.05/img (cheapest OpenAI)"},
    # -- Google Gemini "Nano Banana" native image gen (:generateContent).
    "gemini-3-pro-image":          {"provider": "gemini", "cost": 0.15, "price": "~$0.13/img @1–2K, ~$0.24 @4K (Nano Banana Pro)"},
    "gemini-3.1-flash-image":      {"provider": "gemini", "cost": 0.07, "price": "~$0.067/img @1K (Nano Banana 2)"},
    "gemini-3.1-flash-lite-image": {"provider": "gemini", "cost": 0.04, "price": "cheapest Gemini flash-image"},
    "gemini-2.5-flash-image":      {"provider": "gemini", "cost": 0.04, "price": "~$0.039/img @1K (legacy Nano Banana)"},
    # -- Google Imagen 4 (:predict). NOTE (verified 2026-07-18): these are GATED —
    #    a new Gemini API key gets HTTP 404 "no longer available to new users" and
    #    Google steers you to the Nano Banana (gemini-*-image) models above. Kept
    #    for accounts that still have Imagen access; new keys should use nano-banana.
    "imagen-4.0-ultra-generate-001": {"provider": "imagen", "cost": 0.06, "price": "~$0.06/img (GATED: new keys 404 -> use nano-banana)"},
    "imagen-4.0-generate-001":       {"provider": "imagen", "cost": 0.04, "price": "~$0.04/img (GATED: new keys 404 -> use nano-banana)"},
    "imagen-4.0-fast-generate-001":  {"provider": "imagen", "cost": 0.02, "price": "~$0.02/img (GATED: new keys 404 -> use nano-banana)"},
    # -- Black Forest Labs FLUX (async). FLUX.2 is megapixel-priced.
    "flux-2-max":         {"provider": "bfl", "cost": 0.08,  "price": "~$0.07+/img, scales w/ megapixels (top FLUX.2)"},
    "flux-2-pro":         {"provider": "bfl", "cost": 0.03,  "price": "~$0.03/img @1MP, scales w/ MP"},
    "flux-2-flex":        {"provider": "bfl", "cost": 0.02,  "price": "~$0.015 × MP /img"},
    "flux-2-klein-9b":    {"provider": "bfl", "cost": 0.02,  "price": "fast/cheap FLUX.2"},
    "flux-2-klein-4b":    {"provider": "bfl", "cost": 0.014, "price": "from ~$0.014/img (cheapest FLUX.2)"},
    "flux-pro-1.1-ultra": {"provider": "bfl", "cost": 0.06,  "price": "~$0.06/img (4MP, FLUX1.1)"},
    "flux-pro-1.1":       {"provider": "bfl", "cost": 0.04,  "price": "~$0.04/img (FLUX1.1)"},
    "flux-kontext-max":   {"provider": "bfl", "cost": 0.08,  "price": "image editing, top tier"},
    "flux-kontext-pro":   {"provider": "bfl", "cost": 0.05,  "price": "image editing"},
}

# Friendly aliases -> canonical model id.
ALIASES: dict[str, str] = {
    "nano-banana-pro": "gemini-3-pro-image",
    "nano-banana-2":   "gemini-3.1-flash-image",
    "nano-banana":     "gemini-2.5-flash-image",
    "imagen-4":        "imagen-4.0-generate-001",
    "imagen-4-ultra":  "imagen-4.0-ultra-generate-001",
    "imagen-4-fast":   "imagen-4.0-fast-generate-001",
    "flux":            "flux-2-pro",
    "flux-pro":        "flux-2-pro",
}

# The default = the strongest general-purpose flagship. OpenAI's GPT Image 2 is a
# safe, top-quality default with strong prompt + text rendering (it painted the
# world map well via ChatGPT). Try `nano-banana-pro` (Gemini) or `flux-2-max`
# (BFL) when comparing. Change this one line to re-default.
DEFAULT_MODEL = "gpt-image-2"

KEY_ENV = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY",
           "imagen": "GEMINI_API_KEY", "bfl": "BFL_API_KEY"}

HTTP_TIMEOUT_SECONDS = 180
BFL_POLL_TIMEOUT_SECONDS = 180
BFL_POLL_INTERVAL_SECONDS = 1.5


class ImageGenError(Exception):
    """A user-facing, expected failure. Caught in main() and printed without a
    traceback — never let this leak past main()."""


# ---------------------------------------------------------------------------
# Key/env loading (env wins; fall back to exports.sh then .env at repo root)
# ---------------------------------------------------------------------------

def _load_env_file(path: Path, *, export_prefix: bool) -> None:
    """Parse KEY=VALUE (optionally `export KEY=VALUE`) lines into os.environ.
    Existing env vars always win. Single/double quotes are stripped."""
    if not path.is_file():
        return
    try:
        text = path.read_text()
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if export_prefix and line.startswith("export "):
            line = line[len("export "):]
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if value[:1] not in ("'", '"') and " #" in value:
            value = value.split(" #", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (env wins)."""
    _load_env_file(path, export_prefix=False)


def load_exports(path: Path) -> None:
    """Load `export KEY=VALUE` pairs from an exports.sh file (env wins)."""
    _load_env_file(path, export_prefix=True)


def get_api_key(provider: str) -> str:
    env = KEY_ENV[provider]
    key = os.environ.get(env)
    if not key or not key.strip():
        raise ImageGenError(
            f"Missing {env} for provider '{provider}'. Add it to exports.sh "
            "(export ...) or .env at the repo root, or export it in your shell, "
            "then retry."
        )
    return key.strip()


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def load_ledger(path: Path) -> list:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


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
    """Resolve --model / IMAGE_MODEL (id or alias) to a canonical model id."""
    name = cli_model or os.environ.get("IMAGE_MODEL") or DEFAULT_MODEL
    name = ALIASES.get(name, name)
    if name not in MODELS:
        raise ImageGenError(
            f"Unknown model {name!r}. Run with --list-models to see valid ids/aliases."
        )
    return name


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
    text = (body_text or "").strip()
    if not text:
        return "(empty response body)"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:400]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str) and err:
            return err
        for k in ("detail", "message"):
            if data.get(k):
                return str(data[k])
    return text[:400]


def _request(method: str, url: str, provider: str, *, headers: dict | None = None,
             payload: dict | None = None) -> tuple[int, bytes, dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            return getattr(resp, "status", 200), resp.read(), dict(getattr(resp, "headers", {}) or {})
    except urllib.error.HTTPError as e:
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        message = _extract_error_message(body_text)
        if e.code in (401, 403):
            raise ImageGenError(f"API key appears invalid for {provider} (HTTP {e.code}): {message}")
        if e.code == 404:
            raise ImageGenError(
                f"{provider}: model/endpoint not found (HTTP 404): {message}. Model ids "
                "drift — run --list-models or check the provider's docs."
            )
        if e.code == 429:
            raise ImageGenError(f"{provider} rate-limited or out of quota (HTTP 429): {message}")
        raise ImageGenError(f"{provider} API error (HTTP {e.code}): {message}")
    except urllib.error.URLError as e:
        raise ImageGenError(f"Could not reach {provider} API: {e.reason}")
    except TimeoutError:
        raise ImageGenError(f"{provider} API request timed out")


def _post_json(url: str, headers: dict, payload: dict, provider: str) -> dict:
    _, raw, _ = _request("POST", url, provider, headers=headers, payload=payload)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise ImageGenError(f"{provider} API returned an unparseable response")


# ---------------------------------------------------------------------------
# size / aspect helpers
# ---------------------------------------------------------------------------

def parse_size(size: str) -> tuple[int, int]:
    try:
        w, h = size.lower().split("x")
        return int(w), int(h)
    except Exception:
        raise ImageGenError(f"--size must look like WIDTHxHEIGHT, got {size!r}")


def nearest_aspect(w: int, h: int) -> str:
    ratios = {"1:1": 1.0, "3:4": 3 / 4, "4:3": 4 / 3, "9:16": 9 / 16, "16:9": 16 / 9}
    target = w / h
    return min(ratios, key=lambda k: abs(ratios[k] - target))


# ---------------------------------------------------------------------------
# Provider calls  -> return (image_bytes, file_extension)
# ---------------------------------------------------------------------------

def call_openai(model_id: str, prompt: str, size: str, quality: str, key: str) -> tuple[bytes, str]:
    url = "https://api.openai.com/v1/images/generations"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": model_id, "prompt": prompt, "size": size,
               "quality": quality, "output_format": "png"}
    body = _post_json(url, headers, payload, "openai")
    try:
        b64 = body["data"][0]["b64_json"]
    except (KeyError, IndexError, TypeError):
        raise ImageGenError(f"openai response missing image data: {json.dumps(body)[:300]}")
    try:
        return base64.b64decode(b64), "png"
    except Exception:
        raise ImageGenError("openai response image data was not valid base64")


def call_gemini(model_id: str, prompt: str, aspect: str, key: str) -> tuple[bytes, str]:
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model_id}:generateContent?key={key}")
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"],
                             "imageConfig": {"aspectRatio": aspect}},
    }
    body = _post_json(url, headers, payload, "gemini")
    try:
        parts = body["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        raise ImageGenError(f"gemini response missing candidates: {json.dumps(body)[:300]}")
    for part in parts:
        inline = part.get("inlineData") if isinstance(part, dict) else None
        if inline and str(inline.get("mimeType", "")).startswith("image/"):
            ext = str(inline.get("mimeType", "image/png")).split("/")[-1]
            try:
                return base64.b64decode(inline["data"]), ext
            except Exception:
                raise ImageGenError("gemini response image data was not valid base64")
    raise ImageGenError(f"gemini response did not contain an image part: {json.dumps(body)[:300]}")


def call_imagen(model_id: str, prompt: str, aspect: str, key: str) -> tuple[bytes, str]:
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model_id}:predict?key={key}")
    headers = {"Content-Type": "application/json"}
    payload = {"instances": [{"prompt": prompt}],
               "parameters": {"sampleCount": 1, "aspectRatio": aspect}}
    body = _post_json(url, headers, payload, "imagen")
    try:
        b64 = body["predictions"][0]["bytesBase64Encoded"]
    except (KeyError, IndexError, TypeError):
        raise ImageGenError(f"imagen response missing image data: {json.dumps(body)[:300]}")
    try:
        return base64.b64decode(b64), "png"
    except Exception:
        raise ImageGenError("imagen response image data was not valid base64")


def call_bfl(model_id: str, prompt: str, w: int, h: int, key: str,
             verbose: bool = False) -> tuple[bytes, str]:
    """BFL is async: submit -> poll polling_url -> download the result URL."""
    headers = {"x-key": key, "Content-Type": "application/json", "accept": "application/json"}
    submit = _post_json(f"https://api.bfl.ai/v1/{model_id}", headers,
                        {"prompt": prompt, "width": w, "height": h}, "bfl")
    poll_url = submit.get("polling_url")
    req_id = submit.get("id")
    if not poll_url:
        raise ImageGenError(f"bfl submit returned no polling_url: {json.dumps(submit)[:300]}")
    deadline = time.monotonic() + BFL_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        _, raw, _ = _request("GET", poll_url, "bfl",
                             headers={"x-key": key, "accept": "application/json"})
        try:
            res = json.loads(raw)
        except json.JSONDecodeError:
            raise ImageGenError("bfl polling returned an unparseable response")
        status = str(res.get("status", ""))
        if verbose:
            print(f"  bfl [{req_id}] status: {status}", file=sys.stderr)
        if status == "Ready":
            sample = (res.get("result") or {}).get("sample")
            if not sample:
                raise ImageGenError(f"bfl ready but no image url: {json.dumps(res)[:300]}")
            _, img, hdrs = _request("GET", sample, "bfl")
            ext = "jpg" if "jpeg" in str(hdrs.get("Content-Type", "")).lower() else "png"
            return img, ext
        if status in ("Error", "Failed"):
            raise ImageGenError(f"bfl generation failed: {json.dumps(res)[:300]}")
        if status in ("Content Moderated", "Request Moderated"):
            raise ImageGenError("bfl refused the request (content moderation)")
        time.sleep(BFL_POLL_INTERVAL_SECONDS)
    raise ImageGenError(f"bfl generation timed out after {BFL_POLL_TIMEOUT_SECONDS}s")


def generate_image_bytes(model_id: str, prompt: str, size: str, quality: str,
                         key: str, verbose: bool = False) -> tuple[bytes, str]:
    provider = MODELS[model_id]["provider"]
    w, h = parse_size(size)
    if provider == "openai":
        return call_openai(model_id, prompt, size, quality, key)
    if provider == "gemini":
        return call_gemini(model_id, prompt, nearest_aspect(w, h), key)
    if provider == "imagen":
        return call_imagen(model_id, prompt, nearest_aspect(w, h), key)
    if provider == "bfl":
        return call_bfl(model_id, prompt, w, h, key, verbose)
    raise ImageGenError(f"internal: unknown provider {provider!r}")


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imagegen.py",
        description="Generate images via OpenAI, Gemini/Imagen, or BFL FLUX, "
                    "with a spend ledger and caps.")
    parser.add_argument("--prompt", action="append", default=[],
                        help="Image prompt. Repeat with --out for multiple images.")
    parser.add_argument("--out", action="append", default=[],
                        help="Output image path. Pairs with --prompt by position.")
    parser.add_argument("--batch",
                        help='JSON file: a list of {"prompt": ..., "out": ...} objects.')
    parser.add_argument("--model",
                        help=f"Model id or alias (default {DEFAULT_MODEL}); see --list-models.")
    parser.add_argument("--size", default="1024x1024",
                        help="WIDTHxHEIGHT (default 1024x1024). Gemini/Imagen map it to "
                             "the nearest aspect ratio.")
    parser.add_argument("--quality", default="high", choices=["low", "medium", "high", "auto"],
                        help="OpenAI quality tier (default high; higher = pricier). Others ignore it.")
    parser.add_argument("--list-models", action="store_true",
                        help="Print the model/price map and exit.")
    parser.add_argument("--ledger-status", action="store_true",
                        help="Print cumulative ledger spend and exit.")
    parser.add_argument("--verbose", action="store_true",
                        help="Print progress (model choice, BFL polling).")
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
                    f"--batch entry {i} must be an object with 'prompt' and 'out' keys")
            jobs.append((entry["prompt"], entry["out"]))
    if args.prompt or args.out:
        if len(args.prompt) != len(args.out):
            raise ImageGenError(
                f"Got {len(args.prompt)} --prompt flag(s) but {len(args.out)} --out "
                "flag(s); they must pair up 1:1")
        jobs.extend(zip(args.prompt, args.out))
    return jobs


def print_models() -> None:
    print("Available models (prices rough, researched 2026-07-18 — verify before spending):\n")
    labels = {"openai": "OpenAI (OPENAI_API_KEY)",
              "gemini": "Google Gemini / Nano Banana (GEMINI_API_KEY)",
              "imagen": "Google Imagen (GEMINI_API_KEY)",
              "bfl": "Black Forest Labs FLUX (BFL_API_KEY)"}
    for prov, label in labels.items():
        print(f"  {label}:")
        for mid, meta in MODELS.items():
            if meta["provider"] == prov:
                star = "   <- DEFAULT" if mid == DEFAULT_MODEL else ""
                print(f"    {mid:32} {meta['price']}{star}")
        print()
    print("  aliases: " + ", ".join(f"{a}={t}" for a, t in ALIASES.items()))


def main(argv: list[str] | None = None, *, repo_root: Path | None = None) -> int:
    repo_root = repo_root or Path(__file__).resolve().parent.parent
    load_exports(repo_root / "exports.sh")
    load_dotenv(repo_root / ".env")

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_models:
        print_models()
        return 0

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
                "Nothing to generate: pass --prompt/--out pairs, --batch FILE.json, "
                "or --list-models.")

        model_id = resolve_model(args.model)
        per_image_cost = MODELS[model_id]["cost"]

        max_per_run = _int_env("IMAGEGEN_MAX_PER_RUN", 1)
        check_max_per_run(len(jobs), max_per_run)

        spend_cap = _float_env("IMAGEGEN_SPEND_CAP_USD", 5.00)
        current_total = ledger_total(load_ledger(ledger_path))
        check_spend_cap(current_total, per_image_cost * len(jobs), spend_cap)

        provider = MODELS[model_id]["provider"]
        api_key = get_api_key(provider)
        if args.verbose:
            print(f"model={model_id} provider={provider} price={MODELS[model_id]['price']}",
                  file=sys.stderr)

        running_total = current_total
        for prompt, out in jobs:
            image_bytes, _ext = generate_image_bytes(
                model_id, prompt, args.size, args.quality, api_key, args.verbose)
            out_path = Path(out)
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(image_bytes)
            except OSError as e:
                raise ImageGenError(f"Could not write {out_path}: {e}")
            append_ledger(ledger_path, {
                "timestamp": time.time(), "model": model_id,
                "estimated_usd": per_image_cost})
            running_total += per_image_cost
            print(f"wrote {out_path} ({model_id}, ~${per_image_cost:.2f} est.) "
                  f"— ledger total ~${running_total:.2f}")
        return 0
    except ImageGenError as e:
        print(f"imagegen: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# ---------------------------------------------------------------------------
# Price/model sources (researched 2026-07-18):
#   OpenAI    https://developers.openai.com/api/docs/pricing
#   Gemini    https://ai.google.dev/gemini-api/docs/image-generation
#             https://ai.google.dev/gemini-api/docs/pricing
#   BFL FLUX  https://bfl.ai/pricing  ·  https://docs.bfl.ml/quick_start/pricing
# Model ids drift; use --list-models and the docs above as the source of truth.
# ---------------------------------------------------------------------------
