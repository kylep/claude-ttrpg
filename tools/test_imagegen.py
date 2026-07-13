"""Tests for tools/imagegen.py.

No real network calls. HTTP is simulated by monkeypatching
urllib.request.urlopen with canned success/failure responses. Run with:

    uv run --with pytest pytest tools/test_imagegen.py

The script is a single file with no package, so it's loaded via importlib
rather than a normal import.
"""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parent / "imagegen.py"

# A valid, minimal 1x1 transparent PNG.
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
TINY_PNG_BYTES = base64.b64decode(TINY_PNG_B64)


def _load_module():
    spec = importlib.util.spec_from_file_location("imagegen", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def imagegen():
    return _load_module()


# ---------------------------------------------------------------------------
# .env parsing precedence
# ---------------------------------------------------------------------------

class TestLoadDotenv:
    def test_sets_missing_vars(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.delenv("FOO_TEST_VAR", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("FOO_TEST_VAR=bar\n")
        imagegen.load_dotenv(env_file)
        assert os.environ["FOO_TEST_VAR"] == "bar"

    def test_existing_env_wins(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.setenv("FOO_TEST_VAR", "preset")
        env_file = tmp_path / ".env"
        env_file.write_text("FOO_TEST_VAR=from_dotenv\n")
        imagegen.load_dotenv(env_file)
        assert os.environ["FOO_TEST_VAR"] == "preset"

    def test_ignores_blank_lines_and_comments(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.delenv("FOO_TEST_VAR", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("\n# a comment\n\nFOO_TEST_VAR=bar\n# trailing\n")
        imagegen.load_dotenv(env_file)
        assert os.environ["FOO_TEST_VAR"] == "bar"

    def test_strips_matching_quotes(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.delenv("FOO_TEST_VAR", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text('FOO_TEST_VAR="quoted value"\n')
        imagegen.load_dotenv(env_file)
        assert os.environ["FOO_TEST_VAR"] == "quoted value"

    def test_missing_file_is_a_noop(self, imagegen, tmp_path):
        # Should not raise.
        imagegen.load_dotenv(tmp_path / "does-not-exist.env")


# ---------------------------------------------------------------------------
# Cost table lookup
# ---------------------------------------------------------------------------

class TestCostTable:
    def test_known_models(self, imagegen):
        assert imagegen.COST_ESTIMATES_USD["openai"] == 0.07
        assert imagegen.COST_ESTIMATES_USD["gemini"] == 0.15
        assert imagegen.COST_ESTIMATES_USD["gemini-2.5-flash"] == 0.04

    def test_model_ids(self, imagegen):
        assert imagegen.MODEL_IDS["openai"] == "gpt-image-1.5"
        assert imagegen.MODEL_IDS["gemini"] == "gemini-3-pro-image-preview"
        assert imagegen.MODEL_IDS["gemini-2.5-flash"] == "gemini-2.5-flash-image"

    def test_provider_of(self, imagegen):
        assert imagegen.PROVIDER_OF["openai"] == "openai"
        assert imagegen.PROVIDER_OF["gemini"] == "gemini"
        assert imagegen.PROVIDER_OF["gemini-2.5-flash"] == "gemini"

    def test_resolve_model_default(self, imagegen, monkeypatch):
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        assert imagegen.resolve_model(None) == "openai"

    def test_resolve_model_from_env(self, imagegen, monkeypatch):
        monkeypatch.setenv("IMAGE_MODEL", "gemini-2.5-flash")
        assert imagegen.resolve_model(None) == "gemini-2.5-flash"

    def test_resolve_model_cli_override_wins(self, imagegen, monkeypatch):
        monkeypatch.setenv("IMAGE_MODEL", "openai")
        assert imagegen.resolve_model("gemini") == "gemini"

    def test_resolve_model_unknown_raises(self, imagegen):
        with pytest.raises(imagegen.ImageGenError):
            imagegen.resolve_model("dalle-99")


# ---------------------------------------------------------------------------
# Cap arithmetic
# ---------------------------------------------------------------------------

class TestMaxPerRun:
    def test_within_limit_ok(self, imagegen):
        imagegen.check_max_per_run(1, 1)  # should not raise

    def test_over_limit_raises(self, imagegen):
        with pytest.raises(imagegen.ImageGenError, match="IMAGEGEN_MAX_PER_RUN"):
            imagegen.check_max_per_run(2, 1)


class TestSpendCap:
    def test_under_cap_ok(self, imagegen):
        projected = imagegen.check_spend_cap(1.00, 0.07, 5.00)
        assert projected == pytest.approx(1.07)

    def test_exactly_at_cap_ok(self, imagegen):
        projected = imagegen.check_spend_cap(4.93, 0.07, 5.00)
        assert projected == pytest.approx(5.00)

    def test_over_cap_raises(self, imagegen):
        with pytest.raises(imagegen.ImageGenError, match="IMAGEGEN_SPEND_CAP_USD"):
            imagegen.check_spend_cap(4.98, 0.07, 5.00)

    def test_error_message_shows_totals(self, imagegen):
        with pytest.raises(imagegen.ImageGenError) as exc_info:
            imagegen.check_spend_cap(10.00, 0.15, 5.00)
        msg = str(exc_info.value)
        assert "$10.00" in msg
        assert "$5.00" in msg


class TestLedger:
    def test_empty_ledger_when_missing(self, imagegen, tmp_path):
        assert imagegen.load_ledger(tmp_path / "nope.json") == []
        assert imagegen.ledger_total([]) == 0

    def test_append_and_total(self, imagegen, tmp_path):
        ledger_path = tmp_path / ".imagegen-ledger.json"
        imagegen.append_ledger(ledger_path, {
            "timestamp": 1.0, "model": "openai", "estimated_usd": 0.07,
        })
        imagegen.append_ledger(ledger_path, {
            "timestamp": 2.0, "model": "gemini", "estimated_usd": 0.15,
        })
        records = imagegen.load_ledger(ledger_path)
        assert len(records) == 2
        assert imagegen.ledger_total(records) == pytest.approx(0.22)

    def test_corrupt_ledger_treated_as_empty(self, imagegen, tmp_path):
        ledger_path = tmp_path / ".imagegen-ledger.json"
        ledger_path.write_text("not json")
        assert imagegen.load_ledger(ledger_path) == []


# ---------------------------------------------------------------------------
# Missing-key message
# ---------------------------------------------------------------------------

class TestMissingKey:
    def test_openai_missing_key_message(self, imagegen, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(imagegen.ImageGenError) as exc_info:
            imagegen.get_api_key("openai")
        msg = str(exc_info.value)
        assert "OPENAI_API_KEY" in msg
        assert ".env.sample" in msg

    def test_gemini_missing_key_message(self, imagegen, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(imagegen.ImageGenError) as exc_info:
            imagegen.get_api_key("gemini")
        msg = str(exc_info.value)
        assert "GEMINI_API_KEY" in msg
        assert ".env.sample" in msg

    def test_present_key_returned(self, imagegen, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        assert imagegen.get_api_key("openai") == "sk-test-123"


# ---------------------------------------------------------------------------
# Batch parsing
# ---------------------------------------------------------------------------

class _Args:
    def __init__(self, prompt=None, out=None, batch=None):
        self.prompt = prompt or []
        self.out = out or []
        self.batch = batch


class TestBuildJobs:
    def test_prompt_out_pairs(self, imagegen):
        args = _Args(prompt=["a", "b"], out=["a.png", "b.png"])
        assert imagegen.build_jobs(args) == [("a", "a.png"), ("b", "b.png")]

    def test_mismatched_pairs_raises(self, imagegen):
        args = _Args(prompt=["a", "b"], out=["a.png"])
        with pytest.raises(imagegen.ImageGenError):
            imagegen.build_jobs(args)

    def test_batch_file(self, imagegen, tmp_path):
        batch_file = tmp_path / "batch.json"
        batch_file.write_text(json.dumps([
            {"prompt": "a cat", "out": "cat.png"},
            {"prompt": "a dog", "out": "dog.png"},
        ]))
        args = _Args(batch=str(batch_file))
        assert imagegen.build_jobs(args) == [("a cat", "cat.png"), ("a dog", "dog.png")]

    def test_batch_plus_prompt_out_combines(self, imagegen, tmp_path):
        batch_file = tmp_path / "batch.json"
        batch_file.write_text(json.dumps([{"prompt": "a cat", "out": "cat.png"}]))
        args = _Args(prompt=["extra"], out=["extra.png"], batch=str(batch_file))
        assert imagegen.build_jobs(args) == [("a cat", "cat.png"), ("extra", "extra.png")]

    def test_batch_entry_missing_keys_raises(self, imagegen, tmp_path):
        batch_file = tmp_path / "batch.json"
        batch_file.write_text(json.dumps([{"prompt": "a cat"}]))
        args = _Args(batch=str(batch_file))
        with pytest.raises(imagegen.ImageGenError):
            imagegen.build_jobs(args)

    def test_batch_not_a_list_raises(self, imagegen, tmp_path):
        batch_file = tmp_path / "batch.json"
        batch_file.write_text(json.dumps({"prompt": "a cat", "out": "cat.png"}))
        args = _Args(batch=str(batch_file))
        with pytest.raises(imagegen.ImageGenError):
            imagegen.build_jobs(args)

    def test_batch_invalid_json_raises(self, imagegen, tmp_path):
        batch_file = tmp_path / "batch.json"
        batch_file.write_text("{not json")
        args = _Args(batch=str(batch_file))
        with pytest.raises(imagegen.ImageGenError):
            imagegen.build_jobs(args)

    def test_batch_missing_file_raises(self, imagegen, tmp_path):
        args = _Args(batch=str(tmp_path / "nope.json"))
        with pytest.raises(imagegen.ImageGenError):
            imagegen.build_jobs(args)

    def test_no_jobs_returns_empty(self, imagegen):
        assert imagegen.build_jobs(_Args()) == []


# ---------------------------------------------------------------------------
# HTTP simulation — success and 401 paths, no real network calls
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, body_bytes: bytes):
        self._body = body_bytes

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class TestOpenAICall:
    def test_success_returns_decoded_png(self, imagegen, monkeypatch):
        response_json = json.dumps({"data": [{"b64_json": TINY_PNG_B64}]}).encode()

        def fake_urlopen(req, timeout=None):
            assert req.full_url == "https://api.openai.com/v1/images/generations"
            assert req.get_header("Authorization") == "Bearer sk-test"
            return _FakeResponse(response_json)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        result = imagegen.call_openai("a cat", "1024x1024", "sk-test")
        assert result == TINY_PNG_BYTES

    def test_401_raises_friendly_error(self, imagegen, monkeypatch):
        error_body = json.dumps({"error": {"message": "Incorrect API key provided"}}).encode()

        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 401, "Unauthorized", hdrs=None, fp=io.BytesIO(error_body)
            )

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(imagegen.ImageGenError) as exc_info:
            imagegen.call_openai("a cat", "1024x1024", "sk-bad")
        msg = str(exc_info.value)
        assert "API key appears invalid for openai" in msg
        assert "Incorrect API key provided" in msg

    def test_500_raises_concise_error(self, imagegen, monkeypatch):
        error_body = b"internal server error"

        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 500, "Server Error", hdrs=None, fp=io.BytesIO(error_body)
            )

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(imagegen.ImageGenError, match="HTTP 500"):
            imagegen.call_openai("a cat", "1024x1024", "sk-test")


class TestGeminiCall:
    def test_success_returns_decoded_png(self, imagegen, monkeypatch):
        response_json = json.dumps({
            "candidates": [{
                "content": {
                    "parts": [
                        {"text": "here you go"},
                        {"inlineData": {"mimeType": "image/png", "data": TINY_PNG_B64}},
                    ]
                }
            }]
        }).encode()

        def fake_urlopen(req, timeout=None):
            assert "generativelanguage.googleapis.com" in req.full_url
            assert "key=sk-test" in req.full_url
            return _FakeResponse(response_json)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        result = imagegen.call_gemini("gemini-2.5-flash-image", "a dog", "sk-test")
        assert result == TINY_PNG_BYTES

    def test_403_raises_friendly_error(self, imagegen, monkeypatch):
        error_body = json.dumps({"error": {"message": "API key not valid"}}).encode()

        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, 403, "Forbidden", hdrs=None, fp=io.BytesIO(error_body)
            )

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(imagegen.ImageGenError) as exc_info:
            imagegen.call_gemini("gemini-3-pro-image-preview", "a dog", "sk-bad")
        msg = str(exc_info.value)
        assert "API key appears invalid for gemini" in msg
        assert "API key not valid" in msg

    def test_no_image_part_raises(self, imagegen, monkeypatch):
        response_json = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "no image today"}]}}]
        }).encode()

        def fake_urlopen(req, timeout=None):
            return _FakeResponse(response_json)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(imagegen.ImageGenError, match="did not contain an image part"):
            imagegen.call_gemini("gemini-2.5-flash-image", "a dog", "sk-test")


# ---------------------------------------------------------------------------
# End-to-end main() — sandboxed to tmp_path, no real network/files touched
# ---------------------------------------------------------------------------

class TestMainEndToEnd:
    def test_no_key_exits_1_with_friendly_message(self, imagegen, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        out_path = tmp_path / "out.png"
        code = imagegen.main(
            ["--prompt", "a cat", "--out", str(out_path)], repo_root=tmp_path
        )
        assert code == 1
        assert not out_path.exists()
        captured = capsys.readouterr()
        assert "OPENAI_API_KEY" in captured.err
        assert ".env.sample" in captured.err

    def test_success_writes_file_and_ledger(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        response_json = json.dumps({"data": [{"b64_json": TINY_PNG_B64}]}).encode()

        def fake_urlopen(req, timeout=None):
            return _FakeResponse(response_json)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        out_path = tmp_path / "art" / "out.png"
        code = imagegen.main(
            ["--prompt", "a cat", "--out", str(out_path)], repo_root=tmp_path
        )
        assert code == 0
        assert out_path.read_bytes() == TINY_PNG_BYTES

        ledger_path = tmp_path / ".imagegen-ledger.json"
        records = imagegen.load_ledger(ledger_path)
        assert len(records) == 1
        assert records[0]["model"] == "openai"
        assert records[0]["estimated_usd"] == pytest.approx(0.07)

    def test_max_per_run_refusal(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        monkeypatch.setenv("IMAGEGEN_MAX_PER_RUN", "1")
        code = imagegen.main(
            [
                "--prompt", "a", "--out", str(tmp_path / "a.png"),
                "--prompt", "b", "--out", str(tmp_path / "b.png"),
            ],
            repo_root=tmp_path,
        )
        assert code == 1
        assert not (tmp_path / "a.png").exists()

    def test_spend_cap_refusal(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        monkeypatch.setenv("IMAGEGEN_SPEND_CAP_USD", "0.01")
        code = imagegen.main(
            ["--prompt", "a cat", "--out", str(tmp_path / "out.png")], repo_root=tmp_path
        )
        assert code == 1
        assert not (tmp_path / "out.png").exists()

    def test_ledger_status_flag(self, imagegen, tmp_path, capsys):
        ledger_path = tmp_path / ".imagegen-ledger.json"
        imagegen.append_ledger(ledger_path, {
            "timestamp": 1.0, "model": "openai", "estimated_usd": 0.07,
        })
        code = imagegen.main(["--ledger-status"], repo_root=tmp_path)
        assert code == 0
        captured = capsys.readouterr()
        assert "1 image" in captured.out
        assert "0.07" in captured.out
