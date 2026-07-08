import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, cast

# anthropic import for claude computer use
import anthropic
import yaml
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaTextBlock,
    BetaTextBlockParam,
    BetaToolUseBlockParam,
)

# client and model for claude compute use tool
from dotenv import load_dotenv

# from litellm import drop_params, token_counter
from litellm.router import Router

from . import context

load_dotenv()  # load API keys and local LLM settings from .env

provider = "openai"  # "openai" or "aws" or "anthropic" or "ollama" or "vllm"

prompt_dir = Path(__file__).parent.absolute() / "shop_prompts"

# Local LLM settings (used when provider is "ollama" or "vllm").
# Override via environment variables or a .env file.
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1")
OLLAMA_SLOW_CHAT_MODEL = os.getenv("OLLAMA_SLOW_CHAT_MODEL", OLLAMA_CHAT_MODEL)
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

VLLM_API_BASE = os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "dummy-key")
VLLM_CHAT_MODEL = os.getenv("VLLM_CHAT_MODEL", "Qwen/Qwen2.5-32B-Instruct")
VLLM_SLOW_CHAT_MODEL = os.getenv("VLLM_SLOW_CHAT_MODEL", VLLM_CHAT_MODEL)
VLLM_EMBEDDING_MODEL = os.getenv(
    "VLLM_EMBEDDING_MODEL", "intfloat/e5-mistral-7b-instruct"
)

chat_router = Router(
    model_list=[
        {
            "model_name": "openai",
            "litellm_params": {
                "model": "openai/gpt-5-mini",
                "reasoning_effort": "minimal",
            },
        },
        {
            "model_name": "aws",
            "litellm_params": {
                "model": "bedrock/global.anthropic.claude-haiku-4-5-20251001-v1:0",
                "thinking": {
                    "type": "disabled",
                },
            },
        },
        {
            "model_name": "anthropic",
            "litellm_params": {
                "model": "claude-sonnet-4-20250514",
            },
        },
        {
            "model_name": "openai_thinking",
            "litellm_params": {
                "model": "openai/gpt-5-mini",
                "reasoning_effort": "high",
            },
        },
        {
            "model_name": "aws_thinking",
            "litellm_params": {
                "model": "bedrock/global.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 32000,
                },
            },
        },
        {
            "model_name": "anthropic_thinking",
            "litellm_params": {
                "model": "claude-sonnet-4-20250514",
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 32000,
                },
            },
        },
        {
            "model_name": "ollama",
            "litellm_params": {
                "model": f"ollama_chat/{OLLAMA_CHAT_MODEL}",
                "api_base": OLLAMA_API_BASE,
            },
        },
        {
            "model_name": "ollama_thinking",
            "litellm_params": {
                "model": f"ollama_chat/{OLLAMA_CHAT_MODEL}",
                "api_base": OLLAMA_API_BASE,
            },
        },
        {
            "model_name": "vllm",
            "litellm_params": {
                "model": f"hosted_vllm/{VLLM_CHAT_MODEL}",
                "api_base": VLLM_API_BASE,
                "api_key": VLLM_API_KEY,
            },
        },
        {
            "model_name": "vllm_thinking",
            "litellm_params": {
                "model": f"hosted_vllm/{VLLM_CHAT_MODEL}",
                "api_base": VLLM_API_BASE,
                "api_key": VLLM_API_KEY,
            },
        },
    ]
)

slow_chat_router = Router(
    model_list=[
        {
            "model_name": "openai",
            "litellm_params": {"model": "openai/gpt-5", "reasoning_effort": "minimal"},
        },
        {
            "model_name": "aws",
            "litellm_params": {
                "model": "bedrock/global.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "thinking": {
                    "type": "disabled",
                },
            },
        },
        {
            "model_name": "anthropic",
            "litellm_params": {
                "model": "claude-sonnet-4-20250514",
            },
        },
        {
            "model_name": "openai_thinking",
            "litellm_params": {"model": "openai/gpt-5", "reasoning_effort": "high"},
        },
        {
            "model_name": "aws_thinking",
            "litellm_params": {
                "model": "bedrock/global.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 32000,
                },
            },
        },
        {
            "model_name": "anthropic_thinking",
            "litellm_params": {
                "model": "claude-sonnet-4-20250514",
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 32000,
                },
            },
        },
        {
            "model_name": "ollama",
            "litellm_params": {
                "model": f"ollama_chat/{OLLAMA_SLOW_CHAT_MODEL}",
                "api_base": OLLAMA_API_BASE,
            },
        },
        {
            "model_name": "ollama_thinking",
            "litellm_params": {
                "model": f"ollama_chat/{OLLAMA_SLOW_CHAT_MODEL}",
                "api_base": OLLAMA_API_BASE,
            },
        },
        {
            "model_name": "vllm",
            "litellm_params": {
                "model": f"hosted_vllm/{VLLM_SLOW_CHAT_MODEL}",
                "api_base": VLLM_API_BASE,
                "api_key": VLLM_API_KEY,
            },
        },
        {
            "model_name": "vllm_thinking",
            "litellm_params": {
                "model": f"hosted_vllm/{VLLM_SLOW_CHAT_MODEL}",
                "api_base": VLLM_API_BASE,
                "api_key": VLLM_API_KEY,
            },
        },
    ]
)

embed_router = Router(
    model_list=[
        {
            "model_name": "openai",
            "litellm_params": {"model": "openai/text-embedding-3-small"},
        },
        {
            "model_name": "aws",
            "litellm_params": {
                "model": "bedrock/cohere.embed-english-v3",
                "input_type": "search_document",
                "truncate": "END",
            },
        },
        {
            "model_name": "ollama",
            "litellm_params": {
                "model": f"ollama/{OLLAMA_EMBEDDING_MODEL}",
                "api_base": OLLAMA_API_BASE,
            },
        },
        {
            "model_name": "vllm",
            "litellm_params": {
                "model": f"hosted_vllm/{VLLM_EMBEDDING_MODEL}",
                "api_base": VLLM_API_BASE,
                "api_key": VLLM_API_KEY,
            },
        },
    ]
)


anthropic_client = anthropic.Anthropic()
anthropic_model = "claude-sonnet-4-20250514"


def async_retry(times=10):
    def func_wrapper(f):
        async def wrapper(*args, **kwargs):
            wait = 1
            max_wait = 5
            last_exc = None
            for _ in range(times):
                # noinspection PyBroadException
                try:
                    return await f(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    print("got exc", exc)
                    await asyncio.sleep(wait)
                    wait = min(wait * 2, max_wait)
                    pass
            if last_exc:
                raise last_exc

        return wrapper

    return func_wrapper


def retry(times=10):
    def func_wrapper(f):
        def wrapper(*args, **kwargs):
            wait = 1
            max_wait = 5
            last_exc = None
            for _ in range(times):
                # noinspection PyBroadException
                try:
                    return f(*args, **kwargs)
                except Exception as exc:
                    print("got exc", exc)
                    last_exc = exc
                    # await asyncio.sleep(wait)
                    time.sleep(wait)
                    wait = min(wait * 2, max_wait)
                    pass
            if last_exc:
                raise last_exc

        return wrapper

    return func_wrapper


def _extract_json_string(text: str) -> str:
    import regex

    # Improved pattern to match JSON objects. Note: This is still not foolproof for deeply nested or complex JSON.
    json_pattern = r"\{(?:[^{}]*|(?R))*\}"
    matches = regex.findall(json_pattern, text, regex.DOTALL)
    if matches:
        return matches[0]
    else:
        raise Exception("No JSON object found in the response")


@async_retry()
async def async_chat(
    messages,
    model="small",
    json_mode=False,
    log=True,
    max_tokens=64000,
    enable_thinking=None,
    **kwargs,
):
    """
    Async chat completion that returns the string LLM output.

    For model and provider information, check the head of /src/simulated_web_agent/agent/gpt.py.

    To add your own preferred LLM for chat completion, simply add the model into each of the liteLLM routers,
    and change the provider global variable to your custom provider.

    Args:
        model: "small" for lightweight version of the model
        json_mode: whether the result should be in json deserializable
        log: whether to log the output
        max_tokens: the maximum number of tokens
        enable_thinking: whether to enable thinking, if supported (supported by bedrock and anthropic, not supported by openai)

    Returns:
        A single string object outputted by the LLM.
    """

    if context.api_call_manager.get() and log:
        context.api_call_manager.get().request.append(messages)

    router = chat_router if model == "small" else slow_chat_router
    call_kwargs: Dict[str, Any] = dict(**kwargs)
    if enable_thinking:
        router_model = provider + "_thinking"
    else:
        router_model = provider
    if json_mode and provider in ("openai", "ollama", "vllm"):
        call_kwargs["response_format"] = {"type": "json_object"}
    # Cap max_tokens for backends with smaller context windows (e.g. local
    # models served by vLLM, which reject requests exceeding the model limit).
    max_tokens_cap = os.getenv("LLM_MAX_TOKENS")
    if max_tokens_cap:
        max_tokens = min(max_tokens, int(max_tokens_cap))
    response = await router.acompletion(
        model=router_model,
        messages=messages,
        max_tokens=max_tokens,
        drop_params=True,  # do not forward unused params, such as thinking for openai
        **call_kwargs,
        tools=None,
    )
    content = response.choices[0].message.get("content", "")

    finish_reason = response.choices[0].finish_reason
    if finish_reason != "stop":
        print("finish_reason:", finish_reason)
        print("content:", content)
        print("response:", response)
    # tokens_used = token_counter(model="openai/gpt-5-mini", text=content)
    # print("Output tokens:", tokens_used)

    if context.api_call_manager.get() and log:
        context.api_call_manager.get().response.append(content)

    if json_mode:
        # Extract JSON substring from the content
        try:
            json_str = _extract_json_string(content)
            _ = json.loads(json_str)
            return json_str
        except Exception as e:
            print(e)
            print(content)
            raise Exception("Invalid JSON in response") from e
    return content


@retry()
def chat(
    messages, model="small", enable_thinking=None, json_mode=False, **kwargs
) -> str:
    """
    Returns LLM text completion given list of formatted messages.

    Args:
        model: set to "small" to use the lightweight version of the chat model.
        messages: List of previous messages
        enable_thinking: Whether to enable thinking or not. Pass in an integer for custom thinking budget.
        json_mode: Whether to enable JSON mode or not.

    Returns:
        String output of the LLM model
    """

    router = chat_router if model == "small" else slow_chat_router
    call_kwargs: Dict[str, Any] = dict(**kwargs)
    if enable_thinking:
        call_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": enable_thinking
            if isinstance(enable_thinking, int)
            else 1024,
        }
    if json_mode and provider in ("openai", "ollama", "vllm"):
        call_kwargs["response_format"] = {"type": "json_object"}

    try:
        response = router.completion(
            model=provider,
            messages=messages,
            drop_params=True,  # do not forward unused params, such as thinking for openai
            **call_kwargs,
        )
        return response.choices[0].message["content"]
    except Exception as e:
        print(messages)
        print(e)
        raise e


async def embed_text(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using the provider configured in /src/simulated_web_agent/agent/gpt.py

    Set the EMBEDDING_PROVIDER environment variable to embed with a different
    provider than the chat provider (e.g. chat on vLLM, embeddings on Ollama).

    Returns:
        List of list[float] representing each of the embedded texts
    """
    try:
        embed_provider = os.getenv("EMBEDDING_PROVIDER") or provider
        response = await embed_router.aembedding(model=embed_provider, input=texts)
        return [e["embedding"] for e in response.data]
    except Exception as e:
        print(texts)
        print(e)
        raise e


def chat_anthropic_computer_use(
    messages,
    system: BetaTextBlockParam,
    model=anthropic_model,
    screen_width: int = 1024,
    screen_height: int = 768,
) -> (list[BetaToolUseBlockParam], list[Dict, Any]):
    """
    Given a system block and JSON messages, return the tool use block generated by the computer use tool
    """
    response = anthropic_client.beta.messages.create(
        model=model,
        max_tokens=1024,
        tools=[
            {
                "type": "computer_20250124",
                "name": "computer",
                "display_width_px": screen_width,
                "display_height_px": screen_height,
                "display_number": 1,
            },
            {
                "name": "web_browser",
                "description": "High-level browser controls",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "switch_tab",
                                "forward",
                                "back",
                                "new_tab",
                                "goto_url",
                                "close_tab",
                                "terminate",
                            ],
                        },
                        "tab_index": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Zero-based index for switch_tab and close_tab",
                        },
                        "url": {
                            "type": "string",
                            "description": "URL input, only required for goto_url and new_tab",
                        },
                    },
                    "required": ["action"],
                },
            },
        ],
        system=[system],
        messages=messages,
        betas=["computer-use-2025-01-24"],
    )

    return response


def load_prompt(prompt_name):
    p = prompt_dir / f"{prompt_name}.txt"
    return open(p, "r", encoding="utf-8").read()
