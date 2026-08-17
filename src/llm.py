"""Thin LLM wrapper for the demo UI chat reply.

This is the ONLY place the lab calls a generative LLM. Benchmark scoring never
uses an LLM (see LAB.md): retrieval evidence is graded deterministically. Here
Gemini only turns retrieved memory context into a grounded assistant reply so
the mini-product feels real.

OpenAI is preferred when OPENAI_API_KEY is configured; Gemini remains a fallback.
"""

from __future__ import annotations

from typing import Any

from .config import settings

SYSTEM_INSTRUCTION = (
    "You are the assistant of a personal memory agent for VinUni Lab 17. "
    "Answer the user grounded ONLY in the retrieved memory context provided. "
    "If the context does not contain the answer, say so plainly instead of "
    "inventing facts. Be concise and cite the concrete markers/ids you used. "
    "You may reply in the user's language (Vietnamese or English)."
)


def openai_available() -> bool:
    return bool(settings.openai_api_key)


def gemini_available() -> bool:
    return bool(settings.gemini_api_key)


def llm_available() -> bool:
    return openai_available() or gemini_available()


def llm_provider() -> str:
    if openai_available():
        return f"OpenAI / {settings.openai_model}"
    if gemini_available():
        return f"Gemini / {settings.gemini_model}"
    return "not configured"


def _to_contents(history: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Map chat history to google-genai `contents` turns.

    Roles: user -> "user", everything else (assistant/model) -> "model".
    """
    contents: list[dict[str, Any]] = []
    for msg in history:
        role = "user" if msg.get("role") == "user" else "model"
        text = msg.get("content", "")
        if not text:
            continue
        contents.append({"role": role, "parts": [{"text": text}]})
    return contents


def generate_reply(
    memory_context: str,
    history: list[dict[str, str]],
    user_message: str,
    *,
    model: str | None = None,
) -> str:
    """Generate a grounded assistant reply with OpenAI, or Gemini fallback.

    Raises RuntimeError if no key, and lets SDK/network errors bubble up so the
    UI can surface them. `history` should include the latest user turn or not —
    `user_message` is appended as the final user turn regardless.
    """
    grounding = (
        "Retrieved memory context for this turn:\n"
        "-------------------------------------\n"
        f"{memory_context.strip() or '(no memory retrieved)'}\n"
        "-------------------------------------\n\n"
        f"User message: {user_message}"
    )

    if settings.openai_api_key:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
        messages.extend(
            {"role": "user" if msg.get("role") == "user" else "assistant", "content": msg["content"]}
            for msg in history
            if msg.get("content")
        )
        messages.append({"role": "user", "content": grounding})
        response = client.chat.completions.create(
            model=model or settings.openai_model,
            messages=messages,
            max_completion_tokens=800,
        )
        return (response.choices[0].message.content or "").strip()

    if settings.gemini_api_key:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        contents = _to_contents(history)
        contents.append({"role": "user", "parts": [{"text": grounding}]})
        response = client.models.generate_content(
            model=model or settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.3,
                max_output_tokens=800,
            ),
        )
        return (getattr(response, "text", "") or "").strip()

    raise RuntimeError("No LLM key configured. Add OPENAI_API_KEY or GEMINI_API_KEY to .env.")
