import dspy
from scrapy import signals

from ai_crawler.config import config


class DSPyLMExtension:
    def __init__(self, crawler):
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls(crawler)
        crawler.signals.connect(ext.engine_started, signal=signals.engine_started)
        return ext

    def engine_started(self):
        self._configure_dspy_lm()

    def _configure_dspy_lm(self):
        if not config.OPENAI_API_KEY:
            return
        if dspy.settings.lm is not None:
            return

        base_url = config.OPENAI_BASE_URL
        model = config.MODEL_NAME

        if "api.openai.com" not in base_url and not model.startswith("openai/"):
            model_str = f"openai/{model}"
        else:
            model_str = model

        lm = dspy.LM(model_str, api_key=config.OPENAI_API_KEY, base_url=base_url)
        dspy.settings.configure(lm=lm)
