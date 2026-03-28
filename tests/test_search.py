"""Tests for the search loop (search.py)."""

from __future__ import annotations

import json


from search import (
    IterationRecord,
    SearchState,
    _parse_json_response,
    _summarize_config,
    build_prompt,
    merge_config,
    write_config,
)


# ---------------------------------------------------------------------------
# Tests: Config management
# ---------------------------------------------------------------------------


class TestMergeConfig:
    def test_empty_overrides(self):
        base = {"covariates": [], "context_length": None}
        merged = merge_config(base, {})
        assert merged == base

    def test_override_field(self):
        base = {"covariates": [], "context_length": None}
        merged = merge_config(base, {"covariates": ["brent_crude"]})
        assert merged["covariates"] == ["brent_crude"]
        assert merged["context_length"] is None

    def test_add_new_field(self):
        base = {"covariates": []}
        merged = merge_config(base, {"transforms": {"cpi": "log_diff"}})
        assert merged["transforms"] == {"cpi": "log_diff"}


class TestWriteConfig:
    def test_writes_json(self, tmp_path, monkeypatch):
        import search
        monkeypatch.setattr(search, "CONFIG_DIR", tmp_path)
        monkeypatch.setattr(search, "CURRENT_CONFIG_PATH", tmp_path / "test.json")

        config = {"covariates": ["brent_crude"], "context_length": 64}
        path = write_config(config)

        loaded = json.loads(path.read_text())
        assert loaded["covariates"] == ["brent_crude"]
        assert loaded["context_length"] == 64


# ---------------------------------------------------------------------------
# Tests: JSON parsing
# ---------------------------------------------------------------------------


class TestParseJsonResponse:
    def test_plain_json(self):
        result = _parse_json_response('{"covariates": ["brent_crude"]}')
        assert result == {"covariates": ["brent_crude"]}

    def test_markdown_code_block(self):
        text = 'Here is my proposal:\n```json\n{"covariates": ["vix"]}\n```\nThis should help.'
        result = _parse_json_response(text)
        assert result == {"covariates": ["vix"]}

    def test_code_block_no_language(self):
        text = '```\n{"context_length": 64}\n```'
        result = _parse_json_response(text)
        assert result == {"context_length": 64}

    def test_json_embedded_in_text(self):
        text = 'I suggest: {"covariates": ["brent_crude"]} as the next config.'
        result = _parse_json_response(text)
        assert result == {"covariates": ["brent_crude"]}

    def test_unparseable_returns_empty(self):
        result = _parse_json_response("No JSON here at all.")
        assert result == {}


# ---------------------------------------------------------------------------
# Tests: Search state
# ---------------------------------------------------------------------------


class TestSearchState:
    def test_roundtrip_json(self):
        state = SearchState(
            iteration=5,
            best_score=2.5,
            best_config={"covariates": ["brent_crude"]},
            baseline_score=3.0,
            start_time="2026-03-28T12:00:00",
        )
        state.history.append(IterationRecord(
            iteration=1, config={}, quick_score=3.0, full_score=None,
            status="accepted", description="baseline",
            runtime_seconds=10.0, timestamp="2026-03-28T12:00:00",
        ))

        json_text = state.to_json()
        loaded = SearchState.from_json(json_text)

        assert loaded.iteration == 5
        assert loaded.best_score == 2.5
        assert loaded.best_config == {"covariates": ["brent_crude"]}
        assert len(loaded.history) == 1
        assert loaded.history[0].status == "accepted"

    def test_save_and_load(self, tmp_path, monkeypatch):
        import search
        monkeypatch.setattr(search, "RESULTS_DIR", tmp_path)
        monkeypatch.setattr(search, "SEARCH_STATE_PATH", tmp_path / "state.json")

        state = SearchState(iteration=3, best_score=2.0, start_time="now")
        state.save()

        loaded = SearchState.load()
        assert loaded is not None
        assert loaded.iteration == 3
        assert loaded.best_score == 2.0

    def test_load_missing_returns_none(self, tmp_path, monkeypatch):
        import search
        monkeypatch.setattr(search, "SEARCH_STATE_PATH", tmp_path / "nonexistent.json")
        assert SearchState.load() is None


# ---------------------------------------------------------------------------
# Tests: Prompt building
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_builds_prompts(self, tmp_path, monkeypatch):
        import search
        # Create mock program.md
        program = tmp_path / "program.md"
        program.write_text("You are a search agent.")
        monkeypatch.setattr(search, "PROGRAM_PATH", program)

        # Create mock search_space.yml
        space = tmp_path / "search_space.yml"
        space.write_text("covariates:\n  pool: [brent_crude]")
        monkeypatch.setattr(search, "SEARCH_SPACE_PATH", space)

        state = SearchState(
            iteration=2,
            best_score=2.5,
            best_config={"covariates": []},
            baseline_score=3.0,
        )

        system, user = build_prompt(state, space.read_text(), ["brent_crude", "vix"])

        assert "search agent" in system
        assert "brent_crude" in user
        assert "2.5" in user


class TestSummarizeConfig:
    def test_baseline(self):
        assert _summarize_config({}) == "baseline"

    def test_with_covariates(self):
        summary = _summarize_config({"covariates": ["brent_crude", "vix"]})
        assert "covs=" in summary

    def test_with_fine_tune(self):
        summary = _summarize_config({"fine_tune": True, "covariates": []})
        assert "ft=true" in summary
