"""作者：Wangyuan；日期：2026-10-29；职责：通用代理事件状态投影。"""
from __future__ import annotations

from dataclasses import dataclass


ACTIVE_STATES = {"starting", "queued", "working", "verifying", "retrying", "waiting_user", "blocked"}
TERMINAL_STATES = {"completed", "failed", "cancelled"}
STATE_PRIORITY = {
    "failed": 5,
    "blocked": 5,
    "waiting_user": 4,
    "working": 3,
    "verifying": 3,
    "retrying": 3,
    "starting": 2,
    "queued": 2,
    "completed": 1,
    "cancelled": 1,
    "idle": 0,
    "offline": -1,
    "stale": -1,
}

STATE_LABELS = {
    "idle": "空闲",
    "queued": "排队中",
    "starting": "准备中",
    "working": "工作中",
    "verifying": "验证中",
    "waiting_user": "等待用户",
    "blocked": "已阻塞",
    "retrying": "重试中",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
    "stale": "状态未更新",
    "process_only": "进程运行，工作内容未知",
    "adapter_offline": "数据源离线",
    "offline": "离线",
}


@dataclass(frozen=True, slots=True)
class EventProjection:
    """区分工作状态、注意事项、目标与结果状态。"""
    state: str
    online_status: str
    turn_status: str
    activity: str
    attention: str
    goal_status: str
    result_status: str
    error_reason: str = ""
    waiting_reason: str = ""


def project_event(event_type: str, activity: str, status: str, summary: str) -> EventProjection:
    """把显式事件及状态投影为通用会话状态，不读取实际日志。"""
    event = (event_type or "").lower()
    explicit = (status or "").lower()
    if explicit in {"failed", "blocked", "waiting_user", "completed", "cancelled", "retrying", "verifying", "working", "queued", "starting"}:
        state = explicit
    elif event in {"session_started", "agent_spawned"}:
        state = "starting" if event == "session_started" else "queued"
    elif event in {"task_started", "task_created", "assigned"}:
        state = "queued"
    elif event in {"test_started", "review_started", "build_started", "verification_started"}:
        state = "verifying"
    elif event in {"waiting_user", "waiting_approval", "wait_agent"}:
        state = "waiting_user"
    elif event in {"blocked", "blocker_detected"}:
        state = "blocked"
    elif event in {"failed", "error", "agent_failed"}:
        state = "failed"
    elif event in {"completed", "task_complete", "turn_completed", "agent_completed", "goal_completed"}:
        state = "completed"
    elif event in {"cancelled", "agent_interrupted"}:
        state = "cancelled"
    elif event in {"retry", "retrying"}:
        state = "retrying"
    elif activity or event in {"tool_started", "function_call", "web_search", "file_edit", "heartbeat"}:
        state = "working"
    else:
        state = "idle"

    attention = "none"
    if state == "waiting_user":
        attention = "waiting_input"
    elif state == "blocked":
        attention = "blocked"
    elif state == "failed":
        attention = "error"
    turn_status = "active" if state in ACTIVE_STATES else "completed" if state in TERMINAL_STATES else "idle"
    goal_status = "complete" if event == "goal_completed" else "active" if event in {"thread_goal_updated", "task_started", "session_started"} else "unknown"
    result_status = "success" if state == "completed" else "failure" if state == "failed" else "cancelled" if state == "cancelled" else "none"
    return EventProjection(
        state=state,
        online_status="online" if state not in {"offline", "adapter_offline"} else "offline",
        turn_status=turn_status,
        activity=activity or "communicating",
        attention=attention,
        goal_status=goal_status,
        result_status=result_status,
        error_reason=summary if state in {"failed", "blocked"} else "",
        waiting_reason=summary if state == "waiting_user" else "",
    )

