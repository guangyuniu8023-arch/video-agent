# Video Agent - Seedance 2.0 视频生成 Multi-Agent 系统

LLM Router + 3 Agent (Planner/Producer/Editor) 架构，基于 LangGraph 编排。

## 快速开始

### 1. 启动基础设施

```bash
docker-compose up -d
```

### 2. 后端

```bash
cd backend
cp ../.env.example .env  # 编辑 .env 填入 API Key
pip install -e ".[dev]"
python scripts/test_seedance.py  # 验证 Seedance API
uvicorn app.main:app --reload --port 8000
```

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

## 架构

- **Router**: LLM 意图路由，可配置路由规则
- **Planner (ReAct)**: 理解需求 → 创建角色 → 构建世界观 → 拆解分镜
- **Producer (ReAct)**: 调用 Seedance 2.0 生成视频 → VLM 质量检测
- **Editor (ReAct)**: 裁剪拼接 → 过渡效果 → 音频处理 → 最终合成

## 技术栈

- 后端: Python 3.12 / FastAPI / LangGraph / SQLAlchemy / Redis
- 前端: React / TypeScript / Vite / React Flow / TailwindCSS / Shadcn/UI
- 视频: Seedance 2.0 (火山方舟) / FFmpeg
- LLM: 豆包 / GPT-4o / Claude Sonnet
