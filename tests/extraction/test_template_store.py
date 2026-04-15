"""Tests for TemplateStore - persistent template storage."""

import json
import pytest
import tempfile
from pathlib import Path

from ai_crawler.core.extraction.template_store import TemplateStore


class TestTemplateStoreInit:
    """TemplateStore initialization should set up template directory."""

    def test_init_with_custom_dir(self):
        """Custom template directory is used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            assert store.template_dir == Path(tmpdir)

    def test_init_creates_dir(self):
        """Template directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(f"{tmpdir}/nonexistent")
            assert store.template_dir.exists()

    def test_init_default_dir(self):
        """Default directory is set to templates folder."""
        store = TemplateStore()
        assert store.template_dir.name == "templates"


class TestTemplateStoreLoad:
    """TemplateStore.load() should load templates from disk."""

    def test_load_nonexistent_returns_none(self):
        """Loading nonexistent template returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            result = store.load("amazon", "search")
            assert result is None

    def test_load_existing_template(self):
        """Loading existing template returns its contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            store.save(
                "amazon",
                "search",
                {"site": "amazon", "page_type": "search", "title_selector": "h1"},
            )
            result = store.load("amazon", "search")
            assert result is not None
            assert result["site"] == "amazon"
            assert result["title_selector"] == "h1"

    def test_load_different_page_type(self):
        """Different page_type loads different template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            store.save("amazon", "search", {"site": "amazon", "page_type": "search"})
            store.save("amazon", "detail", {"site": "amazon", "page_type": "detail"})
            result = store.load("amazon", "detail")
            assert result["page_type"] == "detail"

    def test_load_invalid_json_returns_none(self):
        """Invalid JSON file returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            site_dir = Path(tmpdir) / "amazon"
            site_dir.mkdir()
            template_path = site_dir / "search.json"
            template_path.write_text("not valid json{")
            store = TemplateStore(tmpdir)
            result = store.load("amazon", "search")
            assert result is None


class TestTemplateStoreSave:
    """TemplateStore.save() should persist templates to disk."""

    def test_save_creates_site_directory(self):
        """Saving creates site directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            store.save("amazon", "search", {"title": "test"})
            site_dir = Path(tmpdir) / "amazon"
            assert site_dir.exists()

    def test_save_creates_file(self):
        """Saving creates template file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            store.save("amazon", "search", {"title": "test"})
            path = Path(tmpdir) / "amazon" / "search.json"
            assert path.exists()

    def test_save_includes_metadata(self):
        """Saved template includes site, page_type, and _loaded_at."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            store.save("amazon", "search", {"title": "test"})
            result = store.load("amazon", "search")
            assert result["site"] == "amazon"
            assert result["page_type"] == "search"
            assert "_loaded_at" in result

    def test_save_overwrites_existing(self):
        """Saving overwrites existing template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            store.save("amazon", "search", {"title": "first"})
            store.save("amazon", "search", {"title": "second"})
            result = store.load("amazon", "search")
            assert result["title"] == "second"


class TestTemplateStoreExists:
    """TemplateStore.exists() should check template presence."""

    def test_exists_false_for_nonexistent(self):
        """Returns False for nonexistent template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            assert store.exists("amazon", "search") is False

    def test_exists_true_after_save(self):
        """Returns True after template is saved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            store.save("amazon", "search", {"title": "test"})
            assert store.exists("amazon", "search") is True


class TestTemplateStoreDelete:
    """TemplateStore.delete() should remove templates."""

    def test_delete_removes_file(self):
        """Deleting removes template file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            store.save("amazon", "search", {"title": "test"})
            store.delete("amazon", "search")
            assert store.exists("amazon", "search") is False

    def test_delete_nonexistent_is_noop(self):
        """Deleting nonexistent template doesn't raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            store.delete("amazon", "search")


class TestTemplateStoreListSites:
    """TemplateStore.list_sites() should list all sites with templates."""

    def test_list_sites_empty(self):
        """Empty directory returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            assert store.list_sites() == []

    def test_list_sites_returns_saved_sites(self):
        """Returns all sites that have templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TemplateStore(tmpdir)
            store.save("amazon", "search", {})
            store.save("walmart", "search", {})
            sites = store.list_sites()
            assert "amazon" in sites
            assert "walmart" in sites
