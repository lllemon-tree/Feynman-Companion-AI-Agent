# 费曼伴学前端 MVP

基于 Vue 3 + Vite + Pinia 的学习对话首页、教材学习与复习界面。

## Run

```bash
cd /Users/chen/Code/Feynman-Companion-AI-Agent/frontend
npm install
npm run dev
```

默认监听 `http://localhost:5173`。

## Mock / Backend

修改 `frontend/.env.development`：

```ini
# false: greeting/chat/reset 调真实 LangGraph 后端
VITE_USE_FEYNMAN_MOCK=false

# true: 上传、教材树、KP 接口暂时使用前端 Mock
VITE_USE_MATERIAL_MOCK=true

# 前端等待时间要大于后端 DeepSeek 超时，给 Mock 兜底留出返回时间
VITE_API_TIMEOUT_MS=60000
```

`VITE_USE_MOCK` 仅作为旧配置的兼容回退。新配置应分别设置两个开关，避免教材后端尚未接入时阻塞真实 Feynman 对话联调。

`frontend/vite.config.js` 中已配置 `/api` 代理到 `http://127.0.0.1:8000`。

## Structure

```text
src/
├── api/                # API layer and mock data
├── components/         # Chat bubbles, input, report card, chart
├── stores/             # Pinia state
├── styles/             # Global CSS
├── views/              # Page-level views
├── App.vue
└── main.js
```

## Current Demo Behavior

- 登录后首页可切换专家/小白模式和 DeepSeek Flash/Pro 模型；普通回复逐步显示，小白讲解结束后可取得基于用户原话的无教材反馈。
- 左侧导航保留在教材、知识点、复习和报告页面；登录用户的自由对话保存在最近对话中。
- 教材知识点学习保留原有 LangGraph 追问和最终报告，历史教材会话可以继续；这一条路径暂未流式输出。
