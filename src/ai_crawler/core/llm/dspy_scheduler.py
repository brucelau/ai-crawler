from __future__ import annotations

import json
import logging
import pickle
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

import dspy

from ai_crawler.config import config

logger = logging.getLogger(__name__)


MODULE_CONFIGS = {
    "strategy_selector": {
        "class": "StrategySelector",
        "min_traces": 50,
        "min_new_traces": 10,
        "train_interval": 3600,
        "trainset_key": "strategy_selection",
    },
    "initial_tier_selector": {
        "class": "InitialTierSelector",
        "min_traces": 30,
        "min_new_traces": 5,
        "train_interval": 7200,
        "trainset_key": "initial_tier",
    },
    "selector_extractor": {
        "class": "SelectorExtractor",
        "min_traces": 20,
        "min_new_traces": 5,
        "train_interval": 1800,
        "trainset_key": "selector_extraction",
    },
    "block_detector": {
        "class": "BlockDetector",
        "min_traces": 30,
        "min_new_traces": 5,
        "train_interval": 3600,
        "trainset_key": "block_detection",
    },
    "threshold_optimizer": {
        "class": "ThresholdOptimizer",
        "min_traces": 20,
        "min_new_traces": 5,
        "train_interval": 1800,
        "trainset_key": "threshold_optimization",
    },
    "url_discoverer": {
        "class": "URLDiscoverer",
        "min_traces": 15,
        "min_new_traces": 3,
        "train_interval": 3600,
        "trainset_key": "url_discovery",
    },
    "human_behavior_generator": {
        "class": "HumanBehaviorGenerator",
        "min_traces": 10,
        "min_new_traces": 3,
        "train_interval": 7200,
        "trainset_key": "human_behavior",
    },
    "profile_generator": {
        "class": "ProfileGenerator",
        "min_traces": 10,
        "min_new_traces": 3,
        "train_interval": 7200,
        "trainset_key": "profile_generation",
    },
}


def configure_dspy_lm():
    if not config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")

    base_url = config.OPENAI_BASE_URL
    model = config.MODEL_NAME

    if "api.openai.com" not in base_url and not model.startswith("openai/"):
        model_str = f"openai/{model}"
    else:
        model_str = model

    lm = dspy.LM(model_str, api_key=config.OPENAI_API_KEY, base_url=base_url)
    dspy.settings.configure(lm=lm)


@dataclass
class ModuleState:
    version: int = 0
    timestamp: str = ""
    trace_count: int = 0
    last_trained_traces: int = 0


class StrategySelectorTrainer:
    def build_trainset(self, traces: list[dict]) -> list[dspy.Example]:
        examples = []
        for t in traces:
            if not t.get("success"):
                continue
            example = dspy.Example(
                site=t["site"],
                page_pattern=t["page_pattern"],
                block_type=t["block_type"],
                response_snippet=t.get("response_snippet", ""),
                attempt_history=t.get("attempt_history", []),
                recommended_strategy=t.get("recommended_strategy", {}),
                confidence=t.get("confidence", "medium"),
                reasoning=t.get("reasoning", ""),
            ).with_inputs(
                "site", "page_pattern", "block_type", "response_snippet", "attempt_history"
            )
            examples.append(example)
        return examples

    def compile(self, trainset: list[dspy.Example], max_demos: int = 8):
        from ai_crawler.core.llm.dspy_model import StrategySelector

        teleprompter = dspy.teleprompt.BootstrapFewShot(
            metric=self._metric,
            max_bootstrapped_demos=max_demos,
        )
        selector = StrategySelector()
        return teleprompter.compile(selector, trainset=trainset)

    def _metric(self, example, prediction, trace=None):
        if prediction.confidence not in ("high", "medium"):
            return 0.0
        s_pred = prediction.recommended_strategy
        s_true = example.recommended_strategy
        if isinstance(s_pred, str):
            return 0.5
        score = 0.0
        if s_pred.get("proxy") == s_true.get("proxy"):
            score += 0.4
        if s_pred.get("render") == s_true.get("render"):
            score += 0.4
        if s_pred.get("change_ua") == s_true.get("change_ua"):
            score += 0.1
        if s_pred.get("use_cookies") == s_true.get("use_cookies"):
            score += 0.1
        return min(score, 1.0)


class InitialTierSelectorTrainer:
    def build_trainset(self, traces: list[dict]) -> list[dspy.Example]:
        examples = []
        for t in traces:
            if not t.get("success"):
                continue
            # Only use traces that have initial_tier info (from successful crawls)
            if "initial_tier" not in t and "start_tier" not in t:
                continue
            start_tier = t.get("initial_tier") or t.get("start_tier", 6)
            if isinstance(start_tier, str):
                start_tier = int(start_tier)
            example = dspy.Example(
                site=t["site"],
                page_pattern=t["page_pattern"],
                difficulty_hint=t.get("difficulty_hint", ""),
                failure_history=t.get("failure_history", ""),
                start_tier=start_tier,
                confidence=t.get("confidence", "medium"),
                reasoning=t.get("reasoning", ""),
            ).with_inputs("site", "page_pattern", "difficulty_hint", "failure_history")
            examples.append(example)
        return examples

    def compile(self, trainset: list[dspy.Example], max_demos: int = 8):
        from ai_crawler.core.llm.dspy_model import InitialTierSelector

        if not trainset:
            logger.warning("No training data for initial_tier_selector, skipping")
            return None

        teleprompter = dspy.teleprompt.BootstrapFewShot(
            metric=self._metric,
            max_bootstrapped_demos=max_demos,
        )
        selector = InitialTierSelector()
        return teleprompter.compile(selector, trainset=trainset)

    def _metric(self, example, prediction, trace=None):
        pred_tier = int(prediction.start_tier) if prediction.start_tier else 0
        example_tier = int(example.start_tier) if example.start_tier else 0

        if pred_tier == example_tier:
            return 1.0
        elif abs(pred_tier - example_tier) == 1:
            return 0.5
        return 0.0


TRAINER_REGISTRY = {
    "strategy_selector": StrategySelectorTrainer(),
    "initial_tier_selector": InitialTierSelectorTrainer(),
}


def load_traces(traces_dir: str) -> list[dict]:
    traces = []
    traces_path = Path(traces_dir)
    if not traces_path.exists():
        return []
    for file in sorted(traces_path.glob("*.jsonl")):
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    traces.append(json.loads(line))
    return traces


class DSPyScheduler:
    def __init__(
        self,
        traces_dir: str = "traces",
        model_dir: str = "models",
        global_train_interval: int = 1800,
    ):
        self.traces_dir = Path(traces_dir)
        self.model_dir = Path(model_dir)
        self.global_train_interval = global_train_interval
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self._module_states: dict[str, ModuleState] = {}
        self._module_lock = Lock()
        self._running = True
        self._last_module_trained: Optional[str] = None
        self._configure_dspy_lm_done = False

    def _get_module_state(self, module_name: str) -> ModuleState:
        if module_name not in self._module_states:
            version_file = self.model_dir / f"{module_name}_version.json"
            if version_file.exists():
                with open(version_file, "r") as f:
                    data = json.load(f)
                    self._module_states[module_name] = ModuleState(
                        version=data.get("version", 0),
                        timestamp=data.get("timestamp", ""),
                        trace_count=data.get("trace_count", 0),
                        last_trained_traces=data.get("last_trained_traces", 0),
                    )
            else:
                self._module_states[module_name] = ModuleState()
        return self._module_states[module_name]

    def _save_module_state(self, module_name: str, state: ModuleState):
        version_file = self.model_dir / f"{module_name}_version.json"
        data = {
            "version": state.version,
            "timestamp": state.timestamp,
            "trace_count": state.trace_count,
            "last_trained_traces": state.last_trained_traces,
        }
        with open(version_file, "w") as f:
            json.dump(data, f, indent=2)
        self._module_states[module_name] = state

    def _configure_dspy_lm(self):
        if self._configure_dspy_lm_done:
            return
        try:
            configure_dspy_lm()
            self._configure_dspy_lm_done = True
        except Exception as e:
            logger.error(f"Failed to configure DSPy LM: {e}")
            raise

    def _get_next_module(self) -> Optional[str]:
        modules = list(MODULE_CONFIGS.keys())
        if self._last_module_trained is None:
            return modules[0]
        idx = modules.index(self._last_module_trained)
        return modules[(idx + 1) % len(modules)]

    def _should_train_module(self, module_name: str) -> tuple[bool, str]:
        cfg = MODULE_CONFIGS[module_name]
        state = self._get_module_state(module_name)
        total_traces = self._count_traces()
        new_traces = total_traces - state.last_trained_traces

        if total_traces < cfg["min_traces"]:
            return False, f"total_traces {total_traces} < {cfg['min_traces']}"

        if new_traces < cfg["min_new_traces"]:
            return False, f"new_traces {new_traces} < {cfg['min_new_traces']}"

        if state.last_trained_traces > 0:
            time_since_last = time.time() - state.timestamp
            if time_since_last < cfg["train_interval"]:
                return False, f"too soon since last training"

        return True, "ready"

    def _count_traces(self) -> int:
        if not self.traces_dir.exists():
            return 0
        count = 0
        for file in self.traces_dir.glob("*.jsonl"):
            with open(file, "r") as f:
                for line in f:
                    if line.strip():
                        count += 1
        return count

    def _train_module(self, module_name: str) -> bool:
        cfg = MODULE_CONFIGS[module_name]
        state = self._get_module_state(module_name)
        logger.info(f"Training {module_name}...")

        try:
            self._configure_dspy_lm()
        except Exception as e:
            logger.error(f"Failed to configure DSPy LM: {e}")
            return False

        traces = load_traces(str(self.traces_dir))
        if len(traces) < cfg["min_traces"]:
            logger.info(f"Not enough traces for {module_name}")
            return False

        trainer = TRAINER_REGISTRY.get(module_name)
        if not trainer:
            logger.warning(f"No trainer registered for {module_name}, skipping")
            return False

        try:
            trainset = trainer.build_trainset(traces)
            if not trainset:
                logger.info(f"No valid training examples for {module_name}")
                return False

            compiled = trainer.compile(trainset)

            model_file = self.model_dir / f"{module_name}.pkl"
            with self._module_lock:
                with open(model_file, "wb") as f:
                    pickle.dump(compiled, f)

                total_traces = self._count_traces()
                state.version += 1
                state.timestamp = datetime.utcnow().isoformat()
                state.trace_count = total_traces
                state.last_trained_traces = total_traces
                self._save_module_state(module_name, state)

            logger.info(
                f"{module_name} trained: v{state.version}, "
                f"{len(trainset)} examples, {total_traces} total traces"
            )
            return True

        except Exception as e:
            logger.error(f"Training {module_name} failed: {e}")
            return False

    def run(self):
        logger.info(
            f"DSPy Scheduler started. Interval: {self.global_train_interval}s, "
            f"Modules: {list(MODULE_CONFIGS.keys())}"
        )

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        while self._running:
            module_to_train = self._get_next_module()
            should_train, reason = self._should_train_module(module_to_train)

            if should_train:
                self._train_module(module_to_train)
                self._last_module_trained = module_to_train
            else:
                logger.debug(f"{module_to_train}: {reason}")

            time.sleep(self.global_train_interval)

        logger.info("DSPy Scheduler stopped")

    def _shutdown(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self._running = False

    def train_module(self, module_name: str) -> bool:
        if module_name not in MODULE_CONFIGS:
            logger.error(f"Unknown module: {module_name}")
            return False
        return self._train_module(module_name)

    def train_all(self) -> dict[str, bool]:
        results = {}
        for module_name in MODULE_CONFIGS:
            results[module_name] = self._train_module(module_name)
        return results

    def get_status(self) -> dict:
        status = {}
        for module_name in MODULE_CONFIGS:
            state = self._get_module_state(module_name)
            cfg = MODULE_CONFIGS[module_name]
            total_traces = self._count_traces()
            new_traces = total_traces - state.last_trained_traces
            status[module_name] = {
                "version": state.version,
                "last_trained": state.timestamp,
                "total_traces": total_traces,
                "new_traces": new_traces,
                "ready": new_traces >= cfg["min_new_traces"] and total_traces >= cfg["min_traces"],
            }
        return status


def main():
    import argparse

    parser = argparse.ArgumentParser(description="DSPy Model Training Scheduler")
    parser.add_argument("--traces-dir", default="traces", help="Directory containing trace files")
    parser.add_argument("--model-dir", default="models", help="Directory to save trained models")
    parser.add_argument(
        "--interval", type=int, default=1800, help="Training check interval in seconds"
    )
    parser.add_argument("--module", default=None, help="Train specific module only")
    parser.add_argument(
        "--train-once",
        action="store_true",
        help="Train and exit",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show training status and exit",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    scheduler = DSPyScheduler(
        traces_dir=args.traces_dir,
        model_dir=args.model_dir,
        global_train_interval=args.interval,
    )

    if args.status:
        print(json.dumps(scheduler.get_status(), indent=2))
        sys.exit(0)

    if args.train_once:
        if args.module:
            success = scheduler.train_module(args.module)
        else:
            results = scheduler.train_all()
            success = any(results.values())
            print(json.dumps(results, indent=2))
        sys.exit(0 if success else 1)

    scheduler.run()


if __name__ == "__main__":
    main()
