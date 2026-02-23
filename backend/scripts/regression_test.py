#!/usr/bin/env python3
"""Video Agent 系统回归测试

运行: cd backend && source .venv/bin/activate && python scripts/regression_test.py
"""

import json
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, "/Users/bytedance/.cursor/skills/feature-development/scripts")
from regression_test import RegressionTest


class VideoAgentTest(RegressionTest):
    def __init__(self):
        super().__init__(api_url="http://localhost:8000")
        self.frontend_url = "http://localhost:5173"

    def run(self):
        print("=" * 60)
        print(" 回归测试 — Video Agent 系统")
        print("=" * 60)

        self._test_services()
        self._test_canvas_nodes()
        self._test_canvas_edges()
        self._test_agents()
        self._test_skills()
        self._test_edge_side_effects()
        self._test_versions()
        self._test_video_api()
        self._test_mcp_api()

    def _test_services(self):
        self.section("服务可用性")
        self.test("后端 health check", lambda: self.api_get("/health")["status"] == "ok")
        self.test("前端可访问", lambda: self.http_ok(self.frontend_url))

    def _test_canvas_nodes(self):
        self.section("画布节点")
        data = self.api_get("/api/admin/canvas/nodes")
        nodes = data["nodes"]
        types = set(n["node_type"] for n in nodes)

        self.test("画布有节点", lambda: len(nodes) > 0)
        self.test("有 agent 节点", lambda: "agent" in types)
        self.test("有 trigger 节点", lambda: "trigger" in types)
        self.test("节点有位置", lambda: all("position_x" in n for n in nodes))
        self.test("节点有 config", lambda: all("config" in n for n in nodes))

    def _test_canvas_edges(self):
        self.section("画布连线")
        data = self.api_get("/api/admin/canvas/edges")
        edges = data["edges"]
        edge_types = set(e["edge_type"] for e in edges)

        self.test("画布有边", lambda: len(edges) > 0)
        self.test("有 flow 边", lambda: "flow" in edge_types)
        self.test("有 tool 边", lambda: "tool" in edge_types)

    def _test_agents(self):
        self.section("Agent 管理")
        data = self.api_get("/api/admin/agents")
        agents = data.get("agents", [])
        ids = [a["id"] for a in agents]

        self.test("有 Agent", lambda: len(agents) > 0)
        self.test("Router", lambda: "router" in ids)
        self.test("Planner", lambda: "planner" in ids)
        self.test("Producer", lambda: "producer" in ids)
        self.test("Editor", lambda: "editor" in ids)

        planner = self.api_get("/api/admin/agents/planner")
        self.test("有 system_prompt", lambda: len(planner.get("system_prompt", "")) > 0)
        self.test("有 available_tools", lambda: isinstance(planner.get("available_tools"), list))

    def _test_skills(self):
        self.section("Skill 管理")
        data = self.api_get("/api/admin/skills")
        skills = data.get("skills", [])
        names = [s["name"] for s in skills]

        self.test("有 Skill", lambda: len(skills) > 0)
        self.test("web_search", lambda: "web_search" in names)
        self.test("generate_video_t2v", lambda: "generate_video_t2v" in names)
        self.test("有 title", lambda: all(s.get("title") for s in skills))

        content = self.api_get("/api/admin/skills/web_search/content")
        self.test("内容可读取", lambda: len(content.get("content", "")) > 0)

        files = self.api_get("/api/admin/skills/web_search/files")
        self.test("有 scripts", lambda: len(files.get("scripts", [])) > 0)

    def _test_edge_side_effects(self):
        self.section("连线副作用")
        try:
            try:
                self.api_post("/api/admin/agents", {"id": "_rt_agent", "name": "回归测试", "agent_type": "react"})
            except: pass
            try:
                self.api_post("/api/admin/canvas/nodes", {"id": "agent:_rt_agent", "node_type": "agent", "ref_id": "_rt_agent", "position_x": 0, "position_y": 0})
            except: pass

            edge = self.api_post("/api/admin/canvas/edges", {"source_id": "agent:planner", "target_id": "agent:_rt_agent", "edge_type": "tool"})
            eid = edge["id"]

            a = self.api_get("/api/admin/agents/_rt_agent")
            self.test("连线后 parent_id 设置", lambda: a.get("parent_id") == "planner")

            p = self.api_get("/api/admin/agents/planner")
            self.test("连线后 tools 包含子 Agent", lambda: "_rt_agent" in p.get("available_tools", []))

            self.api_delete(f"/api/admin/canvas/edges/{eid}")

            a2 = self.api_get("/api/admin/agents/_rt_agent")
            self.test("断线后 parent_id 清除", lambda: a2.get("parent_id") is None)

            p2 = self.api_get("/api/admin/agents/planner")
            self.test("断线后 tools 移除", lambda: "_rt_agent" not in p2.get("available_tools", []))
        finally:
            try: self.api_delete("/api/admin/canvas/nodes/agent%3A_rt_agent")
            except: pass
            try: self.api_delete("/api/admin/agents/_rt_agent")
            except: pass

    def _test_versions(self):
        self.section("版本管理")
        ver = f"_rt_{int(time.time())}"
        try:
            r = self.api_post("/api/v1/publish", {"version": ver, "description": "regression"})
            self.test("发布成功", lambda: "version" in r)
            self.test("返回节点数", lambda: r.get("nodes", 0) > 0)

            vs = self.api_get("/api/v1/versions")
            self.test("列表可获取", lambda: len(vs.get("versions", [])) > 0)

            v = next((v for v in vs["versions"] if v["version"] == ver), None)
            if v:
                self.api_delete(f"/api/v1/versions/{v['id']}")
                self.test("可删除", lambda: True)
        except Exception as e:
            self.test("版本管理", lambda: False)

    def _test_video_api(self):
        self.section("外部 Video API")
        try:
            r = self.api_post("/api/v1/video/generate", {"prompt": "regression test"})
            pid = r.get("project_id", "")
            self.test("generate 返回 project_id", lambda: len(pid) > 0)
            self.test("返回 processing", lambda: r.get("status") == "processing")
            if pid:
                c = self.api_post(f"/api/v1/video/{pid}/cancel")
                self.test("cancel 可用", lambda: c.get("status") in ("cancelled", "already_done"))
        except Exception as e:
            self.test("Video API", lambda: False)

    def _test_mcp_api(self):
        self.section("MCP API")
        self.test("列表端点", lambda: "servers" in self.api_get("/api/admin/mcp"))


if __name__ == "__main__":
    t = VideoAgentTest()
    t.run()
    ok = t.report()
    sys.exit(0 if ok else 1)
