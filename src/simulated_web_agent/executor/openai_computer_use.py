import json
import logging
import os
from typing import Any, Dict

import openai


logger = logging.getLogger(__name__)


class OpenAIComputerUseRunner:
    """
    Runs a high-level goal using OpenAI's native Computer Use API (computer-use-preview).

    Notes:
    - Requires access to the `computer-use-preview` model on your OpenAI account.
    - Requires `OPENAI_API_KEY` in the environment.
    - This uses OpenAI's native environment; it does NOT use Browserbase/Playwright.
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for native Computer Use.")
        # Prefer modern client if available; otherwise fall back to legacy
        try:
            from openai import OpenAI  # type: ignore

            self.client = OpenAI()
            self._mode = "responses"
        except Exception:
            # Fallback to legacy client
            self.client = openai.Client()
            self._mode = "chat_completions"

    def run(self, persona: str, goal: str, target_url: str | None = None) -> Dict[str, Any]:
        """
        Execute a high-level goal using native Computer Use.
        Returns a dict with raw response payload for inspection.
        """
        instruction = {
            "persona": persona,
            "goal": goal,
            "target_url": target_url,
        }

        try:
            if self._mode == "responses":
                # Attempt Responses API call (modern SDK)
                from openai import OpenAI  # noqa: F401

                resp = self.client.responses.create(
                    model="computer-use-preview",
                    input=json.dumps(instruction),
                    truncation="auto",
                )
                # Serialize best-effort
                try:
                    payload = resp.model_dump()
                except Exception:
                    payload = json.loads(json.dumps(resp, default=str))
                return {"success": True, "provider": "openai", "api": "responses", "payload": payload}
            else:
                # Fallback: try chat completions with model name (may fail if unsupported)
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are OpenAI's native Computer Use agent. Execute the user's goal entirely in your "
                            "managed environment and return a concise status summary when done."
                        ),
                    },
                    {"role": "user", "content": json.dumps(instruction)},
                ]
                resp = self.client.chat.completions.create(model="computer-use-preview", messages=messages)
                content = resp.choices[0].message.content
                return {
                    "success": True,
                    "provider": "openai",
                    "api": "chat_completions",
                    "payload": {"text": content},
                }
        except Exception as e:
            logger.error(f"OpenAI Computer Use error: {e}")
            return {"success": False, "error": str(e)}


