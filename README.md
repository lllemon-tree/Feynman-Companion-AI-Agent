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
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_CHAT_MODELS=deepseek-flash,deepseek-v4-flash
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

1. 登录后进入自由对话首页：专家模式回答学业问题，小白模式听用户讲解并给出无教材、无数值分数的反馈。模型可在输入框下方切换，普通回复流式显示。
2. 教材知识点学习仍是独立模块。用户上传可提取文字的 PDF，前端轮询解析状态；无 PDF 书签也可解析，只是当前会归入“全文（无目录）”。扫描件 OCR 尚未实现。
3. 后端保存原始切片用于引用，把同页相邻切片合并后抽取知识点，再生成四维 rubric 并写入 SQLite。
4. 用户按科目、教材、章节、知识点进入教材讲解；动态引导语与 `session_id`、`kp_id` 一起维持 LangGraph 会话，历史记录可继续。
5. LangGraph 检索当前教材切片及知识点固定页码原文，生成追问与四维诊断报告。游客可体验教材学习；自由对话及历史保存需要登录。

`DEEPSEEK_MODEL` 是教材处理与未指定模型时的后端默认值；首页可选模型由 `DEEPSEEK_CHAT_MODELS` 控制。更改 `.env.local` 后重启后端。当前首页流式输出不代表教材讲解/报告也已流式化。

详细接口见 `docs/backend-api.md`。
