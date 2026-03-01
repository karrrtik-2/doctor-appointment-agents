"""
LLM provider with integrated resilience, cost tracking, and tracing.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from config.settings import get_settings
from utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

# Ensure key is available
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    os.environ["OPENAI_API_KEY"] = openai_api_key


class CostTrackingCallback(BaseCallbackHandler):
    """LangChain callback that records token usage to cost analytics."""

    def __init__(self, tenant_id: str = "", user_id: str = "", model: str = ""):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.model = model

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            from infrastructure.metrics.cost_analytics import get_cost_analytics

            settings = get_settings()
            if not settings.cost_tracking_enabled:
                return

            usage = {}
            if response.llm_output:
                usage = response.llm_output.get("token_usage", {})

            if usage:
                get_cost_analytics().record_usage(
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    model=self.model or settings.openai_model,
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    operation="llm_invoke",
                )
        except Exception as exc:
            logger.debug("Cost tracking callback error: %s", exc)


class LLMModel:
    """LLM factory with resilience wrappers and observability."""

    def __init__(self, model_name: str | None = None):
        settings = get_settings()
        model_name = model_name or settings.openai_model
        if not model_name:
            raise ValueError("Model is not defined.")

        self.model_name = model_name
        self._settings = settings
        self.openai_model = ChatOpenAI(
            model=self.model_name,
            temperature=settings.openai_temperature,
            max_retries=settings.openai_max_retries,
            request_timeout=settings.openai_request_timeout,
        )

    def get_model(self, tenant_id: str = "", user_id: str = "") -> ChatOpenAI:
        """
        Return the model with cost-tracking callback attached.
        """
        callback = CostTrackingCallback(
            tenant_id=tenant_id,
            user_id=user_id,
            model=self.model_name,
        )
        # Return model with callback configured
        return self.openai_model.with_config(callbacks=[callback])

    def get_raw_model(self) -> ChatOpenAI:
        """Return the raw model without extra callbacks."""
        return self.openai_model


if __name__ == "__main__":
    llm_instance = LLMModel()
    llm_model = llm_instance.get_raw_model()
    response = llm_model.invoke("hi")
    print(response)