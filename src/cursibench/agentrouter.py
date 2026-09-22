"""OpenAI Responses-compatible researcher calls through AgentRouterHub."""

import json
import os
from urllib import request


MODEL_CHOICES = ("gpt-6-astra", "gpt-5.6-sol")


def responses_call(prompt: str, model: str = "gpt-6-astra", max_output_tokens: int = 900) -> str:
    if model not in MODEL_CHOICES:
        raise ValueError(f"model must be one of {MODEL_CHOICES}")
    key = os.environ.get("OPENAI_API_KEY")
    base = os.environ.get("OPENAI_BASE_URL", "https://sub2api.agentrouterhub.com").rstrip("/")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    payload = json.dumps({"model": model, "input": prompt, "max_output_tokens": max_output_tokens}).encode()
    req = request.Request(
        base + "/v1/responses",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "cua-rsibench/0.2",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=120) as response:
        body = json.loads(response.read())
    if body.get("error"):
        raise RuntimeError(str(body["error"]))
    return "\n".join(content["text"] for item in body.get("output", []) for content in item.get("content", []) if content.get("text")).strip()
