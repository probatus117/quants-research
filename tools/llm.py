"""LLM Tool   LLM .

tools/  API 
Gemini / GPT / Grok 
APIkey None  Claude fallback

KIK-686: web_search / reasoning 
  - Gemini: google_search tool  GroundingGoogle
  - GPT: reasoning_effort 4 (none/low/medium/high)
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

_ENDPOINTS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    "gpt": "https://api.openai.com/v1/chat/completions",
    "grok": "https://api.x.ai/v1/chat/completions",
}

_API_KEY_ENVS = {
    "gemini": "GEMINI_API_KEY",
    "gpt": "OPENAI_API_KEY",
    "grok": "XAI_API_KEY",
}

_VALID_PROVIDERS = set(_ENDPOINTS.keys())


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def call_llm(
    provider: str,
    model: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    timeout: int = 60,
    web_search: bool = False,
    reasoning: Optional[str] = None,
) -> Optional[str]:
    """LLM text.

    Parameters
    ----------
    provider : str
        "gemini" | "gpt" | "grok"
    model : str
        : "gemini-3-flash-preview", "gpt-5.4", "grok-4.20-0309-reasoning"
    prompt : str
         prompt
    system_prompt : str, optional
        system prompt
    timeout : int
         60
    web_search : bool
        True  Web  (KIK-686)
        - Gemini: Google Search Grounding token
        - GPT/Grok:  Responses API 
    reasoning : str, optional
        GPT :  (KIK-686)
        "none" | "low" | "medium" | "high"
        None 

    Returns
    -------
    str or None
        APIkey None
    """
    if provider not in _VALID_PROVIDERS:
        return None

    api_key = os.environ.get(_API_KEY_ENVS[provider])
    if not api_key:
        return None

    # Validate provider-specific params
    if web_search and provider != "gemini":
        print(f"[llm] WARN: web_search not supported for {provider}, ignoring", file=sys.stderr)
        web_search = False
    _VALID_REASONING = {"none", "low", "medium", "high"}
    if reasoning is not None and reasoning not in _VALID_REASONING:
        print(f"[llm] WARN: invalid reasoning '{reasoning}', using model default", file=sys.stderr)
        reasoning = None
    if reasoning is not None and provider != "gpt":
        reasoning = None  # silently ignore for non-GPT

    t0 = time.time()
    try:
        if provider == "gemini":
            result = _call_gemini(api_key, model, prompt, system_prompt, timeout, web_search)
        elif provider == "gpt":
            result = _call_openai_compatible(
                api_key, _ENDPOINTS["gpt"], model, prompt, system_prompt, timeout,
                reasoning=reasoning,
            )
        elif provider == "grok":
            result = _call_openai_compatible(
                api_key, _ENDPOINTS["grok"], model, prompt, system_prompt, timeout,
            )
        else:
            return None
    except (requests.RequestException, KeyError, json.JSONDecodeError) as exc:
        elapsed = time.time() - t0
        # Sanitize error to avoid leaking API keys in URLs
        exc_str = str(exc)
        if "key=" in exc_str.lower() or "bearer" in exc_str.lower():
            exc_str = f"{type(exc).__name__} [details redacted]"
        print(
            f"[llm] FAIL {provider}/{model} ({elapsed:.1f}s): {exc_str}",
            file=sys.stderr,
        )
        return None

    elapsed = time.time() - t0
    length = len(result) if result else 0
    tags = []
    if web_search and provider == "gemini":
        tags.append("+grounding")
    if reasoning and provider == "gpt":
        tags.append(f"+reasoning={reasoning}")
    tag_str = "".join(tags)
    print(
        f"[llm] OK {provider}/{model}{tag_str} ({elapsed:.1f}s, {length} chars)",
        file=sys.stderr,
    )
    return result


def is_provider_available(provider: str) -> bool:
    """ provider API key."""
    env_var = _API_KEY_ENVS.get(provider)
    if not env_var:
        return False
    return bool(os.environ.get(env_var))


def get_available_providers() -> list[str]:
    """provider."""
    return [p for p in _VALID_PROVIDERS if is_provider_available(p)]


# ---------------------------------------------------------------------------
# KIK-731: Gemini Deep Research re-export
# ---------------------------------------------------------------------------

try:
    from src.data.gemini_client import (  # noqa: E402
        gemini_deep_research,
        is_deep_research_enabled,
    )
    HAS_GEMINI_DR = True
except ImportError:
    HAS_GEMINI_DR = False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _call_openai_compatible(
    api_key: str,
    endpoint: str,
    model: str,
    prompt: str,
    system_prompt: Optional[str],
    timeout: int,
    reasoning: Optional[str] = None,
) -> Optional[str]:
    """OpenAI  APIGPT / Grok."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: dict = {"model": model, "messages": messages}
    if reasoning is not None:
        payload["reasoning_effort"] = reasoning

    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]


def _call_gemini(
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: Optional[str],
    timeout: int,
    web_search: bool = False,
) -> Optional[str]:
    """Google Gemini API ."""
    url = _ENDPOINTS["gemini"].format(model=model)

    payload: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
    if web_search:
        payload["tools"] = [{"google_search": {}}]

    response = requests.post(
        url,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()
    # Grounding  parts   
    try:
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        if not parts:
            return None
        texts = [p.get("text", "") for p in parts if p.get("text")]
        return "\n".join(texts) if texts else None
    except (IndexError, TypeError):
        return None


__all__ = [
    "call_llm",
    "is_provider_available",
    "get_available_providers",
]
