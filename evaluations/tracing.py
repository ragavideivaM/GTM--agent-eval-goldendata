"""LangSmith tracing helpers for reproducible evaluation cases."""

from collections.abc import Callable, Mapping
from contextvars import ContextVar, Token
from typing import Any, TypeVar

from config import Settings


ResultT = TypeVar("ResultT")
_active_trace: ContextVar[Any | None] = ContextVar("active_langsmith_trace", default=None)


def build_trace_metadata(
    *,
    case_id: str,
    dataset_version: str,
    run_name: str,
    prompt_version: str,
    expected_output: Mapping[str, Any] | None = None,
    content_format: str = "content_suite",
) -> dict[str, Any]:
    """Build stable, non-secret metadata shared by baseline and improved runs."""
    return {
        "case_id": case_id,
        "dataset_version": dataset_version,
        "run_name": run_name,
        "prompt_version": prompt_version,
        "content_format": content_format,
        "expected_output": dict(expected_output or {}),
    }


def trace_eval_case(
    operation: Callable[[], ResultT],
    *,
    settings: Settings,
    case_id: str,
    dataset_version: str,
    run_name: str,
    prompt_version: str,
    inputs: Mapping[str, Any],
    expected_output: Mapping[str, Any] | None = None,
    content_format: str = "content_suite",
) -> ResultT:
    """Run one evaluation case under a LangSmith root trace when enabled."""
    if not settings.langsmith_tracing:
        return operation()

    from langsmith import Client
    from langsmith.run_trees import RunTree

    metadata = build_trace_metadata(
        case_id=case_id,
        dataset_version=dataset_version,
        run_name=run_name,
        prompt_version=prompt_version,
        expected_output=expected_output,
        content_format=content_format,
    )
    client = Client(
        api_key=settings.langsmith_api_key or None,
        api_url=settings.langsmith_endpoint,
    )
    trace = RunTree(
        name=run_name,
        run_type="chain",
        inputs=dict(inputs),
        project_name=settings.langsmith_project,
        client=client,
        extra={"metadata": metadata},
    )
    trace.post()
    trace_token: Token[Any] = _active_trace.set(trace)
    try:
        result = operation()
    except Exception as exc:
        trace.end(error=str(exc))
        trace.patch()
        raise
    finally:
        _active_trace.reset(trace_token)
    trace.end(outputs={"result": result})
    trace.patch()
    return result


def trace_child_call(
    operation: Callable[[], ResultT],
    *,
    name: str,
    inputs: Mapping[str, Any],
) -> ResultT:
    """Trace a child operation when it runs inside an evaluation case."""
    parent = _active_trace.get()
    if parent is None:
        return operation()

    child = parent.create_child(
        name=name,
        run_type="llm",
        inputs=dict(inputs),
    )
    child.post()
    try:
        result = operation()
    except Exception as exc:
        child.end(error=str(exc))
        child.patch()
        raise
    child.end(outputs={"result": result})
    child.patch()
    return result