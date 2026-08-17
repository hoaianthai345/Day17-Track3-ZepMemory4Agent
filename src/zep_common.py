from __future__ import annotations

import json
import time
from typing import Any

from zep_cloud.client import Zep
from zep_cloud.types import Message

from .config import settings
from .privacy_guard import minimize_pii, require_memory_consent
from .utils import join_nonempty, object_to_text


def get_zep_client() -> Zep:
    if not settings.zep_api_key or settings.zep_api_key == "__USER_PROVIDED_KEY__":
        raise RuntimeError(
            "ZEP_API_KEY chưa được cấu hình hợp lệ. Hãy thay placeholder trong .env bằng key Zep Cloud."
        )
    return Zep(api_key=settings.zep_api_key)


def safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def ensure_user(client: Zep, user: dict[str, Any], reset: bool = False) -> None:
    user_id = user["user_id"]
    if reset:
        safe_call(client.user.delete, user_id=user_id)
    existing = safe_call(client.user.get, user_id=user_id)
    if existing is None:
        client.user.add(
            user_id=user_id,
            first_name=user.get("first_name", "Lab"),
            last_name=user.get("last_name", "User"),
        )


def recreate_thread(client: Zep, thread_id: str, user_id: str) -> None:
    safe_call(client.thread.delete, thread_id=thread_id)
    client.thread.create(thread_id=thread_id, user_id=user_id)


def add_messages(client: Zep, thread_id: str, raw_messages: list[dict[str, Any]]) -> None:
    messages = [
        Message(
            role=m["role"],
            name=m.get("name"),
            content=minimize_pii(m["content"]),
            created_at=m.get("created_at"),
        )
        for m in raw_messages
    ]
    client.thread.add_messages(thread_id, messages=messages)


def prime_eval_thread(client: Zep, user_id: str, thread_id: str, query: str) -> None:
    recreate_thread(client, thread_id, user_id)
    client.thread.add_messages(
        thread_id,
        messages=[Message(role="user", name="Evaluation User", content=query)],
        ignore_roles=["user"],
    )


def ensure_semantic_graph(client: Zep, graph_id: str, reset: bool = False) -> None:
    if reset:
        safe_call(client.graph.delete, graph_id=graph_id)
    existing = safe_call(client.graph.get, graph_id=graph_id)
    if existing is None:
        client.graph.create(
            graph_id=graph_id,
            name="VinUni Lab17 Domain Knowledge",
            description="Shared semantic/domain knowledge for the memory systems lab.",
        )


def add_semantic_documents(client: Zep, graph_id: str, docs: list[dict[str, Any]]) -> None:
    for doc in docs:
        payload = json.dumps(doc, ensure_ascii=False)
        client.graph.add(graph_id=graph_id, type="json", data=payload)
        summary = doc.get("summary") or payload
        client.graph.add(graph_id=graph_id, type="text", data=str(summary))


def render_graph_search(results: Any, episode_char_cap: int | None = None) -> str:
    """Render Zep graph-search results to text.

    episode_char_cap: when set, each episode's content is truncated to this many
    characters. User episodic search returns a few verbose session messages that
    can crowd out concise, marker-bearing reflections under a tight memory
    budget; capping keeps more distinct episodes within the budget. Leave None
    for semantic/domain search, whose markers sit at the end of each document.
    """
    parts: list[str] = []
    context = getattr(results, "context", None)
    if context:
        parts.append(str(context))

    for edge in getattr(results, "edges", None) or []:
        fact = getattr(edge, "fact", None)
        if fact:
            valid_at = getattr(edge, "valid_at", None)
            invalid_at = getattr(edge, "invalid_at", None)
            parts.append(f"FACT: {fact} [valid_at={valid_at}, invalid_at={invalid_at}]")

    for episode in getattr(results, "episodes", None) or []:
        content = getattr(episode, "content", None)
        metadata = getattr(episode, "metadata", None)
        if content:
            if episode_char_cap:
                content = content[:episode_char_cap]
                parts.append(f"EPISODE: {content}")
            else:
                parts.append(f"EPISODE: {content}\nmetadata={object_to_text(metadata)}")

    for node in getattr(results, "nodes", None) or []:
        name = getattr(node, "name", "")
        summary = getattr(node, "summary", "")
        parts.append(f"ENTITY: {name} - {summary}")

    for obs in getattr(results, "observations", None) or []:
        summary = getattr(obs, "summary", None)
        if summary:
            parts.append(f"OBSERVATION: {summary}")

    for item in getattr(results, "thread_summaries", None) or []:
        summary = getattr(item, "summary", None)
        if summary:
            parts.append(f"THREAD_SUMMARY: {summary}")

    return join_nonempty(parts)


def wait_for_search(
    client: Zep,
    *,
    query: str,
    expected: str,
    user_id: str | None = None,
    graph_id: str | None = None,
    timeout: int | None = None,
) -> None:
    timeout = timeout or settings.zep_poll_timeout
    deadline = time.time() + timeout
    last_text = ""
    scopes = ("episodes", "edges", "nodes")
    while time.time() < deadline:
        chunks: list[str] = []
        for scope in scopes:
            try:
                kwargs: dict[str, Any] = {"query": query, "scope": scope, "limit": 10}
                if user_id:
                    kwargs["user_id"] = user_id
                else:
                    kwargs["graph_id"] = graph_id
                results = client.graph.search(**kwargs)
                chunks.append(render_graph_search(results))
            except Exception:
                continue
        last_text = join_nonempty(chunks)
        if expected.casefold() in last_text.casefold():
            return
        time.sleep(settings.zep_poll_interval)
    raise TimeoutError(
        f"Zep ingestion/search did not become ready within {timeout}s. "
        f"query={query!r}, expected={expected!r}, last={last_text[:300]!r}"
    )


def ingest_user_stage(client: Zep, user: dict[str, Any], stage: int) -> None:
    require_memory_consent(user["user_id"])
    for session in user.get("sessions", []):
        if session["stage"] != stage:
            continue
        recreate_thread(client, session["thread_id"], user["user_id"])
        add_messages(client, session["thread_id"], session["messages"])
        probe = session.get("ready_probe")
        if probe:
            wait_for_search(
                client,
                user_id=user["user_id"],
                query=probe["query"],
                expected=probe["must_contain"],
            )
