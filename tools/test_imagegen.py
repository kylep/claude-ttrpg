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


class _FakeResponse:
    def __init__(self, body_bytes: bytes, status: int = 200, headers: dict | None = None):
        self._body = body_bytes
        self.status = status
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


# ---------------------------------------------------------------------------
# env-file parsing (.env and exports.sh)
# ---------------------------------------------------------------------------

class TestEnvLoading:
    def test_dotenv_sets_missing_vars(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.delenv("FOO_TEST_VAR", raising=False)
        (tmp_path / ".env").write_text("FOO_TEST_VAR=bar\n")
        imagegen.load_dotenv(tmp_path / ".env")
        assert os.environ["FOO_TEST_VAR"] == "bar"

    def test_existing_env_wins(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.setenv("FOO_TEST_VAR", "preset")
        (tmp_path / ".env").write_text("FOO_TEST_VAR=from_dotenv\n")
        imagegen.load_dotenv(tmp_path / ".env")
        assert os.environ["FOO_TEST_VAR"] == "preset"

    def test_dotenv_strips_matching_quotes(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.delenv("FOO_TEST_VAR", raising=False)
        (tmp_path / ".env").write_text('FOO_TEST_VAR="quoted value"\n')
        imagegen.load_dotenv(tmp_path / ".env")
        assert os.environ["FOO_TEST_VAR"] == "quoted value"

    def test_missing_file_is_a_noop(self, imagegen, tmp_path):
        imagegen.load_dotenv(tmp_path / "nope.env")
        imagegen.load_exports(tmp_path / "nope.sh")

    def test_exports_strips_export_prefix(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.delenv("BAR_TEST_VAR", raising=False)
        (tmp_path / "exports.sh").write_text('export BAR_TEST_VAR="sk-abc"\n# a comment\n')
        imagegen.load_exports(tmp_path / "exports.sh")
        assert os.environ["BAR_TEST_VAR"] == "sk-abc"

    def test_exports_existing_env_wins(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.setenv("BAR_TEST_VAR", "preset")
        (tmp_path / "exports.sh").write_text("export BAR_TEST_VAR=from_file\n")
        imagegen.load_exports(tmp_path / "exports.sh")
        assert os.environ["BAR_TEST_VAR"] == "preset"

    def test_exports_strips_inline_comment_on_unquoted(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.delenv("BAR_TEST_VAR", raising=False)
        (tmp_path / "exports.sh").write_text("export BAR_TEST_VAR=sk-xyz # my key\n")
        imagegen.load_exports(tmp_path / "exports.sh")
        assert os.environ["BAR_TEST_VAR"] == "sk-xyz"


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_flagships_present_with_providers(self, imagegen):
        assert imagegen.MODELS["gpt-image-2"]["provider"] == "openai"
        assert imagegen.MODELS["gemini-3-pro-image"]["provider"] == "gemini"
        assert imagegen.MODELS["imagen-4.0-fast-generate-001"]["provider"] == "imagen"
        assert imagegen.MODELS["flux-2-pro"]["provider"] == "bfl"

    def test_every_model_has_cost_and_price(self, imagegen):
        for mid, meta in imagegen.MODELS.items():
            assert isinstance(meta["cost"], (int, float)), mid
            assert isinstance(meta["price"], str) and meta["price"], mid

    def test_default_model_is_valid(self, imagegen):
        assert imagegen.DEFAULT_MODEL in imagegen.MODELS

    def test_resolve_default(self, imagegen, monkeypatch):
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        assert imagegen.resolve_model(None) == imagegen.DEFAULT_MODEL

    def test_resolve_alias(self, imagegen, monkeypatch):
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        assert imagegen.resolve_model("nano-banana-pro") == "gemini-3-pro-image"

    def test_resolve_from_env(self, imagegen, monkeypatch):
        monkeypatch.setenv("IMAGE_MODEL", "flux-2-pro")
        assert imagegen.resolve_model(None) == "flux-2-pro"

    def test_resolve_cli_overrides_env(self, imagegen, monkeypatch):
        monkeypatch.setenv("IMAGE_MODEL", "gpt-image-2")
        assert imagegen.resolve_model("flux") == "flux-2-pro"

    def test_resolve_unknown_raises(self, imagegen):
        with pytest.raises(imagegen.ImageGenError):
            imagegen.resolve_model("dalle-99")

    def test_key_env_mapping(self, imagegen):
        assert imagegen.KEY_ENV["bfl"] == "BFL_API_KEY"
        assert imagegen.KEY_ENV["imagen"] == "GEMINI_API_KEY"


class TestSizeAspect:
    def test_parse_size_ok(self, imagegen):
        assert imagegen.parse_size("1536x1024") == (1536, 1024)

    def test_parse_size_bad_raises(self, imagegen):
        with pytest.raises(imagegen.ImageGenError):
            imagegen.parse_size("big")

    def test_nearest_aspect(self, imagegen):
        assert imagegen.nearest_aspect(1024, 1024) == "1:1"
        assert imagegen.nearest_aspect(1536, 1024) == "4:3"   # 1.5 -> closest of the label set
        assert imagegen.nearest_aspect(1920, 1080) == "16:9"
        assert imagegen.nearest_aspect(1024, 1536) == "3:4"


# ---------------------------------------------------------------------------
# Caps + ledger
# ---------------------------------------------------------------------------

class TestCaps:
    def test_max_per_run_ok(self, imagegen):
        imagegen.check_max_per_run(1, 1)

    def test_max_per_run_over_raises(self, imagegen):
        with pytest.raises(imagegen.ImageGenError, match="IMAGEGEN_MAX_PER_RUN"):
            imagegen.check_max_per_run(2, 1)

    def test_spend_cap_under_ok(self, imagegen):
        assert imagegen.check_spend_cap(1.00, 0.07, 5.00) == pytest.approx(1.07)

    def test_spend_cap_at_cap_ok(self, imagegen):
        assert imagegen.check_spend_cap(4.93, 0.07, 5.00) == pytest.approx(5.00)

    def test_spend_cap_over_raises(self, imagegen):
        with pytest.raises(imagegen.ImageGenError, match="IMAGEGEN_SPEND_CAP_USD"):
            imagegen.check_spend_cap(4.98, 0.07, 5.00)


class TestLedger:
    def test_empty_when_missing(self, imagegen, tmp_path):
        assert imagegen.load_ledger(tmp_path / "nope.json") == []
        assert imagegen.ledger_total([]) == 0

    def test_append_and_total(self, imagegen, tmp_path):
        p = tmp_path / ".imagegen-ledger.json"
        imagegen.append_ledger(p, {"timestamp": 1.0, "model": "gpt-image-2", "estimated_usd": 0.20})
        imagegen.append_ledger(p, {"timestamp": 2.0, "model": "flux-2-pro", "estimated_usd": 0.03})
        records = imagegen.load_ledger(p)
        assert len(records) == 2
        assert imagegen.ledger_total(records) == pytest.approx(0.23)

    def test_corrupt_treated_as_empty(self, imagegen, tmp_path):
        p = tmp_path / ".imagegen-ledger.json"
        p.write_text("not json")
        assert imagegen.load_ledger(p) == []


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

class TestKeys:
    def test_openai_missing_mentions_exports(self, imagegen, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(imagegen.ImageGenError) as e:
            imagegen.get_api_key("openai")
        msg = str(e.value)
        assert "OPENAI_API_KEY" in msg and "exports.sh" in msg

    def test_bfl_missing_names_bfl_key(self, imagegen, monkeypatch):
        monkeypatch.delenv("BFL_API_KEY", raising=False)
        with pytest.raises(imagegen.ImageGenError) as e:
            imagegen.get_api_key("bfl")
        assert "BFL_API_KEY" in str(e.value)

    def test_present_key_returned_stripped(self, imagegen, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "  sk-test-123  ")
        assert imagegen.get_api_key("openai") == "sk-test-123"


# ---------------------------------------------------------------------------
# build_jobs
# ---------------------------------------------------------------------------

class _Args:
    def __init__(self, prompt=None, out=None, batch=None):
        self.prompt = prompt or []
        self.out = out or []
        self.batch = batch


class TestBuildJobs:
    def test_pairs(self, imagegen):
        assert imagegen.build_jobs(_Args(["a", "b"], ["a.png", "b.png"])) == [("a", "a.png"), ("b", "b.png")]

    def test_mismatch_raises(self, imagegen):
        with pytest.raises(imagegen.ImageGenError):
            imagegen.build_jobs(_Args(["a", "b"], ["a.png"]))

    def test_batch_file(self, imagegen, tmp_path):
        bf = tmp_path / "b.json"
        bf.write_text(json.dumps([{"prompt": "a cat", "out": "cat.png"}, {"prompt": "a dog", "out": "dog.png"}]))
        assert imagegen.build_jobs(_Args(batch=str(bf))) == [("a cat", "cat.png"), ("a dog", "dog.png")]

    def test_batch_plus_pairs_combine(self, imagegen, tmp_path):
        bf = tmp_path / "b.json"
        bf.write_text(json.dumps([{"prompt": "a cat", "out": "cat.png"}]))
        assert imagegen.build_jobs(_Args(["x"], ["x.png"], str(bf))) == [("a cat", "cat.png"), ("x", "x.png")]

    def test_batch_missing_keys_raises(self, imagegen, tmp_path):
        bf = tmp_path / "b.json"
        bf.write_text(json.dumps([{"prompt": "a cat"}]))
        with pytest.raises(imagegen.ImageGenError):
            imagegen.build_jobs(_Args(batch=str(bf)))

    def test_batch_not_list_raises(self, imagegen, tmp_path):
        bf = tmp_path / "b.json"
        bf.write_text(json.dumps({"prompt": "a cat", "out": "cat.png"}))
        with pytest.raises(imagegen.ImageGenError):
            imagegen.build_jobs(_Args(batch=str(bf)))

    def test_batch_bad_json_raises(self, imagegen, tmp_path):
        bf = tmp_path / "b.json"
        bf.write_text("{not json")
        with pytest.raises(imagegen.ImageGenError):
            imagegen.build_jobs(_Args(batch=str(bf)))

    def test_batch_missing_file_raises(self, imagegen, tmp_path):
        with pytest.raises(imagegen.ImageGenError):
            imagegen.build_jobs(_Args(batch=str(tmp_path / "nope.json")))

    def test_no_jobs_empty(self, imagegen):
        assert imagegen.build_jobs(_Args()) == []


# ---------------------------------------------------------------------------
# Provider calls (simulated HTTP)
# ---------------------------------------------------------------------------

class TestOpenAI:
    def test_success(self, imagegen, monkeypatch):
        resp = json.dumps({"data": [{"b64_json": TINY_PNG_B64}]}).encode()

        def fake(req, timeout=None):
            assert req.full_url == "https://api.openai.com/v1/images/generations"
            assert req.get_header("Authorization") == "Bearer sk-test"
            return _FakeResponse(resp)

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        data, ext = imagegen.call_openai("gpt-image-2", "a cat", "1024x1024", "high", "sk-test")
        assert data == TINY_PNG_BYTES and ext == "png"

    def test_401_friendly(self, imagegen, monkeypatch):
        body = json.dumps({"error": {"message": "Incorrect API key provided"}}).encode()

        def fake(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", None, io.BytesIO(body))

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        with pytest.raises(imagegen.ImageGenError) as e:
            imagegen.call_openai("gpt-image-2", "a cat", "1024x1024", "high", "sk-bad")
        assert "API key appears invalid for openai" in str(e.value)

    def test_500_concise(self, imagegen, monkeypatch):
        def fake(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 500, "err", None, io.BytesIO(b"boom"))

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        with pytest.raises(imagegen.ImageGenError, match="HTTP 500"):
            imagegen.call_openai("gpt-image-2", "a cat", "1024x1024", "high", "sk-test")


class TestGemini:
    def test_success(self, imagegen, monkeypatch):
        resp = json.dumps({"candidates": [{"content": {"parts": [
            {"text": "here"}, {"inlineData": {"mimeType": "image/png", "data": TINY_PNG_B64}}]}}]}).encode()

        def fake(req, timeout=None):
            assert "generativelanguage.googleapis.com" in req.full_url
            assert "key=sk-test" in req.full_url and "generateContent" in req.full_url
            return _FakeResponse(resp)

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        data, ext = imagegen.call_gemini("gemini-3-pro-image", "a dog", "1:1", "sk-test")
        assert data == TINY_PNG_BYTES and ext == "png"

    def test_403_friendly(self, imagegen, monkeypatch):
        body = json.dumps({"error": {"message": "API key not valid"}}).encode()

        def fake(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", None, io.BytesIO(body))

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        with pytest.raises(imagegen.ImageGenError) as e:
            imagegen.call_gemini("gemini-3-pro-image", "a dog", "1:1", "sk-bad")
        assert "API key appears invalid for gemini" in str(e.value)

    def test_no_image_raises(self, imagegen, monkeypatch):
        resp = json.dumps({"candidates": [{"content": {"parts": [{"text": "no image"}]}}]}).encode()
        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _FakeResponse(resp))
        with pytest.raises(imagegen.ImageGenError, match="did not contain an image part"):
            imagegen.call_gemini("gemini-2.5-flash-image", "a dog", "1:1", "sk-test")


class TestImagen:
    def test_success(self, imagegen, monkeypatch):
        resp = json.dumps({"predictions": [{"bytesBase64Encoded": TINY_PNG_B64}]}).encode()

        def fake(req, timeout=None):
            assert ":predict" in req.full_url
            return _FakeResponse(resp)

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        data, ext = imagegen.call_imagen("imagen-4.0-generate-001", "a castle", "1:1", "sk-test")
        assert data == TINY_PNG_BYTES and ext == "png"


class TestBFL:
    def test_success_submit_poll_download(self, imagegen, monkeypatch):
        submit = json.dumps({"id": "req-1", "polling_url": "https://api.bfl.ai/v1/get_result?id=req-1"}).encode()
        ready = json.dumps({"status": "Ready", "result": {"sample": "https://delivery.bfl.ai/img.png"}}).encode()

        def fake(req, timeout=None):
            if req.get_method() == "POST":
                assert req.full_url == "https://api.bfl.ai/v1/flux-2-pro"
                assert req.get_header("X-key") == "sk-bfl"
                return _FakeResponse(submit)
            if "get_result" in req.full_url:
                return _FakeResponse(ready)
            # the image download
            return _FakeResponse(TINY_PNG_BYTES, headers={"Content-Type": "image/png"})

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        data, ext = imagegen.call_bfl("flux-2-pro", "a dragon", 1024, 1024, "sk-bfl")
        assert data == TINY_PNG_BYTES and ext == "png"

    def test_moderated_raises(self, imagegen, monkeypatch):
        submit = json.dumps({"id": "r", "polling_url": "https://api.bfl.ai/v1/get_result?id=r"}).encode()
        mod = json.dumps({"status": "Content Moderated"}).encode()

        def fake(req, timeout=None):
            return _FakeResponse(submit if req.get_method() == "POST" else mod)

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        with pytest.raises(imagegen.ImageGenError, match="content moderation"):
            imagegen.call_bfl("flux-2-pro", "bad", 1024, 1024, "sk-bfl")

    def test_error_status_raises(self, imagegen, monkeypatch):
        submit = json.dumps({"id": "r", "polling_url": "https://api.bfl.ai/v1/get_result?id=r"}).encode()
        err = json.dumps({"status": "Error", "detail": "kaboom"}).encode()

        def fake(req, timeout=None):
            return _FakeResponse(submit if req.get_method() == "POST" else err)

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        with pytest.raises(imagegen.ImageGenError, match="failed"):
            imagegen.call_bfl("flux-2-pro", "x", 1024, 1024, "sk-bfl")

    def test_401_on_submit_friendly(self, imagegen, monkeypatch):
        body = json.dumps({"detail": "invalid key"}).encode()

        def fake(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", None, io.BytesIO(body))

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        with pytest.raises(imagegen.ImageGenError) as e:
            imagegen.call_bfl("flux-2-pro", "x", 1024, 1024, "sk-bad")
        assert "API key appears invalid for bfl" in str(e.value)


# ---------------------------------------------------------------------------
# print_models
# ---------------------------------------------------------------------------

class TestPrintModels:
    def test_lists_default_and_all_providers(self, imagegen, capsys):
        imagegen.print_models()
        out = capsys.readouterr().out
        assert "DEFAULT" in out
        assert "gpt-image-2" in out and "flux-2-pro" in out and "gemini-3-pro-image" in out
        assert "nano-banana-pro" in out  # alias line


# ---------------------------------------------------------------------------
# main() end-to-end — sandboxed to tmp_path, no real network/files
# ---------------------------------------------------------------------------

class TestMain:
    def test_no_key_exits_1(self, imagegen, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        monkeypatch.setattr(urllib.request, "urlopen",
                            lambda req, timeout=None: (_ for _ in ()).throw(AssertionError("no network")))
        out = tmp_path / "out.png"
        code = imagegen.main(["--prompt", "a cat", "--out", str(out)], repo_root=tmp_path)
        assert code == 1 and not out.exists()
        err = capsys.readouterr().err
        assert "OPENAI_API_KEY" in err and "exports.sh" in err

    def test_success_writes_file_and_ledger(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        resp = json.dumps({"data": [{"b64_json": TINY_PNG_B64}]}).encode()
        monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _FakeResponse(resp))
        out = tmp_path / "art" / "out.png"
        code = imagegen.main(["--prompt", "a cat", "--out", str(out)], repo_root=tmp_path)
        assert code == 0 and out.read_bytes() == TINY_PNG_BYTES
        records = imagegen.load_ledger(tmp_path / ".imagegen-ledger.json")
        assert len(records) == 1
        assert records[0]["model"] == imagegen.DEFAULT_MODEL
        assert records[0]["estimated_usd"] == pytest.approx(imagegen.MODELS[imagegen.DEFAULT_MODEL]["cost"])

    def test_max_per_run_refusal(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        monkeypatch.setenv("IMAGEGEN_MAX_PER_RUN", "1")
        monkeypatch.setattr(urllib.request, "urlopen",
                            lambda req, timeout=None: (_ for _ in ()).throw(AssertionError("no network")))
        code = imagegen.main(["--prompt", "a", "--out", str(tmp_path / "a.png"),
                              "--prompt", "b", "--out", str(tmp_path / "b.png")], repo_root=tmp_path)
        assert code == 1 and not (tmp_path / "a.png").exists()

    def test_spend_cap_refusal(self, imagegen, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("IMAGE_MODEL", raising=False)
        monkeypatch.setenv("IMAGEGEN_SPEND_CAP_USD", "0.01")
        monkeypatch.setattr(urllib.request, "urlopen",
                            lambda req, timeout=None: (_ for _ in ()).throw(AssertionError("no network")))
        code = imagegen.main(["--prompt", "a cat", "--out", str(tmp_path / "out.png")], repo_root=tmp_path)
        assert code == 1 and not (tmp_path / "out.png").exists()

    def test_list_models_flag(self, imagegen, tmp_path, capsys):
        code = imagegen.main(["--list-models"], repo_root=tmp_path)
        assert code == 0
        assert "gpt-image-2" in capsys.readouterr().out

    def test_ledger_status_flag(self, imagegen, tmp_path, capsys):
        imagegen.append_ledger(tmp_path / ".imagegen-ledger.json",
                               {"timestamp": 1.0, "model": "gpt-image-2", "estimated_usd": 0.20})
        code = imagegen.main(["--ledger-status"], repo_root=tmp_path)
        assert code == 0
        out = capsys.readouterr().out
        assert "1 image" in out and "0.20" in out
