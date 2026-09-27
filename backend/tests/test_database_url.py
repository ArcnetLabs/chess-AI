"""Tests for DATABASE_URL validation and driver selection.

Regression guard for a deploy-breaking coupling: a bare ``postgresql://`` URL
resolved to psycopg2 on SQLAlchemy 2.0 but to psycopg v3 on 2.1, and the
unpinned ``sqlalchemy>=2.0.23`` requirement meant a fresh build picked up 2.1
and failed at ``alembic upgrade head`` with
``ModuleNotFoundError: No module named 'psycopg'``.
"""

import pytest

from app.core.database import DEFAULT_DRIVER, _validate_database_url


class TestDriverIsExplicit:
    def test_bare_postgresql_url_names_the_installed_driver(self):
        url = "postgresql://user:pass@host:6543/postgres?sslmode=require"
        assert _validate_database_url(url) == url.replace(
            "postgresql://", f"postgresql+{DEFAULT_DRIVER}://", 1
        )

    def test_heroku_style_postgres_scheme_is_normalised(self):
        url = "postgres://user:pass@host:5432/db"
        assert _validate_database_url(url).startswith(f"postgresql+{DEFAULT_DRIVER}://")

    def test_explicit_driver_is_respected(self):
        """A deliberate psycopg v3 configuration must not be rewritten."""
        url = "postgresql+psycopg://user:pass@host:5432/db"
        assert _validate_database_url(url) == url

    def test_explicit_psycopg2_is_unchanged(self):
        url = "postgresql+psycopg2://user:pass@host:5432/db"
        assert _validate_database_url(url) == url

    def test_sqlite_allowed_only_under_pytest(self, monkeypatch):
        monkeypatch.setenv("TESTING", "1")
        assert _validate_database_url("sqlite:///:memory:") == "sqlite:///:memory:"

        monkeypatch.delenv("TESTING", raising=False)
        with pytest.raises(RuntimeError, match="forbidden outside pytest"):
            _validate_database_url("sqlite:///:memory:")

    def test_missing_url_fails_fast(self):
        with pytest.raises(RuntimeError, match="not configured"):
            _validate_database_url("")

    def test_non_postgres_scheme_rejected(self):
        with pytest.raises(RuntimeError, match="Unsupported DATABASE_URL scheme"):
            _validate_database_url("mysql://user:pass@host/db")
