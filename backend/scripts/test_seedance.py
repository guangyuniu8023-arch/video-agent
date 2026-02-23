"""Seedance 2.0 API 联调测试脚本

用法:
    1. 复制 .env.example 为 .env 并填入 ARK_API_KEY 和 ARK_SEEDANCE_ENDPOINT_ID
    2. cd backend && source .venv/bin/activate
    3. python scripts/test_seedance.py
"""

import asyncio
import sys
import os
import time
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def test_sdk_import():
    print("\n=== SDK Import Test ===")
    try:
        from volcenginesdkarkruntime import Ark
        print("[OK] volcenginesdkarkruntime imported")

        api_key = os.getenv("ARK_API_KEY", "")
        if api_key:
            client = Ark(api_key=api_key)
            print("[OK] Ark client initialized")
            return True
        else:
            print("[SKIP] ARK_API_KEY not set")
            return False
    except ImportError:
        print("[FAIL] Run: pip install volcengine-python-sdk")
        return False


async def test_text_to_video():
    print("\n=== Text-to-Video Test ===")
    from app.tools.seedance import SeedanceClient

    api_key = os.getenv("ARK_API_KEY", "")
    endpoint_id = os.getenv("ARK_SEEDANCE_ENDPOINT_ID", "")

    if not api_key or not endpoint_id:
        print("[SKIP] API keys not configured")
        return None

    client = SeedanceClient(api_key=api_key, endpoint_id=endpoint_id)

    prompt = (
        "赛博朋克风格城市夜景，霓虹灯闪烁，"
        "一位紫色短发的年轻女性走在雨中街道，"
        "镜头从远景缓慢推近到中景，色调偏蓝紫色"
    )

    print(f"[t2v] Prompt: {prompt[:40]}...")
    print(f"[t2v] Submitting task (duration=5s, ratio=16:9)...")
    start = time.time()

    try:
        result = await client.text_to_video(
            prompt=prompt,
            duration=5,
            ratio="16:9",
            return_last_frame=True,
        )
        elapsed = time.time() - start
        print(f"[t2v] Success! ({elapsed:.1f}s)")
        print(f"  Task ID:        {result.task_id}")
        print(f"  Video URL:      {result.video_url}")
        print(f"  Last Frame URL: {result.last_frame_url}")

        output_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "test_t2v.mp4")

        async with httpx.AsyncClient() as http:
            resp = await http.get(result.video_url, follow_redirects=True)
            with open(output_path, "wb") as f:
                f.write(resp.content)
        print(f"  Downloaded to:  {output_path}")
        return result

    except Exception as e:
        elapsed = time.time() - start
        print(f"[t2v] Failed ({elapsed:.1f}s): {e}")
        return None


async def main():
    print("=" * 60)
    print("Seedance 2.0 API Test")
    print("=" * 60)

    sdk_ok = await test_sdk_import()
    if not sdk_ok:
        print("\n[DONE] SDK not available, skipping API tests")
        return

    result = await test_text_to_video()

    print("\n" + "=" * 60)
    if result:
        print("All tests PASSED")
    else:
        print("Some tests skipped/failed - check .env configuration")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
