# 离线工具目录、受限动作与事件投影

作者：Wangyuan · 2026-10-29

本项目源码采用 MIT 许可证，见 LICENSE；第三方依赖仍适用各自上游许可。

## 可用能力

- 显式中性工具注册表、状态/分类/搜索/收藏；占位工具不注册执行动作。
- 动作白名单、必填/未知字段检查、输入字节预算、整计划预检、固定结果合同、证据引用白名单；本地适配器依赖注入。
- 可选模块故障隔离与核心失败阻断；不根据字符串导入任意模块。
- 通用会话/任务/工具事件状态投影、幂等事件及冲突拒绝、按事件时间投影、活动过期状态；只读取显式事件。

## 运行

Python 3.11+。依赖仅为标准库，或 requirements.txt 明确列出的开源解析库。程序默认不联网；安装依赖时由包管理器下载。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -B cli.py demo
python3 -B cli.py demo --output demo-output
python3 -B cli.py run example.json --output demo-output
python3 -B -m unittest discover -s tests -v
```

演示数据从零生成；默认临时目录会在命令结束时释放。需要保留文件或数据库时必须指定 --output，输入与输出目录应由使用者自行控制。JSON输出到标准输出，参数错误返回非零状态。

## 输入与输出

动作：`search`、`validate`、`plan`、`events`；库接口 `Catalog`、`EventStore`、`load_modules`。每个动作参数名称对应核心文件中的同名函数/方法签名，公共接口有类型标注及中文说明。通用调用格式是 action 与 args；目录、收集模块另接受 tools/events/contract 等顶层显式合同。

```json
{
  "action": "events",
  "events": [
    {
      "id": "event-1",
      "session": "session-1",
      "agent": "agent-1",
      "timestamp": "2030-01-01T00:00:00+00:00",
      "type": "task_started"
    }
  ],
  "now": "2030-01-01T00:01:00+00:00",
  "stale_seconds": 30
}
```

CLI的plan只提供固定echo演示适配器；库允许调用方显式注入自己的本地函数。策略不是恶意Python代码沙箱，禁止将不可信代码当适配器。收藏和事件投影为进程内数据；长期保存由调用方显式导出JSON。

## 保留边界

旧工具地址/URL、组织目录/头像/外链、模型提供商和钥匙串、私人日志/进程发现、原UI与真实会话适配器均未包含。原外链或占位入口没有独立算法，未包装成虚构项目。

只保留通用流程与算法；这是经过提取/重构的独立工具或组件集合，并不声称完整迁移原应用、原业务质量或生产验收。源码来源、哈希与原入口映射保存在本地私有审计台账，不随此目录分发。

## 验证

tests/仅使用合成数据与临时文件，覆盖主流程、空/缺失、身份冲突和关键异常；cli.py demo可独立复现完整示例。未运行真实业务数据、联网/正式发送、原系统回归或生产部署。本项目为CLI/库，不包含Web UI。

## 2026-11-08 候选修订

- 白名单必须字符串数组；所有步骤在调用适配器之前预检。

使用包内合成样例复跑；发布集合根目录的 `verify_release.py --project workflow-tool-catalog` 会依次执行测试和首次使用命令。原有版本的测试计数属于当时记录，本轮汇总以集合验证报告为准。
