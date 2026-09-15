# argus/io/llm_client.py
"""Ported from simbi `utils/llm_client.py` @ 929d5a7, re-namespaced.

Verbatim except the logger: `utils/logger.py` is not on M7's import list, so
`get_logger` becomes stdlib `logging.getLogger`. This is the only module in
`io/` allowed to import `anthropic` (I1: the proposer's client).
"""
import asyncio
import anthropic
import logging

logger = logging.getLogger(__name__)


class AnthropicClient:

    def __init__(self, api_key: str, model: str, temperature: float = 0.0):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature

    async def complete(self, prompt: str, max_tokens: int = 4096) -> str:
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
