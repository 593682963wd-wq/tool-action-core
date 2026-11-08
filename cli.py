"""作者：Wangyuan；日期：2026-10-29；职责：独立离线JSON命令行入口。"""
from __future__ import annotations
import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from catalog import Catalog, EventStore, load_modules, validate_result
def run(payload: dict, output: Path) -> Any:
    """目录/事件离线处理；CLI不提供任意函数或代码执行入口。"""
    if payload["action"] == "events":
        store = EventStore()
        for event in payload["events"]: store.ingest(event)
        return store.snapshot(payload["now"], payload["stale_seconds"])
    catalog = Catalog(payload["tools"])
    if payload["action"] == "search": return catalog.search(**payload.get("args", {}))
    if payload["action"] == "validate": return catalog.validate(**payload["args"])
    if payload["action"] == "plan":
        def echo(value: dict) -> dict:
            """固定离线示例适配器，只回显明确字段。"""
            return {"text": str(value.get("text", "")), "evidence": []}
        return catalog.execute(payload["steps"], {(item["id"], "echo"): echo for item in payload["tools"] if "echo" in item.get("actions", {})})
    raise ValueError("未知动作")

def demo(output: Path) -> dict:
    """展示目录、有限动作与事件状态。"""
    tools = [{"id": "notes", "name": "文本回显", "category": "文字", "summary": "合成演示", "state": "available", "actions": {"echo": {"input_fields": ["text"], "required_fields": ["text"], "max_input_bytes": 1000}}}, {"id": "future", "name": "待接入项目", "category": "计划", "state": "placeholder", "actions": {}}]
    return {"catalog": run({"action": "search", "tools": tools}, output), "plan": run({"action": "plan", "tools": tools, "steps": [{"id": "step-1", "tool": "notes", "action": "echo", "input": {"text": "合成文本"}}]}, output), "events": run({"action": "events", "events": [{"id": "event-1", "session": "session-1", "agent": "agent-1", "timestamp": "2030-01-01T00:00:00+00:00", "type": "task_started"}], "now": "2030-01-01T00:00:01+00:00", "stale_seconds": 60}, output)}

def main() -> int:
    """运行合成演示或显式输入；错误返回非零，不访问外部服务。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["demo", "run"])
    parser.add_argument("input", nargs="?")
    parser.add_argument("--output", help="显式输出目录；默认临时目录")
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(args.output or temporary)
            output.mkdir(parents=True, exist_ok=True)
            if args.command == "demo":
                result = demo(output)
            else:
                if not args.input:
                    raise ValueError("run必须提供JSON文件")
                source = Path(args.input)
                if source.stat().st_size > 10_000_000:
                    raise ValueError("JSON文件超出预算")
                result = run(json.loads(source.read_text(encoding="utf-8")), output)
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
if __name__ == "__main__":
    raise SystemExit(main())
