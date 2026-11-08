"""作者：Wangyuan；日期：2026-10-29；职责：中性工具目录、受限动作编排与离线事件状态。"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable

from states import project_event


def encoded(value: Any) -> str:
    """稳定序列化，不接受非有限数。"""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def timestamp(value: str) -> datetime:
    """事件必须有明确时区。"""
    result = datetime.fromisoformat(value)
    if result.tzinfo is None: raise ValueError("事件缺少时区")
    return result.astimezone(timezone.utc)


class Catalog:
    """声明式目录；不自动发现本机工具、路径、账号或远端。"""

    def __init__(self, tools: list[dict]) -> None:
        """校验入口身份及动作白名单。"""
        self.tools = {}; self.favorites: set[str] = set(); self.recent: list[str] = []
        for tool in tools:
            identifier = tool.get("id")
            if not identifier or identifier in self.tools: raise ValueError("工具身份缺失或重复")
            if tool.get("state") not in {"available", "disabled", "placeholder"}: raise ValueError("工具状态无效")
            actions = tool.get("actions", {})
            if tool["state"] != "available" and actions: raise ValueError("不可用工具不能注册动作")
            for action, policy in actions.items():
                if not action or type(policy.get("max_input_bytes")) is not int or policy["max_input_bytes"] < 1:
                    raise ValueError("动作预算无效")
                if set(policy.get("required_fields", [])) - set(policy.get("input_fields", [])):
                    raise ValueError("必填字段须在白名单中")
            self.tools[identifier] = json.loads(encoded(tool))

    def search(self, query: str = "", category: str | None = None, favorites: bool = False) -> list[dict]:
        """按名称/简介/类别搜索，返回公开目录字段。"""
        result = []
        for tool in self.tools.values():
            if category is not None and tool.get("category") != category: continue
            if favorites and tool["id"] not in self.favorites: continue
            if query.casefold() not in " ".join(str(tool.get(k, "")) for k in ("name", "summary", "category")).casefold(): continue
            result.append({k: tool.get(k) for k in ("id", "name", "category", "summary", "state")})
        return sorted(result, key=lambda x: x["id"])

    def favorite(self, identifier: str, enabled: bool) -> None:
        """显式更新收藏，不写原工作台状态。"""
        if identifier not in self.tools: raise KeyError(identifier)
        if enabled: self.favorites.add(identifier)
        else: self.favorites.discard(identifier)

    def validate(self, identifier: str, action: str, payload: dict) -> dict:
        """最小化输入并检查动作、必填字段、字节预算；未知字段拒绝。"""
        tool = self.tools.get(identifier)
        if not tool or tool["state"] != "available" or action not in tool["actions"]: raise ValueError("工具动作未获配置授权")
        policy = tool["actions"][action]
        if not isinstance(payload, dict) or set(payload) - set(policy["input_fields"]) or set(policy.get("required_fields", [])) - set(payload): raise ValueError("动作字段不符白名单")
        if len(encoded(payload).encode()) > policy["max_input_bytes"]: raise ValueError("输入超出预算")
        return json.loads(encoded(payload))

    def execute(self, steps: list[dict], handlers: dict[tuple[str, str], Callable[[dict], dict]]) -> dict:
        """运行调用方显式注入的本地函数；先预检整计划，失败停止后续步骤。"""
        if len({x["id"] for x in steps}) != len(steps): raise ValueError("步骤身份重复")
        prepared = []
        for step in steps:
            if not isinstance(step.get("allowed_evidence",[]),list) or any(not isinstance(x,str) for x in step.get("allowed_evidence",[])):raise ValueError("证据白名单须为字符串数组")
            key = (step["tool"], step["action"])
            if key not in handlers: raise ValueError("动作没有本地适配器")
            prepared.append((step, self.validate(*key, step["input"])))
        results = []
        for step, payload in prepared:
            try:
                result = handlers[(step["tool"], step["action"])](payload)
                result = validate_result(result, step.get("allowed_evidence", []))
            except Exception as exc:
                return {"state": "failed", "steps": results, "failed_step": step["id"], "error_type": type(exc).__name__}
            results.append({"id": step["id"], "result": result})
            self.recent = [step["tool"]] + [x for x in self.recent if x != step["tool"]]
        return {"state": "completed", "steps": results}


def validate_result(result: dict, allowed_evidence: list[str]) -> dict:
    """校验固定结果合同及证据引用，不接受任意模型动作命令。"""
    if not isinstance(result, dict) or set(result) - {"text", "evidence", "warnings"} or not isinstance(result.get("text"), str): raise ValueError("结果合同无效")
    if not isinstance(allowed_evidence,list) or any(not isinstance(x,str) for x in allowed_evidence):raise ValueError("证据白名单须为字符串数组")
    references = result.get("evidence", [])
    if not isinstance(references, list) or any(not isinstance(x, str) or x not in allowed_evidence for x in references): raise ValueError("结果引用不在白名单")
    if not isinstance(result.get("warnings", []), list) or any(not isinstance(x, str) for x in result.get("warnings", [])): raise ValueError("警告格式无效")
    if len(encoded(result).encode()) > 1_000_000: raise ValueError("结果超出预算")
    return json.loads(encoded(result))


def load_modules(specs: list[dict], factories: dict[str, Callable[[], Any]]) -> dict:
    """非核心组件故障隔离；仅调用显式注入的工厂，不执行模块路径。"""
    status = {}
    for spec in specs:
        if spec["id"] in status: raise ValueError("组件身份重复")
        try:
            factories[spec["id"]]()
            status[spec["id"]] = {"state": "available"}
        except Exception as exc:
            status[spec["id"]] = {"state": "unavailable", "error_type": type(exc).__name__}
            if spec.get("essential"):
                raise RuntimeError("核心组件加载失败") from exc
    return status


class EventStore:
    """读取显式输入的事件，幂等去重、拒绝冲突并按时间形成会话快照。"""

    def __init__(self) -> None:
        """初始化空事件集，不扫描真实会话日志。"""
        self.events: dict[str, dict] = {}

    def ingest(self, event: dict) -> bool:
        """旧事件保留历史但不覆盖新状态，同身份异内容拒绝。"""
        required = {"id", "session", "agent", "timestamp", "type"}
        if required - set(event) or any(not str(event[x]) for x in required): raise ValueError("事件身份不完整")
        timestamp(event["timestamp"])
        if event["id"] in self.events:
            if encoded(self.events[event["id"]]) != encoded(event): raise ValueError("事件身份冲突")
            return False
        self.events[event["id"]] = json.loads(encoded(event)); return True

    def snapshot(self, now: str, stale_seconds: int) -> dict:
        """按会话投影状态，时效阈值显式，完成状态不因静默误变工作中。"""
        if type(stale_seconds) is not int or stale_seconds < 0: raise ValueError("过期阈值无效")
        moment = timestamp(now); latest = {}
        for event in sorted(self.events.values(), key=lambda x: (timestamp(x["timestamp"]), x["id"])):
            if timestamp(event["timestamp"]) <= moment: latest[(event["session"], event["agent"])] = event
        sessions = []
        for (session, agent), event in sorted(latest.items()):
            projected = asdict(project_event(event["type"], event.get("activity", ""), event.get("status", ""), event.get("summary", "")))
            age = (moment - timestamp(event["timestamp"])).total_seconds()
            stale = age > stale_seconds and projected["turn_status"] == "active"
            sessions.append({"session": session, "agent": agent, "projection": projected, "stale": stale, "last_event": event["id"]})
        return {"sessions": sessions, "events": len(self.events), "active": sum(x["projection"]["turn_status"] == "active" for x in sessions)}
