"""
Governed agent actions: the propose -> confirm -> execute spine for anything the chat agent
does that changes state.

The agent never mutates directly. It calls ``propose_action`` (which persists an AgentAction
in status "proposed" and returns a preview for a confirm card in the UI). Only when the user
confirms does ``execute_action`` run it - through the same governed path as any other trigger
(``enqueue_for_tool_type``), never by a tool calling another tool. Money actions reuse this
with ``capability="money"`` behind a details-verified confirmation (added in a later phase).

Every proposal expires (ACTION_TTL_SECONDS) so a stale, un-confirmed action can never fire.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.audit.logger import write_audit_log
from app.core.logging import get_logger

logger = get_logger(__name__)

ACTION_TTL_SECONDS = 900  # a proposed action must be confirmed within 15 minutes
_MODEL_VERSION = "agent_actions/1.0"

# kind -> capability. Read actions never reach here (they return data directly); everything
# routed through propose/confirm is a state change.
_ACTION_CAPABILITY = {
    "run_automation": "write",
}


class AgentActionError(Exception):
    """Raised when a proposal cannot be built or executed."""


async def propose_action(db, tenant_id: str, *, kind: str, params: dict, proposed_by: str | None) -> dict:
    """Validate and persist a proposed action. Returns the confirm-card payload. Does NOT
    change any external state - it only records intent for the user to confirm."""
    if kind not in _ACTION_CAPABILITY:
        raise AgentActionError(f"Unknown action kind: {kind!r}")

    preview, norm_params = await _build_preview(db, tenant_id, kind, params)
    now = datetime.now(UTC)
    action = await db.agentaction.create(
        data={
            "tenant_id": tenant_id,
            "kind": kind,
            "capability": _ACTION_CAPABILITY[kind],
            "params": norm_params,
            "preview": preview,
            "status": "proposed",
            "proposed_by": proposed_by,
            "expires_at": now + timedelta(seconds=ACTION_TTL_SECONDS),
        }
    )
    return {
        "action_id": action.id,
        "kind": kind,
        "capability": action.capability,
        "preview": preview,
        "requires_confirmation": True,
        "expires_at": action.expires_at.isoformat(),
    }


async def execute_action(db, tenant_id: str, action_id: str, *, confirmed_by: str | None) -> dict:
    """Execute a previously-proposed action after the user confirms it. Idempotent: a second
    confirm of the same action returns the same execution rather than firing twice."""
    action = await db.agentaction.find_first(where={"id": action_id, "tenant_id": tenant_id})
    if action is None:
        raise AgentActionError("Action not found")
    if action.status == "executed":
        return {"executed": True, "action_id": action.id, "execution_id": action.execution_id, "idempotent": True}
    if action.status != "proposed":
        raise AgentActionError(f"Action is {action.status}, cannot execute")
    if action.expires_at <= datetime.now(UTC):
        await db.agentaction.update(where={"id": action.id}, data={"status": "expired"})
        raise AgentActionError("Action expired - ask again to propose a fresh one")

    execution_id = await _execute_by_kind(db, tenant_id, action)

    await db.agentaction.update(
        where={"id": action.id},
        data={"status": "executed", "confirmed_by": confirmed_by,
              "confirmed_at": datetime.now(UTC), "execution_id": execution_id},
    )
    await write_audit_log(
        tenant_id=tenant_id, actor=f"agent:{confirmed_by or 'unknown'}",
        action=f"agent_action:{action.kind}",
        reasoning_trace={"action_id": action.id, "params": action.params, "execution_id": execution_id},
        model_version=_MODEL_VERSION, execution_id=execution_id,
    )
    return {"executed": True, "action_id": action.id, "execution_id": execution_id}


async def cancel_action(db, tenant_id: str, action_id: str) -> dict:
    """Cancel a proposed action the user declined."""
    action = await db.agentaction.find_first(where={"id": action_id, "tenant_id": tenant_id})
    if action is None:
        raise AgentActionError("Action not found")
    if action.status == "proposed":
        await db.agentaction.update(where={"id": action.id}, data={"status": "cancelled"})
    return {"cancelled": True, "action_id": action_id}


# ---------------------------------------------------------------------------
# Per-kind preview + execution
# ---------------------------------------------------------------------------

async def _build_preview(db, tenant_id: str, kind: str, params: dict) -> tuple[str, dict]:
    """Return (human preview, normalised params) for a proposal, validating referenced records."""
    if kind == "run_automation":
        tool_type = str(params.get("tool_type") or "").strip()
        if not tool_type:
            raise AgentActionError("tool_type is required")
        tool = await db.tool.find_first(where={"tenant_id": tenant_id, "type": tool_type})
        if tool is None:
            raise AgentActionError(f"No '{tool_type}' automation is deployed")
        if tool.status != "active":
            raise AgentActionError(f"The '{tool_type}' automation is paused - deploy it first")
        return (f"Run the {tool_type} automation now.", {"tool_id": tool.id, "tool_type": tool_type})
    raise AgentActionError(f"Unknown action kind: {kind!r}")


async def _execute_by_kind(db, tenant_id: str, action) -> str:
    """Execute the action through the governed dispatch path. Returns the execution id."""
    if action.kind == "run_automation":
        params = action.params if isinstance(action.params, dict) else {}
        tool = await db.tool.find_first(where={"id": params.get("tool_id"), "tenant_id": tenant_id})
        if tool is None or tool.status != "active":
            raise AgentActionError("Automation is no longer active")

        # Idempotency: one execution per confirmed action (unique tenant_id + input_ref).
        input_ref = f"agent:{action.id}"
        existing = await db.execution.find_first(
            where={"tenant_id": tenant_id, "tool_id": tool.id, "input_ref": input_ref}
        )
        if existing:
            return existing.id

        execution = await db.execution.create(
            data={"tenant_id": tenant_id, "tool_id": tool.id, "input_ref": input_ref,
                  "decision": "pending", "confidence": 0.0, "status": "queued"}
        )
        from app.core.dispatch import enqueue_for_tool_type
        from app.queue.pool import get_queue_pool
        pool = await get_queue_pool()
        await enqueue_for_tool_type(
            pool=pool, tool_type=tool.type, execution_id=execution.id,
            tenant_id=tenant_id, tool_id=tool.id, payload={},
        )
        return execution.id
    raise AgentActionError(f"Unknown action kind: {action.kind!r}")
