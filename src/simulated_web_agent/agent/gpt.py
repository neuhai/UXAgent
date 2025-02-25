import asyncio
import json
import time
from pathlib import Path
from typing import Any

import aioboto3
import boto3
import openai
from openai.types import CreateEmbeddingResponse
from openai.types.chat import ChatCompletion
import botocore
from . import context

# client = openai.Client()
async_client = None
# client = None
client = None
# async_client = None
# embedding_model = "text-embedding-3-small"
embedding_model = "cohere.embed-english-v3"
# chat_model = "gpt-4o-mini"
prompt_dir = Path(__file__).parent.absolute() / "shop_prompts"

provider = ""

session = aioboto3.Session()


def async_retry(times=10):
    def func_wrapper(f):
        async def wrapper(*args, **kwargs):
            wait = 1
            max_wait = 5
            for _ in range(times):
                # noinspection PyBroadException
                try:
                    return await f(*args, **kwargs)
                except Exception as exc:
                    print("got exc", exc)
                    await asyncio.sleep(wait)
                    wait = min(wait * 2, max_wait)
                    pass
            raise exc

        return wrapper

    return func_wrapper


def retry(times=10):
    def func_wrapper(f):
        def wrapper(*args, **kwargs):
            wait = 1
            max_wait = 5
            exc = None
            for _ in range(times):
                # noinspection PyBroadException
                try:
                    return f(*args, **kwargs)
                except Exception as exc1:
                    exc = exc1
                    print("got exc", exc)
                    # await asyncio.sleep(wait)
                    time.sleep(wait)
                    wait = min(wait * 2, max_wait)
                    pass
            raise exc

        return wrapper

    return func_wrapper


@async_retry()
async def embed_text_bedrock(
    texts: list[str], model=embedding_model, type="search_document", **kwargs
) -> list[list[float]]:
    async with session.client("bedrock-runtime", region_name="us-east-1") as client:
        response = await client.invoke_model(
            modelId=model,
            body=json.dumps(
                {
                    "texts": texts,
                    "input_type": type,
                    "truncate": "END",
                }
            ),
        )
        result = json.loads(await response["body"].read())
        return result["embeddings"]


@async_retry()
async def async_chat_bedrock(
    messages: list[dict[str, str]],
    model,
    log=True,
    json_mode=False,
    **kwargs,
) -> ChatCompletion:
    async with session.client("bedrock-runtime", region_name="us-east-1") as client:
        if context.api_call_manager.get() and log:
            context.api_call_manager.get().request.append(messages)
        system_message = messages[0]["content"]
        messages = messages[1:]
        new_messages = []
        for message in messages:
            new_messages.append(
                {
                    "role": message["role"],
                    "content": [
                        {
                            # 'type': 'text',
                            "text": message["content"]
                        }
                    ],
                }
            )
        messages = new_messages
        response = await client.converse(
            modelId=model,
            **{
                "inferenceConfig": {
                    "maxTokens": 1000,
                },
                "messages": messages,
                "system": [{"text": system_message}],
            },
        )
        content = response["output"]["message"]["content"][0]["text"]
        if context.api_call_manager.get() and log:
            context.api_call_manager.get().response.append(content)

        if json_mode:
            # Extract JSON substring from the content
            try:
                json_str = _extract_json_string(content)
                json_obj = json.loads(json_str)
                return json_str
            except Exception as e:
                print(e)
                print(content)
                print(json_str)
                raise Exception("Invalid JSON in response") from e
        else:
            return content


def _extract_json_string(text: str) -> str:
    import regex

    # Improved pattern to match JSON objects. Note: This is still not foolproof for deeply nested or complex JSON.
    json_pattern = r"\{(?:[^{}]*|(?R))*\}"
    matches = regex.findall(json_pattern, text, regex.DOTALL)
    if matches:
        return matches[0]
    else:
        raise Exception("No JSON object found in the response")


@retry()
def chat_bedrock(messages: list[dict[str, str]], model, **kwargs) -> str:
    client = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")
    system_message = messages[0]["content"]
    messages = messages[1:]
    response = client.invoke_model(
        modelId=model,
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 5000,
                "system": system_message,
                "messages": messages,
            }
        ),
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


async def embed_text_openai(texts, model=embedding_model, **kwargs):
    try:
        global async_client
        if async_client is None:
            async_client = openai.AsyncClient()
        del kwargs["type"]
        embeds = await async_client.embeddings.create(
            input=texts, model=model, **kwargs
        )
        return [e.embedding for e in embeds.data]
    except Exception as e:
        print(texts)
        print(e)
        raise e


def chat_openai(messages, model, json_mode=False, **kwargs) -> ChatCompletion:
    try:
        global client
        if client is None:
            client = openai.Client()

        for message in messages:
            new_contents = []
            if isinstance(message["content"], str):
                new_contents.append(
                    {
                        "type": "text",
                        "text": message["content"],
                    }
                )
            elif isinstance(message["content"], list):
                for content in message["content"]:
                    if isinstance(content, dict):
                        if content["type"] == "image":
                            new_content = {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content['source']['media_type']};base64,"
                                    + content["source"]["data"]
                                },
                            }
                            new_contents.append(new_content)
                        else:
                            new_contents.append(content)
            message["content"] = new_contents
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return (
            client.chat.completions.create(model=model, messages=messages, **kwargs)
            .choices[0]
            .message.content
        )
    except Exception as e:
        print(messages)
        print(e)
        raise e


async def async_chat_openai(
    messages, model, log=True, json_mode=False, **kwargs
) -> ChatCompletion:
    try:
        global async_client
        if async_client is None:
            async_client = openai.AsyncClient()
        for message in messages:
            new_contents = []
            if isinstance(message["content"], str):
                new_contents.append(
                    {
                        "type": "text",
                        "text": message["content"],
                    }
                )
            elif isinstance(message["content"], list):
                for content in message["content"]:
                    if isinstance(content, dict):
                        if content["type"] == "image":
                            new_content = {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content['source']['media_type']};base64,"
                                    + content["source"]["data"]
                                },
                            }
                            new_contents.append(new_content)
                        else:
                            new_contents.append(content)
            message["content"] = new_contents
        if context.api_call_manager.get() and log:
            context.api_call_manager.get().request.append(messages)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await async_client.chat.completions.create(
            model=model, messages=messages, **kwargs
        )
        if context.api_call_manager.get() and log:
            context.api_call_manager.get().response.append(
                response.choices[0].message.content
            )
        return response.choices[0].message.content
    except Exception as e:
        # print(messages)
        print(e)
        raise e


async def async_chat(*args, model="small", **kwargs):
    if model == "small":
        model = {
            "openai": "gpt-4o-mini",
            "aws": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        }[provider]
    else:
        model = {
            "openai": "gpt-4o",
            "aws": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        }[provider]

    if provider == "openai":
        return await async_chat_openai(*args, model=model, **kwargs)
    else:
        return await async_chat_bedrock(*args, model=model, **kwargs)


def chat(*args, model="small", **kwargs):
    if model == "small":
        model = {
            "openai": "gpt-4o-mini",
            "aws": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        }[provider]
    else:
        model = {
            "openai": "gpt-4o",
            "aws": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        }[provider]
    if provider == "openai":
        return chat_openai(*args, model=model, **kwargs)
    else:
        return chat_bedrock(*args, model=model, **kwargs)


async def embed_text(*args, **kwargs):
    if provider == "openai":
        return await embed_text_openai(*args, **kwargs)
    else:
        return await embed_text_bedrock(*args, **kwargs)


def load_prompt(prompt_name):
    return (prompt_dir / f"{prompt_name}.txt").read_text()
