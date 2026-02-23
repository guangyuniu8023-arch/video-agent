"""端到端测试脚本 — 验证 Sprint 0~5 全链路功能

用法: python scripts/test_e2e.py [--base-url http://localhost:8000]
"""

import asyncio
import json
import sys
import time
import httpx
import websockets


BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


async def test_health():
    """测试 1: 健康检查"""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        print(f"  ✓ Health: {data}")
        return data


async def test_agents():
    """测试 2: Agent 列表"""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/api/admin/agents")
        assert r.status_code == 200
        agents = r.json()["agents"]
        agent_ids = [a["id"] for a in agents]
        assert "router" in agent_ids
        assert "planner" in agent_ids
        assert "producer" in agent_ids
        assert "editor" in agent_ids
        assert "quality_gate" in agent_ids
        assert "human_feedback" in agent_ids
        print(f"  ✓ Agents: {len(agents)} registered ({', '.join(agent_ids)})")
        return agents


async def test_tools():
    """测试 3: 工具列表"""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/api/admin/tools")
        assert r.status_code == 200
        tools = r.json()["tools"]
        tool_names = [t["name"] for t in tools]
        assert "seedance_t2v" in tool_names
        assert "ffmpeg_trim" in tool_names
        print(f"  ✓ Tools: {len(tools)} registered")
        return tools


async def test_prompt_crud():
    """测试 4: Prompt 读取/更新/重置"""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/api/admin/agents/planner/prompt")
        assert r.status_code == 200
        original = r.json()["prompt"]
        assert len(original) > 50

        test_prompt = original + "\n\n# E2E Test Marker"
        r = await client.put(
            f"{BASE_URL}/api/admin/agents/planner/prompt",
            json={"prompt": test_prompt},
        )
        assert r.status_code == 200

        r = await client.get(f"{BASE_URL}/api/admin/agents/planner/prompt")
        assert "E2E Test Marker" in r.json()["prompt"]

        r = await client.post(f"{BASE_URL}/api/admin/agents/planner/prompt/reset")
        assert r.status_code == 200
        assert "E2E Test Marker" not in r.json()["prompt"]

        print("  ✓ Prompt CRUD: read/update/reset")


async def test_prompt_versions():
    """测试 5: Prompt 版本历史"""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/api/admin/agents/planner/versions")
        assert r.status_code == 200
        versions = r.json()["versions"]
        print(f"  ✓ Prompt versions: {len(versions)} versions")


async def test_tool_management():
    """测试 6: 工具管理"""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/api/admin/agents/planner/tools")
        assert r.status_code == 200
        data = r.json()
        assert "all_tools" in data
        assert "current_tools" in data
        print(f"  ✓ Tool management: {len(data['current_tools'])} current, {len(data['all_tools'])} available")


async def test_routing_rules():
    """测试 7: 路由规则 CRUD"""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/api/admin/routes",
            json={
                "name": "E2E Test Rule",
                "target_type": "skip_to_producer",
                "match_description": "E2E 测试规则",
                "enabled": False,
            },
        )
        assert r.status_code == 200
        rule_id = r.json()["id"]

        r = await client.get(f"{BASE_URL}/api/admin/routes")
        assert r.status_code == 200
        rules = r.json()["rules"]
        assert any(r["id"] == rule_id for r in rules)

        r = await client.patch(
            f"{BASE_URL}/api/admin/routes/{rule_id}/toggle",
            json={"enabled": True},
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is True

        r = await client.delete(f"{BASE_URL}/api/admin/routes/{rule_id}")
        assert r.status_code == 200

        print("  ✓ Routing rules: create/list/toggle/delete")


async def test_skills():
    """测试 8: Skill 注册表"""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/api/admin/skills")
        assert r.status_code == 200
        skills = r.json()["skills"]
        skill_names = [s["name"] for s in skills]
        print(f"  ✓ Skills: {len(skills)} registered ({', '.join(skill_names)})")


async def test_websocket():
    """测试 9: WebSocket 连接 + ping/pong"""
    try:
        async with websockets.connect(f"{WS_URL}/ws/e2e-test", open_timeout=5) as ws:
            await ws.send(json.dumps({"type": "ping"}))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            assert data["type"] == "pong"
            print("  ✓ WebSocket: ping/pong")
    except Exception as e:
        print(f"  ✗ WebSocket failed: {e}")


async def test_workflow_start():
    """测试 10: 启动工作流 (不等待完成)"""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/api/chat/start",
            json={"message": "帮我做一个5秒的测试视频", "project_id": "e2e-test"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["project_id"] == "e2e-test"
        assert data["status"] in ("started", "already_running")

        await asyncio.sleep(1)

        r = await client.get(f"{BASE_URL}/api/chat/status/e2e-test")
        assert r.status_code == 200
        print(f"  ✓ Workflow start: {data['status']}, running={r.json().get('running')}")

        await client.post(f"{BASE_URL}/api/chat/stop/e2e-test")


async def test_upload():
    """测试 11: 文件上传"""
    async with httpx.AsyncClient() as client:
        dummy_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        files = {"file": ("test.png", dummy_content, "image/png")}
        r = await client.post(
            f"{BASE_URL}/api/chat/upload",
            files=files,
            data={"project_id": "e2e-test"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["original_name"] == "test.png"
        assert data["url"].startswith("/files/uploads/")
        print(f"  ✓ Upload: {data['filename']} ({data['size']} bytes)")


async def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("--base-url"):
        global BASE_URL, WS_URL
        BASE_URL = sys.argv[1].split("=")[1] if "=" in sys.argv[1] else sys.argv[2]
        WS_URL = BASE_URL.replace("http", "ws")

    print(f"\n{'='*60}")
    print(f"  Video Agent E2E Tests")
    print(f"  Backend: {BASE_URL}")
    print(f"{'='*60}\n")

    tests = [
        ("Health Check", test_health),
        ("Agent Registry", test_agents),
        ("Tool Registry", test_tools),
        ("Prompt CRUD", test_prompt_crud),
        ("Prompt Versions", test_prompt_versions),
        ("Tool Management", test_tool_management),
        ("Routing Rules", test_routing_rules),
        ("Skill Registry", test_skills),
        ("WebSocket", test_websocket),
        ("Workflow Start", test_workflow_start),
        ("File Upload", test_upload),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            print(f"[{name}]")
            await test_fn()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
