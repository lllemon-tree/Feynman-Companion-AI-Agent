# 费曼伴学智能体 第四周 PRD（V1.1）

> 版本：V1.1　　日期：2026-07-11　　周期：第四周
> 范围：教材知识点动态解析 + LangGraph 追问流程重构
> 团队：2 后端 + 1 前端

---

## 一、产品概述与本周目标

### 1.1 本周目标

在第三周单知识点 MVP 基础上，完成两项核心能力：

1. **教材知识点动态解析**：用户上传教材 PDF，系统自动解析章节结构、抽取知识点、为每个知识点生成四维 rubric 并存储。用户按 `科目→教材→章节→知识点` 选择后进入费曼追问。**替代第三周的硬编码 Dijkstra 知识点**。
2. **LangGraph 追问流程重构**：将现有 `FeynmanService` 状态机改造为 LangGraph 线性状态机，evaluate 节点从数据库读取动态 rubric 注入 prompt，复用现有四维打分与 Mock 兜底逻辑。

### 1.2 非目标（本周不做）

- 向量库 / RAG 语义检索（主路径不需要，详见技术架构文档第五章）
- 跨知识点关联抽取（属 V2/P1）
- 扫描件 OCR / 无目录 PDF（限定有目录的文字版 PDF）
- 验证 pass（属 V1.5）
- 账号、历史记录、SSE 流式

### 1.3 成功指标

| 指标 | 目标 |
|---|---|
| 教材解析成功率（有目录文字版 PDF） | ≥ 90% |
| 知识点抽取人工验收合格率 | ≥ 70%（允许人工增删改兜底） |
| 四维 rubric 生成 JSON 格式合规率 | ≥ 95% |
| LangGraph 追问全流程无阻塞 | 100% |
| 接口请求成功率 | ≥ 95% |

---

## 二、团队分工

| 角色 | 负责 | 一周交付物 |
|---|---|---|
| 马茗燕（教材/RAG 管线） | PDF 解析、切片、KP 抽取、rubric 生成、存储、查询接口 | 管线 6 步代码 + 5 个接口 + 数据模型 |
| 陈艺博（LangGraph 运行时） | LangGraph 状态机改造、greeting 动态化、复用打分逻辑 | LangGraph 节点图 + greeting/聊天接口改造 |
| 许嘉琪（前端） | 上传页、四级级联选择页、greeting 动态化、复用对话/报告页 | 2 个新页面 + 现有页面改造 |

---

## 三、功能点清单

### 3.1 后端 A：教材解析管线

| 功能点 | 优先级 | 说明 |
|---|---|---|
| PDF 上传 | P0 | 接收 PDF，存原始文件，返回 material_id，异步触发解析 |
| 解析状态轮询 | P0 | 返回处理中/完成/失败 + 进度步骤 |
| PDF 解析 | P0 | PyMuPDF 提取文本+页码+目录；无目录则 LLM 兜底识别章节边界 |
| 切片 | P0 | 按章节切，~300-500 字/块，保留 chunk_id+页码+章节归属 |
| 章节结构抽取 | P0 | 有目录直接用；无目录→LLM 识别 |
| 逐章知识点抽取 | P0 | 每章 chunks→LLM→KP 列表（名称+摘要+chunk_ids） |
| 逐 KP 生成 rubric | P0 | 每个 KP 的 chunks→LLM→四维 rubric（与 Dijkstra 同结构） |
| 存储 | P0 | 落 SQLite，状态置完成 |
| 知识点树查询 | P0 | 返回 科目→教材→章节→知识点 树 |
| 知识点详情查询 | P0 | 返回单个 KP 的 rubric + 原文 chunks |
| 知识点人工增删改查 | P1 | 用户手动加/改 KP 时只需填"名称+起止页码"，rubric 由 LLM 按页码重新生成；改页码范围触发 regenerate |

### 3.2 后端 B：LangGraph 追问

| 功能点 | 优先级 | 说明 |
|---|---|---|
| LangGraph 状态机 | P0 | 拆分现有 FeynmanService 为节点：off_topic/ineffective/evaluate/fallback/report |
| evaluate 节点 | P0 | 从 DB 读 rubric，注入 System Prompt，调 DeepSeek |
| 复用 Mock 兜底 | P0 | LLM 失败自动降级 MockLLM（逻辑保留） |
| 复用四维打分 | P0 | generate_report 逻辑保留 |
| greeting 动态化 | P0 | 根据选中的 KP 生成引导语 |
| 会话绑定 KP | P0 | 会话创建时记录当前选中的 kp_id |

### 3.3 前端

| 功能点 | 优先级 | 说明 |
|---|---|---|
| 上传页 | P0 | 拖拽上传 PDF + 状态轮询 + 进度展示 |
| 四级级联选择页 | P0 | 科目→教材→章节→知识点 级联，支持搜索 |
| greeting 动态化 | P0 | 进入对话页展示动态引导语 |
| 知识点编辑 | P1 | 知识点列表可增删改、触发重新生成 |
| 复用对话页 | P0 | 现有 ChatView/气泡/加载态复用 |
| 复用报告页 | P0 | 现有 ReportCard/ReportDrawer/RadarChart 复用 |

---

## 四、用户流程

### 4.1 主流程

1. 用户进入上传页，拖拽上传教材 PDF。
2. 前端轮询解析状态，展示进度（解析中→切片中→抽取知识点中→生成 rubric 中→完成）。
3. 完成后跳转选择页，四级级联：科目（预设）→教材（已上传列表）→章节→知识点。
4. 选中知识点后进入对话页，展示动态 greeting（"请你讲解《XX》第3章的 XX 知识点…"）。
5. 用户费曼讲解，后端 LangGraph 运行追问流程（最多 3 轮），复用现有四维打分。
6. 熔断后渲染底部报告卡片 + 四维雷达图报告弹窗。
7. 用户可"重新开始"换知识点或重新讲解。

### 4.2 异常分支

| 分支 | 触发 | 处理 |
|---|---|---|
| PDF 无目录 | 目录解析失败 | LLM 兜底识别章节边界；仍失败则提示"教材目录无法识别，请换有目录的 PDF" |
| 解析超时 | 单步 >60s | 标记失败，允许重试该步 |
| rubric 生成 JSON 解析失败 | LLM 返回非 JSON | 正则兜底提取；仍失败则该 KP 标记"生成失败"，可手动重生成 |
| 知识点抽取为空 | 章节无有效文本 | 该章节标记"无可抽取知识点"，前端提示 |
| 知识点被删除后会话引用失效 | 用户删除了正在追问的 KP | 后端 B 在 evaluate 节点发现 `kp_id` 为空或 KP 不存在时，返回 `next_action=guide_topic` + 提示文案"该知识点已被删除，请重新选择知识点再开始讲解"，并清空 session 的 kp_id；前端收到后跳回知识点选择页 |

---

## 五、数据模型

```text
Material 教材
  id, 科目(subject), 文件名, 原始路径, 上传时间,
  状态(parsing/chunking/extracting/generating/done/failed),
  进度步骤, 失败原因

Chapter 章节
  id, material_id, 章节号, 标题, 起止页

Chunk 切片
  id, material_id, chapter_id, 页码, 文本, 序号

KP 知识点
  id, chapter_id, 名称, 一句话摘要,
  rubric(JSON: concept_prerequisite/core_mechanism/principle_proof/common_misunderstandings),
  page_start, page_end,           ← 用户可编辑，grounding 入口
  来源chunk_ids[],                ← 由 page_start/page_end 派生（内部字段）
  状态(done/failed/pending_regenerate)

Session 会话(扩展现有)
  在现有字段基础上增加 kp_id、material_id、chapter_id
```

> rubric 的 JSON 结构与第三周硬编码的 `DIJKSTRA_GROUND_TRUTH` 完全一致，确保现有 prompt、追问、打分逻辑零改动复用。

### 5.1 知识点人工编辑字段约定（核心设计原则）

**用户只管"知识点在哪"，rubric 永远让 LLM 生成。**

| 字段 | 谁提供 | 必填 | 说明 |
|---|---|---|---|
| 知识点名称 | 用户 | 是 | 可任意编辑 |
| 起止页码 `page_start`/`page_end` | 用户 | 是 | grounding 入口，LLM 据此定位原文 chunks |
| 一句话摘要 | 系统（LLM 生成） | 否 | 留空则自动生成；用户可不填 |
| 四维 rubric | 系统（LLM 从该页原文生成） | — | **绝不让用户填写**，保证 grounding |
| 所属章节 | 上下文继承 | 隐式 | 从当前选中的章节带入 |

**rubric 不让用户填的原因**：
1. 破坏 grounding：rubric 防幻觉靠"LLM 从教材原文生成"，用户手写则脱离教材原文；
2. 用户非领域专家：四维中"原理证明""常见误区"让考研学生写易错或写浅，而那正是要帮他发现的盲区；
3. 质量风险：用户填的 rubric 进 System Prompt 当评判标准，错一个维度后续追问全歪。

**页码的作用**：不是元数据，是让 LLM 拿到原文的钥匙。改页码范围 → 触发 rubric 重新生成，是用户在不写 rubric 前提下修正抽取质量的人工兜底出口。

**V1 边界**：只支持连续页码范围（`page_start ≤ page_end`）；非连续页码（跨页跳跃知识点）留 V2，前端表单不提供多段页码控件。

### 5.2 数据库表设计（SQLite）

> V1 仅 `Material / Chapter / Chunk / KP` 四张表落 SQLite；`Session` 仍沿用第三周的内存存储（InMemorySessionStore），新增 `kp_id / material_id / chapter_id` 字段在内存对象上扩展，不落库。

#### 表结构 DDL

```sql
-- 教材
CREATE TABLE material (
  id            TEXT PRIMARY KEY,          -- mat-xxx
  subject       TEXT NOT NULL,             -- 科目：计算机/政治/数学...
  filename      TEXT NOT NULL,             -- 原始文件名
  raw_path      TEXT NOT NULL,             -- 本地存储路径
  uploaded_at   TEXT NOT NULL,             -- ISO8601
  status        TEXT NOT NULL DEFAULT 'parsing',
                                              -- parsing/chunking/extracting/generating/done/failed
  progress_step TEXT,                      -- 当前步骤文案，如"rubric 生成中"
  progress      REAL DEFAULT 0,           -- 0~1
  error         TEXT                       -- 失败原因，成功时为 NULL
);

-- 章节
CREATE TABLE chapter (
  id           TEXT PRIMARY KEY,           -- ch-xxx
  material_id  TEXT NOT NULL REFERENCES material(id) ON DELETE CASCADE,
  chapter_no   TEXT,                       -- "第6章"
  title        TEXT NOT NULL,              -- "图论"
  page_start   INTEGER,                    -- 章节起止页（从目录解析）
  page_end     INTEGER
);

-- 切片
CREATE TABLE chunk (
  id           TEXT PRIMARY KEY,           -- chunk-xxx
  material_id  TEXT NOT NULL REFERENCES material(id) ON DELETE CASCADE,
  chapter_id   TEXT REFERENCES chapter(id) ON DELETE SET NULL,  -- 未分章时 NULL
  page_no      INTEGER NOT NULL,          -- 该 chunk 所属页码
  seq          INTEGER NOT NULL,          -- 同页内顺序
  text         TEXT NOT NULL
);
CREATE INDEX idx_chunk_material_page ON chunk(material_id, page_no);

-- 知识点
CREATE TABLE kp (
  id           TEXT PRIMARY KEY,           -- kp-xxx
  chapter_id   TEXT NOT NULL REFERENCES chapter(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  summary      TEXT,                       -- 一句话摘要，LLM 生成
  rubric       TEXT,                       -- 四维 JSON 字符串
  page_start   INTEGER NOT NULL,           -- 用户可编辑，grounding 入口
  page_end     INTEGER NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending_regenerate',
                                              -- done/failed/pending_regenerate
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE INDEX idx_kp_chapter ON kp(chapter_id);
```

#### 字段说明与设计要点

| 表 | 关键设计点 |
|---|---|
| `material` | `status` 枚举驱动前端进度轮询；`progress` + `progress_step` 用于进度条文案 |
| `chapter` | `page_start/page_end` 从 PDF 目录解析得出；目录缺失时由 LLM 兜底识别后回填 |
| `chunk` | **`chapter_id` 可空**：解析阶段先切完所有 chunk 再分章，过渡期 chapter_id 为 NULL；`page_no` 是 KP 定位原文的依据 |
| `kp` | **`page_start/page_end` 是唯一真值**；`chunk_ids` 不存储，运行时按 `material_id + page 范围` 查 chunk 派生（避免与 page 字段不一致）；`rubric` 存 JSON 字符串 |

> **派生 `chunk_ids` 的查询**：`SELECT id FROM chunk WHERE material_id=? AND page_no BETWEEN ? AND ? ORDER BY page_no, seq`。这样用户改页码后，下次生成 rubric 自动拿到新 chunks，无需维护关联表。

> **软删除 vs 硬删除**：V1 KP 直接硬删除（`ON DELETE CASCADE` 级联清理由章节删除带走的 KP）；会话内存里的 `kp_id` 由后端 B 在 evaluate 节点判空兜底（见 4.2 末行）。

---

## 六、处理流水线（后端 A，异步）

```text
上传 ─→ [1.解析(代码)] ─→ [2.切片(代码)] ─→ [3.章节抽取(代码+LLM兜底)]
     ─→ [4.逐章抽KP(LLM)] ─→ [5.逐KP生成rubric(LLM)] ─→ [6.存库(代码)]
```

| 步骤 | 工具 | 是否 LLM | 产出 |
|---|---|---|---|
| 1. PDF 解析 | PyMuPDF | 否 | 每页文本+页码+目录 |
| 2. 切片 | 代码 | 否 | chunk+chunk_id+页码+章节归属 |
| 3. 章节结构抽取 | 目录优先，LLM 兜底 | 兜底时是 | 章节列表 |
| 4. 逐章抽 KP | LLM | 是 | 每章 KP 列表（名称+摘要+chunk_ids） |
| 5. 逐 KP 生成 rubric | LLM | 是 | 四维 rubric JSON |
| 6. 存储 | 代码 | 否 | 落 SQLite，状态 done |

**防幻觉手段**：第 5 步把该 KP 的原文 chunks 全部塞进 prompt（grounding）+ 结构化输出 + 引用 chunk_id。

---

## 七、接口契约（新增）

### 7.1 后端 A 接口

#### 上传教材

```http
POST /api/v1/material/upload
Content-Type: multipart/form-data
```

请求：`file`(PDF) + `subject`(科目)

响应：
```json
{ "code": 200, "msg": "success", "data": { "material_id": "mat-xxx", "status": "parsing" } }
```

#### 查询解析状态

```http
GET /api/v1/material/{material_id}/status
```

响应：
```json
{ "code": 200, "msg": "success", "data": {
  "material_id": "mat-xxx",
  "status": "generating",
  "step": "rubric 生成中",
  "progress": 0.6,
  "error": null
}}
```

#### 查询知识点树

```http
GET /api/v1/material/tree?subject=计算机
```

响应：
```json
{ "code": 200, "msg": "success", "data": [
  { "material_id": "mat-xxx", "title": "数据结构教材",
    "chapters": [
      { "chapter_id": "ch-1", "title": "图论",
        "knowledge_points": [
          { "kp_id": "kp-1", "name": "Dijkstra 算法", "summary": "..." }
        ]}
    ]}
]}
```

#### 查询知识点详情

```http
GET /api/v1/kp/{kp_id}
```

响应：
```json
{ "code": 200, "msg": "success", "data": {
  "kp_id": "kp-1", "name": "Dijkstra 算法", "summary": "...",
  "rubric": { "concept_prerequisite": {...}, "core_mechanism": {...},
              "principle_proof": {...}, "common_misunderstandings": {...} },
  "source_chunks": [{"page": 32, "text": "..."}, ...]
}}
```

#### 新增知识点（手动）

```http
POST /api/v1/kp
Content-Type: application/json
```

请求体：
```json
{ "chapter_id": "ch-1", "name": "Floyd 算法", "page_start": 40, "page_end": 43, "summary": "" }
```

> `summary` 留空时后端自动生成；`rubric` 不接受用户传入，由后端按页码定位 chunks 后 LLM 生成。

响应：
```json
{ "code": 200, "msg": "success", "data": { "kp_id": "kp-2", "status": "pending_regenerate" } }
```

#### 修改知识点

```http
PATCH /api/v1/kp/{kp_id}
Content-Type: application/json
```

请求体（任意子集）：
```json
{ "name": "Floyd-Warshall", "page_start": 40, "page_end": 44 }
```

后端行为：
- 只改 `name`/`summary`：直接更新，不重生成 rubric；
- 改了 `page_start` 或 `page_end`：标记 `pending_regenerate`，异步按新页码范围重新生成 rubric，前端轮询状态。

响应：
```json
{ "code": 200, "msg": "success", "data": { "kp_id": "kp-2", "regenerate_triggered": true, "status": "pending_regenerate" } }
```

#### 删除知识点

```http
DELETE /api/v1/kp/{kp_id}
```

响应：
```json
{ "code": 200, "msg": "success", "data": { "kp_id": "kp-2", "deleted": true } }
```

> 删除后引用该 KP 的会话将 `kp_id` 置空，已生成的报告保留但不可继续追问。

#### 重新生成 rubric

```http
POST /api/v1/kp/{kp_id}/regenerate
```

> 用当前 `page_start/page_end` 重新拉 chunks → LLM 重新生成 rubric+摘要。用于用户对当前 rubric 质量不满意、页码没变想重抽的场景。

响应：
```json
{ "code": 200, "msg": "success", "data": { "kp_id": "kp-2", "status": "pending_regenerate" } }
```

> 上述新增/改页码/regenerate 三类操作均异步，前端通过 `GET /api/v1/kp/{kp_id}` 轮询 `status`，变为 `done` 即可读 `rubric`。

### 7.2 后端 B 接口改造

#### greeting 动态化

```http
GET /api/v1/feynman/greeting?kp_id=kp-1
```

响应：
```json
{ "code": 200, "msg": "success", "data": {
  "reply_text": "请你向我讲解一下 Dijkstra 算法的核心原理，讲得越详细越好。",
  "kp_id": "kp-1", "kp_name": "Dijkstra 算法"
}}
```

#### chat 绑定 KP

```http
POST /api/v1/feynman/chat
{ "session_id": "...", "kp_id": "kp-1", "user_input": "..." }
```

响应结构同第三周，不变。

### 7.3 接口 Mock 数据（前后端并行开发用）

> 后端 A 周一第一件事：把下列 mock 响应固化成一个 mock 开关（`USE_MOCK=true` 时直接返回，不跑真实管线）。前端和后端 B 全部基于这套 mock 开发，等真实管线接通后切换。所有 mock 以"计算机/数据结构教材/图论/Dijkstra 算法"为统一样例。

#### Mock 数据集（统一样例）

```json
// material_id = mat-demo, chapter_id = ch-demo, kp_id = kp-demo

// 1) 解析状态：直接返回完成
GET /api/v1/material/mat-demo/status
{ "code":200, "msg":"success", "data":{
  "material_id":"mat-demo", "status":"done", "step":"完成", "progress":1, "error":null }}

// 2) 知识点树
GET /api/v1/material/tree?subject=计算机
{ "code":200, "msg":"success", "data":[
  { "material_id":"mat-demo", "title":"数据结构教材",
    "chapters":[
      { "chapter_id":"ch-demo", "title":"图论",
        "knowledge_points":[
          { "kp_id":"kp-demo", "name":"Dijkstra 算法", "summary":"非负权图求单源最短路径的贪心算法" },
          { "kp_id":"kp-demo2", "name":"Floyd 算法", "summary":"全源最短路径动态规划算法" }
        ]}
    ]}
]}

// 3) 知识点详情（含完整四维 rubric + 原文 chunks）
GET /api/v1/kp/kp-demo
{ "code":200, "msg":"success", "data":{
  "kp_id":"kp-demo", "name":"Dijkstra 算法",
  "summary":"非负权图求单源最短路径的贪心算法",
  "rubric":{
    "concept_prerequisite":{ "name":"概念前提",
      "content":"Dijkstra算法适用于边权非负的带权图。负权边会破坏已访问节点最短路径已确定这一核心结论。" },
    "core_mechanism":{ "name":"核心机制",
      "content":"基于贪心：每次从未访问节点中选距离起点最近的，标记为已访问，并用它松弛相邻节点。" },
    "principle_proof":{ "name":"原理证明",
      "content":"正确性依赖非负权前提：当前距离最小的未访问节点之后不可能再通过其他未访问节点得到更短路径。" },
    "common_misunderstandings":{ "name":"常见误区",
      "content":[
        "认为Dijkstra可以处理负权图",
        "只记步骤无法解释贪心策略正确性",
        "混淆松弛操作的作用",
        "误以为每次选的是边权最小的边"
      ]}
  },
  "page_start":30, "page_end":33,
  "status":"done",
  "source_chunks":[
    { "chunk_id":"chunk-1", "page":30, "text":"Dijkstra算法用于求解..." },
    { "chunk_id":"chunk-2", "page":31, "text":"贪心策略：每次选择..." },
    { "chunk_id":"chunk-3", "page":32, "text":"松弛操作：用当前节点更新相邻节点距离..." },
    { "chunk_id":"chunk-4", "page":33, "text":"正确性依赖边权非负..." }
  ]
}}

// 4) 动态 greeting
GET /api/v1/feynman/greeting?kp_id=kp-demo
{ "code":200, "msg":"success", "data":{
  "reply_text":"请你向我讲解一下 Dijkstra 算法的核心原理，讲得越详细越好。",
  "kp_id":"kp-demo", "kp_name":"Dijkstra 算法" }}

// 5) 新增/改/重生成：统一返回 pending_regenerate，前端轮询 /kp/{id} 拿 done
POST /api/v1/kp          → { "code":200, "data":{ "kp_id":"kp-mock-new", "status":"pending_regenerate" }}
PATCH /api/v1/kp/kp-demo → { "code":200, "data":{ "kp_id":"kp-demo", "regenerate_triggered":true, "status":"pending_regenerate" }}
DELETE /api/v1/kp/kp-demo → { "code":200, "data":{ "kp_id":"kp-demo", "deleted":true }}
```

#### 各端使用约定

| 消费方 | 依赖的 mock 接口 | 说明 |
|---|---|---|
| 前端 | `/material/tree`、`/material/{id}/status`、`/kp/{id}`、`/greeting`、KP 增删改 regenerate | 全部 UI 先对 mock 调通 |
| 后端 B | `/kp/{id}`（拿 rubric）、`/greeting`（拿引导语） | LangGraph evaluate 节点调 `/kp/{id}` 注入 rubric；真实管线没通前用 mock 返回的 rubric 验证追问链路 |
| 后端 A | — | 自己产出上述 mock，是 mock 的提供方 |

> **并行开发前提**：后端 A 把上面这套 mock 提交到仓库（建议放 `backend/app/services/material_mock.py` 或加 `USE_MOCK` 开关在 routes 层短路），前端和后端 B 周一即可开工，不等真实管线。

---

## 八、界面设计

原型link：https://www.figma.com/make/psdZhD3SJbnxU3wwr3upXT/Design-chat-interface?t=ELomtgaT6hS2rjTK-1

### 8.1 上传页

版本：上传页面

路径：/upload

![image-20260712004008112](C:/Users/Pamela/AppData/Roaming/Typora/typora-user-images/image-20260712004008112.png)

**状态**：拖拽态 / 上传中 / 解析中（进度条+步骤文案）/ 完成 / 失败（重试按钮）。

点击已完成上传的教材进入知识点列表

- 知识点按章节折叠
- 支持增删改查知识点
- 生成失败支持重新生成（详情看原型交互）

![image-20260712004434727](C:/Users/Pamela/AppData/Roaming/Typora/typora-user-images/image-20260712004434727.png)

**注意事项：**

```
# 费曼伴学-教材上传页面 功能交互原型词（移除查看知识点按钮，调整跳转逻辑）
## 一、页面顶部固定模块
1. 左侧固定文字：费曼伴学
2. 右侧科目下拉选择器，选项：计算机、数学、政治；默认选中计算机
3. 下拉交互：切换科目，下方已上传教材列表实时刷新，仅展示当前科目教材，无加载阻塞
4. 页面主标题：上传教材PDF

## 二、PDF上传核心拖拽模块
### 展示内容
- 主提示文字：拖拽教材PDF到此处 / 点击选择文件
- 辅助小字：仅支持文字版PDF文件，文件大小上限50MB
### 交互逻辑
1. 点击模块空白区域：唤起本地文件选择弹窗，仅筛选.pdf文件；选中文件发起POST /api/v1/material/upload，携带subject、file参数
2. 拖拽交互
   - 合法PDF拖拽悬浮至模块内：模块高亮
   - 拖拽非PDF文件：弹出轻提示「仅支持文字版PDF文件」，不上传
   - 松手上传合法PDF，接口返回material_id，后端开启异步解析
3. 上传中状态：模块内展示上传进度百分比+文字「文件上传中 XX%」，禁止重复上传
4. 上传失败（文件超限/格式错误）：模块底部红色失败文案，附带「重新上传」按钮，点击清空文件重新选择

## 三、已上传教材列表区域（上传模块下方，按上传时间倒序展示）
单条教材Item统一展示内容：PDF原始文件名 + 解析状态+进度条+步骤文案
1. 状态区分展示
   - parsing/chunking/extracting/generating：展示步骤文案+0~100%进度条，例：rubric生成中 60%，无操作按钮
   - done：绿色对勾标识「已完成」，整条Item可点击
   - failed：红色失败标识，展示error失败原因，右侧固定「重试解析」按钮；点击重试重新执行完整解析管线，刷新本条进度
2. 列表Mock固定渲染数据
   - Item1：数据结构教材.pdf，状态generating，rubric生成中，进度60%，不可点击
   - Item2：操作系统教材.pdf，状态done，绿色已完成标识，整条可点击
3. 轮询机制
   页面初始化、上传成功、点击重试后，定时轮询GET /api/v1/material/{material_id}/status，实时同步status/step/progress/error；status变为done/failed后停止单条轮询

## 四、Item点击跳转交互（核心修改：移除独立查看按钮，整行点击触发）
1. 仅status=done的教材Item支持点击；处理中/失败条目点击无响应，无弹窗、无跳转
2. 点击已完成教材Item：跳转全新知识点管理页面，自动携带当前material_id、subject，请求GET /api/v1/material/tree加载该教材完整章节知识点树
3. 知识点管理页面基础规则（上传页仅负责跳转，配套交互同步说明）
### 知识点管理页面-展示规则
1. 整体结构：章节分组折叠面板，默认全部展开；点击章节标题可折叠/展开当前章节下所有知识点
2. 单章节内展示：章节标题 + 该章节下全部知识点条目
3. 知识点条目默认渲染Mock数据：Dijkstra算法、Floyd算法，每条展示名称、起止页码、生成状态（done/pending_regenerate/failed）
### 知识点管理页面-完整CRUD交互
1. 新增知识点（弹窗交互）
   - 页面顶部「新增知识点」按钮，点击弹出独立弹窗
   - 弹窗输入项：
     ① 知识点名称（必填输入框，空值确定拦截，提示填写名称）
     ② 起始页码（数字输入框，仅允许正整数）
     ③ 结束页码（数字输入框，仅允许正整数，前端校验结束页码≥起始页码，不满足则拦截提交）
   - 弹窗底部：取消、确定按钮
     - 取消：关闭弹窗，不保存任何内容
     - 确定：校验通过后调用POST /api/v1/kp，携带当前chapter_id、名称、page_start、page_end；接口返回kp_id、status=pending_regenerate，弹窗关闭，新增条目立刻回显至当前章节列表，条目展示「rubric生成中」状态，页面定时轮询GET /api/v1/kp/{kp_id}同步生成状态
2. 修改知识点
   - 每条知识点右侧「编辑」按钮，点击复用新增弹窗，回填当前知识点名称、起止页码
   - 修改仅名称：直接更新数据库，不触发rubric重生成
   - 修改起止页码：提交后标记status=pending_regenerate，后台异步重新生成rubric，列表实时刷新状态
3. 删除知识点
   - 每条知识点右侧「删除」按钮，点击弹出二次确认弹窗；确认后调用DELETE /api/v1/kp/{kp_id}，当前知识点条目从列表移除
4. 手动重新生成rubric
   - 知识点状态为done/failed时，右侧显示「重新生成」按钮；点击调用POST /api/v1/kp/{kp_id}/regenerate，条目切换为pending_regenerate，轮询等待生成完成

## 五、上传页面异常交互
1. 解析识别无目录PDF：轮询返回error，Item标记failed，失败文案「教材目录无法识别，请换有目录的PDF」，支持重试解析
2. 单步解析超时60s以上：Item状态置failed，展示超时提示，可重试
3. 接口请求异常：弹出轻Toast「加载失败，请稍后刷新页面」，不阻塞页面其他操作

## 六、空列表状态
切换科目后无对应教材，列表区域展示居中提示文字：暂无上传教材，请拖拽PDF文件上传，无额外操作按钮
```

### 8.2 四级级联选择

版本：添加知识点选择页面

路径：/select

![image-20260712005836691](C:/Users/Pamela/AppData/Roaming/Typora/typora-user-images/image-20260712005836691.png)

**注意事项**

```
# 费曼伴学-四级级联知识点选择页面 功能交互原型词
## 一、页面顶部标题区域
页面固定标题文字：选择知识点开始费曼学习

## 二、四级级联筛选区域（自上而下顺序：科目、教材、章节、知识点）
1. 科目下拉选择框
下拉可选数据：计算机、数学、政治
页面默认选中：计算机
交互逻辑：切换科目下拉选项，清空下级教材、章节、知识点选择内容，重新请求GET /api/v1/material/tree?subject=选中科目，刷新教材下拉列表；无对应教材时教材下拉置空不可选

2. 教材下拉选择框
当前mock加载数据（科目=计算机）：数据结构教材、操作系统教材
页面默认选中：数据结构教材
交互逻辑：切换教材下拉选项，清空下级章节、知识点选择内容，根据选中material_id筛选对应章节，刷新章节下拉列表；无章节时章节下拉置空不可选

3. 章节下拉选择框
当前mock加载数据（教材=数据结构教材）：第6章 图论、第5章 树结构
页面默认选中：第6章 图论
交互逻辑：切换章节下拉选项，清空知识点列表，根据选中chapter_id筛选对应知识点，刷新下方知识点单选列表；无知识点时列表展示空白提示

4. 知识点单选列表容器
mock展示数据（章节=第6章 图论）
● Dijkstra 算法 [高频考点]
○ 最小生成树
○ 拓扑排序
交互规则：
- 单选模式，同一时间仅能选中一条知识点
- 默认页面加载完成自动选中第一条：Dijkstra 算法
- 未选中任意知识点时，底部「开始费曼讲解」按钮置灰不可点击；选中知识点后按钮激活可点击

## 三、底部操作按钮
按钮文字：开始费曼讲解 →
交互逻辑：
点击按钮，携带当前选中kp_id、material_id、chapter_id、subject跳转Home页面，同时调用GET /api/v1/feynman/greeting?kp_id=选中kp_id，预加载对应知识点动态引导语

## 四、接口与mock数据说明
1. 页面初始化mock请求GET /api/v1/material/tree?subject=计算机
返回树形结构：
[
  {
    "material_id": "mat-demo",
    "title": "数据结构教材",
    "chapters": [
      {
        "chapter_id": "ch-demo",
        "title": "第6章 图论",
        "knowledge_points": [
          {
            "kp_id": "kp-demo",
            "name": "Dijkstra 算法",
            "summary": "非负权图求单源最短路径的贪心算法",
            "tag": "高频考点"
          },
          {
            "kp_id": "kp-mst",
            "name": "最小生成树",
            "summary": "连通图总权值最小的生成子图"
          },
          {
            "kp_id": "kp-topo",
            "name": "拓扑排序",
            "summary": "有向无环图节点线性排序方式"
          }
        ]
      },
      {
        "chapter_id": "ch-tree",
        "title": "第5章 树结构",
        "knowledge_points": []
      }
    ]
  },
  {
    "material_id": "mat-os",
    "title": "操作系统教材",
    "chapters": []
  }
]
2. 选中Dijkstra算法后，预加载greeting mock返回
{
  "code":200,
  "msg":"success",
  "data":{
    "reply_text":"请你向我讲解一下 Dijkstra 算法的核心原理，讲得越详细越好。",
    "kp_id":"kp-demo",
    "kp_name":"Dijkstra 算法"
  }
}

## 五、空状态交互
1. 切换科目无教材：教材下拉框显示「暂无教材」禁用，章节、知识点区域隐藏
2. 选中教材无章节：章节下拉框显示「暂无章节」禁用，知识点列表隐藏
3. 选中章节无知识点：知识点列表展示提示文字「当前章节暂无知识点，请前往教材管理页面新增」

## 六、异常交互
下拉切换、列表加载接口请求失败时，弹出轻Toast：加载数据失败，请重新切换选项

```

### 8.3 对话页（改造）

版本：状态一、二、三（之前mvp那几个版本）

路径：/home

顶部增加当前知识点面包屑：`计算机 / 数据结构教材 / 第6章 图论 / Dijkstra 算法`，其余复用第三周对话与报告界面。

**注意事项**

- 四级级联选择页面点击“开始费曼讲解”按钮后跳转到对话页
- 引导词应随知识点动态变化

---

## 九、验收标准

### 9.1 教材解析管线

1. **上传闭环**：上传一本有目录的文字版 PDF，30 秒内完成解析、切片、KP 抽取、rubric 生成，状态变为 done。
2. **知识点抽取质量**：人工验收一本真实教材，抽取出的知识点数量与目录章节对应，名称合理，70% 以上可接受。
3. **rubric 合规**：所有 KP 的 rubric 为合法 JSON，四维字段齐全，每条结论标注来源 chunk_id。
4. **人工编辑**：前端可增删改 KP，删除后知识点树实时更新；重新生成 rubric 成功。
5. **异常兜底**：上传无目录 PDF → 触发 LLM 兜底或友好报错；rubric 生成失败 → 该 KP 标记 failed，可重试。

### 9.2 LangGraph 追问

1. **状态图跑通**：选中任意 KP 进入对话，LangGraph 状态机正常流转，能完成 3 轮追问 + 报告生成。
2. **rubric 注入**：日志确认 evaluate 节点读到了该 KP 的动态 rubric，prompt 中 ground truth 不再是硬编码 Dijkstra。
3. **兜底保留**：DeepSeek 调用失败时自动降级 MockLLM，`last_provider` 记录正确。
4. **greeting 动态化**：不同 KP 的 greeting 文本不同，包含知识点名称。
5. **复用打分**：generate_report 返回的四维结构与第三周一致，前端雷达图正常渲染。

### 9.3 前端

1. 上传→轮询→完成全流程无阻塞，进度文案准确。
2. 四级级联选择正确联动，换教材/章节时下级重置。
3. 对话页 greeting 动态展示，面包屑正确。
4. 报告页雷达图与文字报告正常渲染。

---

## 十、非功能需求与风险

### 10.1 非功能

- **性能**：单教材（≤200 页）全流程 ≤ 60s；单接口平均响应 ≤ 10s。
- **兼容**：桌面端 Chrome/Edge 最新版。
- **异步**：解析管线用 FastAPI BackgroundTasks，状态轮询，不上 Celery。
- **存储**：V1 用 SQLite，原始 PDF 存本地文件系统。

### 10.2 风险与应对

| 风险 | 等级 | 应对 |
|---|---|---|
| LLM 知识点抽取质量差 | 高 | 前端支持人工增删改兜底；迭代 prompt；上线前人工验收一本真实教材 |
| rubric 生成 JSON 格式不稳定 | 中 | json_object 强制 + 正则兜底 + failed 标记可重试 |
| PyMuPDF 对部分 PDF 解析失败 | 中 | 兜底报错，提示换教材；限定文字版 PDF |
| LangGraph 学习曲线 | 中 | 包装现有逻辑而非重写；节点图保持线性，不引入复杂分支 |
| Windows 部署环境问题 | 中 | 不上向量库/embedding 本地模型，规避部署成本 |
| 两后端接口边界不清互相阻塞 | 中 | 先定死接口契约（第七章），后端 B 调后端 A 的 `/kp/{id}` |

### 10.3 接口边界约定（并行开发前提）

后端 A 先交付 `/kp/{kp_id}` 与 `/material/tree` 的 mock 返回结构，后端 B 即可并行开发 LangGraph。真实管线接通后切换。

---

## 附录 A：本周砍项（留 V1.5/V2）

- 验证 pass（二次 LLM 校验 rubric 结论） → V1.5
- 跨知识点关联抽取 → V2
- 向量库 + RAG 语义检索 → V2
- 扫描件 OCR / 无目录 PDF 兜底 → V2
- 多教材版本别名映射 → V2
- SRS 间隔复习 / 学情画像 → V2/V3
