"""Tests for backend/scripts/simulate_coach_journey.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "simulate_coach_journey.py"


def _load_script_module():
    module_name = "simulate_coach_journey"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_script_imports_without_error():
    module = _load_script_module()
    assert hasattr(module, "main")
    assert hasattr(module, "parse_args")
    assert hasattr(module, "run_coach_journey")


def test_normalize_base_url_appends_api_v1():
    module = _load_script_module()
    assert module.normalize_base_url("http://localhost:8000") == "http://localhost:8000/api/v1"
    assert (
        module.normalize_base_url("http://localhost:8000/api/v1")
        == "http://localhost:8000/api/v1"
    )


def test_parse_args_defaults():
    module = _load_script_module()
    args = module.parse_args([])
    assert args.base_url == "http://localhost:8000"
    assert args.jwt is None
    assert args.mock is False
    assert args.chesscom_username is None
    assert args.message == module.DEFAULT_MESSAGE


def test_parse_args_custom_values():
    module = _load_script_module()
    args = module.parse_args(
        [
            "--base-url",
            "http://example.com",
            "--jwt",
            "token-abc",
            "--mock",
            "--chesscom-username",
            "hikaru",
            "--message",
            "Help with tactics",
        ]
    )
    assert args.base_url == "http://example.com"
    assert args.jwt == "token-abc"
    assert args.mock is True
    assert args.chesscom_username == "hikaru"
    assert args.message == "Help with tactics"


def test_auth_headers_includes_bearer():
    module = _load_script_module()
    headers = module.auth_headers("my-jwt")
    assert headers == {"Authorization": "Bearer my-jwt"}
    assert module.auth_headers(None) == {}


def test_is_non_template_response():
    module = _load_script_module()
    assert module.is_non_template_response({"used_llm": True, "message": "x"}) is True
    assert module.is_non_template_response({"llm_provider": "ollama", "message": "x"}) is True
    assert module.is_non_template_response(
        {"used_llm": False, "message": "Custom coaching advice here."}
    ) is True
    assert module.is_non_template_response(
        {
            "used_llm": False,
            "message": module.TEMPLATE_MARKER + " Study more.",
        }
    ) is False


def test_run_coach_journey_mock_mode_exits_successfully():
    module = _load_script_module()
    success, results = module.run_coach_journey(
        api_base="http://mock.test/api/v1",
        jwt=None,
        message="How can I improve my endgames?",
        chesscom_username="mockplayer",
        mock=True,
    )
    assert success is True
    step_names = [step.name for step in results]
    assert "GET /chat/health" in step_names
    assert "POST /chat/message" in step_names
    assert all(step.passed for step in results)


def test_main_mock_mode_returns_zero(capsys):
    module = _load_script_module()
    exit_code = module.main(["--mock"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Overall: PASS" in captured.out


def test_main_without_jwt_returns_one(capsys):
    module = _load_script_module()
    exit_code = module.main([])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Sign in via Supabase, copy access_token" in captured.out
    assert "Overall: FAIL" in captured.out
