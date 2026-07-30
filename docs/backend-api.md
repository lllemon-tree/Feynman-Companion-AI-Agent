# 费曼伴学智能体后端接口文档

本文档面向前端对接，覆盖账号鉴权、LangGraph 动态知识点对话和会话恢复接口。

## 基础信息

- 后端地址：`http://localhost:8000`
- Swagger 文档：`http://localhost:8000/docs`
- Mock 知识点：`kp-demo`（Dijkstra）、`kp-demo2`（Floyd）
- 会话机制：前端页面初始化时生成一个 `session_id`，同一轮对话必须一直使用同一个 `session_id` 和 `kp_id`
- 鉴权机制：无 Token 时按游客 `guest` 处理；有 Token 时必须合法且未过期，否则返回 HTTP 401

## 1. 健康检查

```http
GET /health
```

示例响应：

```json
{
  "status": "ok",
  "app": "Feynman Companion Backend",
  "llm_provider": "deepseek",
  "deepseek_configured": true
}
```

前端一般不需要调用；联调时可以用来确认后端是否启动、DeepSeek 配置是否读取成功。

## 2. 注册、登录与当前用户

```http
POST /api/v1/auth/register
Content-Type: application/json
```

```json
{
  "username": "student01",
  "password": "123456abc"
}
```

注册成功后调用 `POST /api/v1/auth/login`，请求体相同。登录响应中的
`data.token` 存入前端，并在后续请求中携带：

```http
Authorization: Bearer <token>
```

`GET /api/v1/auth/current` 必须携带 Token，用于刷新页面后恢复当前登录用户。

## 3. 初始引导语

```http
GET /api/v1/feynman/greeting?kp_id=kp-demo
```

示例响应：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "reply_text": "请你向我讲解一下 Dijkstra 算法的核心原理，讲得越详细越好。",
    "kp_id": "kp-demo",
    "kp_name": "Dijkstra 算法"
  }
}
```

前端处理：页面初始化时展示为第一条 AI 气泡。

## 4. 费曼对话接口

```http
POST /api/v1/feynman/chat
Content-Type: application/json
```

请求体：

```json
{
  "session_id": "demo-001",
  "kp_id": "kp-demo",
  "user_input": "Dijkstra 是用来求图中最短路径的算法。"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | string | 是 | 前端生成的会话 ID。同一轮对话保持不变 |
| `kp_id` | string | 新流程是 | 当前选择的知识点 ID。同一轮对话保持不变；省略时默认 `kp-demo` 仅用于兼容第三周 |
| `user_input` | string | 是 | 用户输入内容，最大 500 字 |

### 响应结构

所有成功响应都遵循：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "next_action": "follow_up",
    "reply_text": "AI 回复文本",
    "card_preview": null,
    "final_report": null
  }
}
```

### next_action 前端处理规则

| `next_action` | 含义 | 前端处理 |
| --- | --- | --- |
| `follow_up` | AI 继续追问 | 展示一条 AI 气泡，解锁输入框，允许用户继续回答 |
| `guide_topic` | 用户偏题 | 展示一条 AI 引导气泡，解锁输入框，本轮不算正式追问 |
| `generate_report` | 对话结束，生成报告 | 展示 AI 气泡，渲染底部报告卡片，锁定输入框 |

### follow_up 示例

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "next_action": "follow_up",
    "reply_text": "如果图里出现负权边，这个方法还能保证正确吗？为什么？",
    "card_preview": null,
    "final_report": null
  }
}
```

### guide_topic 示例

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "next_action": "guide_topic",
    "reply_text": "这个问题先放一放，我们这轮只围绕 Dijkstra 算法。你可以先讲讲它解决什么问题。",
    "card_preview": null,
    "final_report": null
  }
}
```

### generate_report 示例

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "next_action": "generate_report",
    "reply_text": "这轮讲解先到这里，我给你整理了一份诊断报告。",
    "card_preview": {
      "total_score": 32,
      "summary": "掌握流程，原理需补强"
    },
    "final_report": {
      "dimensions": [
        {
          "name": "理解深度",
          "score": 8,
          "analysis": "对核心机制有基本理解，但正确性依据仍需补强。",
          "suggestion": "补充非负权前提与贪心选择成立原因。"
        },
        {
          "name": "表达完整性",
          "score": 8,
          "analysis": "覆盖了主要流程，但部分边界条件没有讲清楚。",
          "suggestion": "讲解时加入适用条件和常见误区。"
        },
        {
          "name": "逻辑连贯性",
          "score": 8,
          "analysis": "步骤顺序基本清晰，但因果解释略弱。",
          "suggestion": "用“为什么可以确定最短路”串起整体逻辑。"
        },
        {
          "name": "结构化能力",
          "score": 8,
          "analysis": "表达能形成基本结构。",
          "suggestion": "按“用途-前提-步骤-原理”组织。"
        }
      ],
      "overall_comment": "本次讲解已经覆盖部分核心内容，后续重点是把非负权前提、贪心选择和松弛操作之间的因果关系讲清楚。"
    }
  }
}
```

## 5. 重置会话

用于前端“重新开始”按钮。

```http
POST /api/v1/feynman/reset
Content-Type: application/json
```

请求体：

```json
{
  "session_id": "demo-001"
}
```

响应：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "session_id": "demo-001",
    "reset": true
  }
}
```

前端处理：清空聊天区，重新展示初始引导语，解锁输入框。

## 6. 历史会话列表

```http
GET /api/v1/feynman/sessions
Authorization: Bearer <token>
```

返回当前用户的会话摘要，按最近更新时间倒序排列。游客可以省略 Header，
此时只返回 `guest` 会话。

## 7. 恢复完整会话

```http
GET /api/v1/feynman/sessions/{session_id}
Authorization: Bearer <token>
```

游客请求可以省略 Header。后端只返回属于当前登录用户或游客账号的会话，
其他用户的同名会话按 404 处理。响应中的 `chat_history` 用于恢复聊天气泡，
`report_data` 用于恢复最终报告：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "session_id": "demo-001",
    "kp_id": "kp-demo",
    "kp_name": "Dijkstra 算法",
    "material_id": "mat-demo",
    "chapter_id": "ch-demo",
    "chat_history": [
      {"role": "user", "content": "Dijkstra 用于求最短路径"},
      {"role": "assistant", "content": "它对边权有什么要求？"}
    ],
    "report_data": null,
    "created_at": "2026-07-23T10:00:00+00:00",
    "updated_at": "2026-07-23T10:01:00+00:00"
  }
}
```

## 8. Session 调试接口

仅用于开发联调，不建议展示给用户。

```http
GET /api/v1/feynman/session/{session_id}
```

示例响应：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "session_id": "demo-001",
    "exists": true,
    "follow_up_count": 2,
    "invalid_answer_count": 0,
    "off_topic_count": 0,
    "ended": false,
    "message_count": 4,
    "last_provider": "deepseek",
    "fallback_used": false,
    "kp_id": "kp-demo",
    "kp_name": "Dijkstra 算法",
    "material_id": "mat-demo",
    "chapter_id": "ch-demo",
    "recent_messages": []
  }
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `follow_up_count` | 已发起的正式追问次数，最多 3 |
| `invalid_answer_count` | 用户输入“不会/不知道”等无效回答次数 |
| `off_topic_count` | 偏题次数 |
| `ended` | 是否已经生成最终报告 |
| `last_provider` | 最近一次响应来源：`deepseek`、`mock`、`rule` |
| `fallback_used` | DeepSeek 调用失败后是否使用 mock 兜底 |
| `kp_id` / `kp_name` | 当前会话绑定的知识点 |
| `material_id` / `chapter_id` | 当前知识点所属教材和章节 |

## 9. 历史诊断报告

诊断报告接口只对登录用户开放，必须携带：

```http
Authorization: Bearer <token>
```

当登录用户的费曼对话返回 `next_action=generate_report` 后，后端会自动把
四维报告写入 `diagnostic_report`。同一个 `session_id` 重复请求不会产生重复报告。
游客仍能在当前对话看到报告，但不会写入历史报告和知识漏洞库。

### 9.1 报告列表

```http
GET /api/v1/reports?page=1&page_size=20
Authorization: Bearer <token>
```

- `page` 从 1 开始，默认 1。
- `page_size` 默认 20，最大 100。
- 数据按 `created_at` 倒序返回。
- 列表中的 `dimensions` 只包含维度名和分数，适合渲染迷你评分图。

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "report_id": "rpt-a1b2c3d4e5f6",
        "kp_id": "kp-demo",
        "kp_name": "Dijkstra 算法",
        "material_name": "数据结构教材",
        "total_score": 24,
        "dimensions": [
          {"name": "理解深度", "score": 4},
          {"name": "表达完整性", "score": 6},
          {"name": "逻辑连贯性", "score": 7},
          {"name": "结构化能力", "score": 7}
        ],
        "gaps_identified": 2,
        "created_at": "2026-07-28T10:30:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### 9.2 报告详情

```http
GET /api/v1/reports/{report_id}
Authorization: Bearer <token>
```

详情中的 `dimensions_full` 包含每个维度的 `analysis` 和 `suggestion`，可直接
传给报告抽屉组件。请求不存在或不属于当前用户的报告统一返回 HTTP 404，避免
跨用户读取。

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "report_id": "rpt-a1b2c3d4e5f6",
    "kp_id": "kp-demo",
    "kp_name": "Dijkstra 算法",
    "material_name": "数据结构教材",
    "session_id": "demo-001",
    "dimensions_full": [
      {
        "name": "理解深度",
        "score": 4,
        "analysis": "能描述步骤，但正确性依据仍不完整。",
        "suggestion": "补充非负权条件和贪心选择成立的原因。"
      }
    ],
    "total_score": 24,
    "overall_comment": "当前已掌握基本流程，下一步需要补足原理解释。",
    "gaps_identified": 2,
    "created_at": "2026-07-28T10:30:00Z"
  }
}
```

## 前端联调注意事项

1. 同一轮对话必须复用同一个 `session_id` 和 `kp_id`。
2. 页面刷新时使用原 `session_id` 请求 `/feynman/sessions/{session_id}` 恢复消息；点击“重新开始”时调用 reset 或生成新的 ID。
3. 请求发出后锁定输入框和发送按钮，接口返回后再根据 `next_action` 决定是否解锁。
4. `generate_report` 返回后，本轮对话结束，输入框应保持锁定。
5. `card_preview` 和 `final_report` 只有在 `next_action=generate_report` 时才不是 `null`。
6. 切换知识点前必须调用 reset 或生成新的 `session_id`，否则后端返回 `session is already bound to another kp_id`。
7. 若知识点不存在或已删除，chat 返回 `next_action=guide_topic`，前端应跳回知识点选择页。
8. 前端请求拦截器只在本地存在 Token 时添加 `Authorization`；不要给游客发送空 Bearer Token。
9. 历史报告 Tab 应调用 `/reports`，点击卡片后再按需调用 `/reports/{report_id}`；两个接口都不支持游客模式。
