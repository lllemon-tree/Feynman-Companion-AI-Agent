# Feynman Companion AI Agent

费曼伴学智能体 demo 仓库，当前采用前后端同仓管理：

- `frontend/`: Vue 3 + Vite + Pinia 聊天界面
- `backend/`: FastAPI 后端服务、DeepSeek 调用、会话状态与测试
- `docs/`: 产品需求、接口文档和项目资料

## Quick Start

后端统一使用 Python 3.13。先确认当前解释器版本：

```bash
/opt/homebrew/bin/python3.13 --version
```

### 1. Start Backend

```bash
cd /Users/chen/Code/Feynman-Companion-AI-Agent
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

后端默认监听 `http://localhost:8000`，Swagger 文档在 `http://localhost:8000/docs`。

本地 DeepSeek 配置仍然放在根目录 `.env.local`，该文件不会提交到 Git。组员第一次启动前可以先复制示例文件：

```bash
cp .env.local.example .env.local
```

然后在 `.env.local` 里填自己的 DeepSeek API key：

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_PROVIDER=deepseek
REQUEST_TIMEOUT_SECONDS=30
AUTH_SECRET_KEY=replace_with_a_long_random_secret
AUTH_TOKEN_EXPIRE_MINUTES=1440
```

### 2. Start Frontend

```bash
cd /Users/chen/Code/Feynman-Companion-AI-Agent/frontend
npm install
npm run dev
```

前端默认监听 `http://localhost:5173`，开发环境会把 `/api` 代理到 `http://127.0.0.1:8000`。

## Project Layout

```text
Feynman-Companion-AI-Agent/
├── backend/
│   ├── app/                  # FastAPI application code
│   ├── scripts/              # Backend helper scripts
│   ├── tests/                # Backend tests
│   ├── requirements.txt      # Python dependencies
│   └── README.md
├── frontend/
│   ├── src/                  # Vue frontend source code
│   ├── package.json          # Frontend dependencies and scripts
│   ├── vite.config.js        # Vite dev server and proxy config
│   ├── .env.development      # Frontend development env
│   └── README.md
├── docs/
│   └── backend-api.md        # Frontend-backend API contract
├── .env.local.example        # Local backend env template
├── .env.local                # Local backend secrets, ignored by Git
└── README.md
```

## Useful Commands

```bash
# Backend tests
source .venv/bin/activate
python -m pytest -q backend/tests

# Frontend production build
cd frontend
npm run build
```

## Demo Flow

1. 用户上传有目录的文字版 PDF，前端轮询教材解析状态。
2. 后端完成章节切片、知识点抽取和四维 rubric 生成并写入 SQLite。
3. 用户按科目、教材、章节、知识点选择真实知识点。
4. 游客直接使用，登录用户通过 Bearer Token 绑定自己的持久化会话。
5. 前端请求动态 greeting，并将 `session_id`、`kp_id` 和讲解内容发送给 LangGraph。
6. LangGraph 检索当前教材相关切片，并与知识点固定页码原文一起注入评判 Prompt。
7. 后端最多追问 3 轮，随后返回四维诊断报告；DeepSeek 失败时降级 Mock。

详细接口见 `docs/backend-api.md`。
