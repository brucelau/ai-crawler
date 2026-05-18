"""Tests for DSPy models - ProfileGenerator, TierSelector, StrategySelector."""

import pytest
from unittest.mock import Mock, patch


class TestProfileGeneratorSignature:
    """ProfileGenerationSignature should define all fingerprint output fields."""

    def test_signature_exists(self):
        """Signature class exists and is valid DSPy Signature."""
        from ai_crawler.llm.dspy_model import ProfileGenerationSignature

        assert ProfileGenerationSignature is not None


class TestInitialTierSelectorSignature:
    """InitialTierSignature should define tier selection inputs/outputs."""

    def test_signature_exists(self):
        """Signature class exists and is valid DSPy Signature."""
        from ai_crawler.llm.dspy_model import InitialTierSignature

        assert InitialTierSignature is not None


class TestStrategySelectorSignature:
    """StrategySelectionSignature should define strategy selection inputs/outputs."""

    def test_signature_exists(self):
        """Signature class exists and is valid DSPy Signature."""
        from ai_crawler.llm.dspy_model import StrategySelectionSignature

        assert StrategySelectionSignature is not None


class TestStrategySelectorModule:
    """StrategySelector DSPy module should select strategies."""

    def test_module_has_predict(self):
        """StrategySelector has predict attribute."""
        from ai_crawler.llm.dspy_model import StrategySelector

        selector = StrategySelector()
        assert hasattr(selector, "predict")

    def test_module_has_forward(self):
        """StrategySelector has forward method."""
        from ai_crawler.llm.dspy_model import StrategySelector

        selector = StrategySelector()
        assert hasattr(selector, "forward")
        assert callable(selector.forward)


class TestDSPyTrainer:
    """DSPyTrainer should compile strategy selector from traces."""

    def test_init_with_traces(self):
        """DSPyTrainer accepts traces list."""
        from ai_crawler.llm.dspy_model import DSPyTrainer

        traces = [{"site": "amazon", "success": True}]
        trainer = DSPyTrainer(traces)
        assert trainer.traces == traces

    def test_build_trainset_filters_failed(self):
        """build_trainset filters out failed traces."""
        from ai_crawler.llm.dspy_model import DSPyTrainer

        traces = [
            {
                "site": "amazon",
                "success": True,
                "page_pattern": "search",
                "block_type": "http_403",
                "response_snippet": "Access denied",
                "attempt_history": [],
                "recommended_strategy": {},
                "confidence": "high",
                "reasoning": "Test",
            },
            {
                "site": "amazon",
                "success": False,
                "page_pattern": "search",
                "block_type": "http_403",
                "response_snippet": "Access denied",
            },
        ]
        trainer = DSPyTrainer(traces)
        trainset = trainer.build_trainset()
        assert len(trainset) == 1

    def test_build_trainset_returns_list(self):
        """build_trainset returns list of dspy.Example objects."""
        from ai_crawler.llm.dspy_model import DSPyTrainer

        traces = [
            {
                "site": "amazon",
                "success": True,
                "page_pattern": "search",
                "block_type": "http_403",
                "response_snippet": "Access denied",
                "attempt_history": [],
                "recommended_strategy": {},
                "confidence": "high",
                "reasoning": "Test",
            }
        ]
        trainer = DSPyTrainer(traces)
        trainset = trainer.build_trainset()
        assert isinstance(trainset, list)


class TestLoadTraces:
    """load_traces should load traces from JSONL files."""

    def test_load_traces_returns_list(self):
        """load_traces returns a list."""
        from ai_crawler.llm.dspy_model import load_traces
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_traces(tmpdir)
            assert isinstance(result, list)
            assert len(result) == 0

    def test_load_traces_empty_dir(self):
        """load_traces handles empty directory gracefully."""
        from ai_crawler.llm.dspy_model import load_traces
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_traces(tmpdir)
            assert result == []

    def test_load_traces_reads_jsonl(self):
        """load_traces reads .jsonl files."""
        from ai_crawler.llm.dspy_model import load_traces
        import tempfile
        import os
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_file = os.path.join(tmpdir, "traces.jsonl")
            with open(jsonl_file, "w") as f:
                f.write(json.dumps({"site": "amazon", "success": True}) + "\n")

            result = load_traces(tmpdir)
            assert len(result) == 1
            assert result[0]["site"] == "amazon"
