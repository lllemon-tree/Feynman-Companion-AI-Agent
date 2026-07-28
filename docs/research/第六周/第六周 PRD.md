# 费曼伴学智能体 第六周 PRD（V1.0）

版本：V1.0

日期：2026-07-28

周期：第六周

范围：学情初始化 + 知识漏洞库 + 诊断报告持久化 + 个人中心

团队：2 后端（马茗燕、陈艺博）+ 1 前端（许嘉琪）

前置基线：第五周已完成账号体系、RAG 语义检索、会话持久化、全表 user_id 数据隔离

---

## 一、产品概述与本周目标

### 1.1 本周核心目标

在第五周全链路闭环基础上，新增三大用户类功能模块，实现「学情画像→诊断→漏洞追踪→复习引导」的完整费曼学习闭环：

1. **学情初始化模块**

   当前注册后无任何引导，用户直接进入上传页；新增学情画像，收集报考学科、备考阶段、核心痛点等信息，为后续个性化推荐和学科定制化追问提供基础。

2. **知识漏洞库（Gap DB）**

   当前四维诊断报告生成后漏洞信息不持久化，关闭页面即丢失；新增知识漏洞表，每次对话结束自动记录低分维度（≤6 分），支持用户手动管理漏洞状态（待复习/已掌握），为 SRS 间隔复习做准备。

3. **诊断报告持久化与历史查询**

   当前报告仅存在于内存 LearnSession 的 final_response_json 中；新增诊断报告独立表，支持按用户查询历史报告列表、查看报告详情。

4. **前端个人中心页面**

   新增 Profile 页面，包含学情档案、知识漏洞库、历史报告、我的教材四个 Tab。

### 1.2 本周非目标（顺延后续迭代）

1. SRS 间隔复习推送（第七周）
2. 个性化复习建议算法（第七周）
3. 系统预设教材库（第七周，等待师姐提供 token）
4. 学科定制化追问（第七周）
5. 错题复盘 / 主观题训练场景（第八周）

### 1.3 成功指标

| 指标 | 目标值 |
|---|---|
| 学情初始化接口请求成功率 | ≥ 98% |
| 对话结束后知识漏洞自动入库成功率 | ≥ 95% |
| 历史报告查询列表展示完整（含四维评分 + 总分） | 100% |
| 个人中心页面加载 < 2s | 100% |
| 漏洞状态更新（标记已掌握）接口正常 | 100% |
| 存量用户无学情画像时接口不报错 | 100% |

---

## 二、团队分工

| 角色 | 负责模块 | 操作文件（仅这些） |
|---|---|---|
| 马茗燕（后端 A） | 1. user_profile 表 + CRUD 接口；2. knowledge_gap 表 + CRUD 接口；3. 学情和漏洞 Mock 数据；4. 三张表的建表 DDL 迁移 | **新建**：`models/user_profile.py`、`services/user_profile_service.py`、`api/user_profile.py`、`models/knowledge_gap.py`、`services/knowledge_gap_service.py`、`api/knowledge_gap.py` **修改**：`core/database.py`（加 import + DDL）、`main.py`（加 2 行 include_router） |
| 陈艺博（后端 B） | 1. diagnostic_report 表 + 列表/详情接口；2. LangGraph report 节点后置钩子（自动写 gap + report）；3. 报告 Mock 数据 | **新建**：`models/diagnostic_report.py`、`services/diagnostic_report_service.py`、`api/diagnostic_report.py` **修改**：`graphs/feynman_graph.py`、`main.py`（加 1 行 include_router） |
| 许嘉琪（前端） | 1. 个人中心页面（4 个 Tab）；2. 学情初始化弹窗；3. 漏洞列表 + 状态操作；4. 历史报告列表 + 详情回看 | 前端独立文件，后端只需 Mock 数据就绪 |

---

## 三、功能点清单

### 3.1 后端 A：数据模型 + 接口

#### P0 必做功能

1. **user_profile 学情表**
   - 字段：user_id, nickname（可选）, exam_subject（报考学科）, exam_sub_category（专业方向）, preparation_stage（备考阶段: 基础/强化/冲刺）, exam_type（备考类型: 应届/二战/在职）, pain_points（核心痛点 JSON 数组）, target_school（目标院校）, target_major（目标专业）, created_at, updated_at
   - 注册后自动创建空记录，无初始化数据时接口不报错

2. **学情 CRUD 接口**
   - `GET /api/v1/user/profile` — 查询当前学情
   - `POST /api/v1/user/profile` — 首次提交学情
   - `PATCH /api/v1/user/profile` — 更新学情
   - 所有接口携带 Token 鉴权

3. **knowledge_gap 知识漏洞表**
   - 字段：id, user_id, kp_id, kp_name, material_id, material_name, dimension（维度名）, gap_description, severity（严重程度 1-5）, score（当时得分 0-10）, status（open/reviewing/resolved）, source_session_id, review_count, last_reviewed_at, next_review_at, created_at, updated_at

4. **漏洞 CRUD 接口**
   - `GET /api/v1/gaps` — 查询漏洞列表（支持 status 过滤）
   - `PATCH /api/v1/gaps/{gap_id}` — 更新漏洞状态（标记复习中/已掌握）
   - `GET /api/v1/gaps/stats` — 漏洞统计数据（各维度分布、总数）

5. **diagnostic_report 诊断报告表**
   - 字段：id, user_id, session_id, kp_id, kp_name, material_id, material_name, dimensions（完整四维评分 JSON）, total_score, overall_comment, gaps_identified（本报告产生的漏洞数）, created_at

6. **历史报告接口**
   - `GET /api/v1/reports` — 历史报告列表（分页，按时间倒序）
   - `GET /api/v1/reports/{report_id}` — 报告详情（含完整四维评分+评语）

#### P1 次要功能

1. 漏洞库按学科/教材/kp 分组统计接口
2. 学情画像更新后的推荐逻辑（预留，第七周）

### 3.2 后端 B：LangGraph 集成改造

#### P0 必做功能

1. **report 节点后置钩子**
   - LangGraph `_report` / `_persist_session` 节点后：
     - 检查 final_response.final_report 中四维评分
     - 对每个得分 ≤ 6 分的维度，自动插入 knowledge_gap 记录（自动去重：同一 kp+维度 已存在且为 open 状态则更新分数，不重复插入）
     - 写入 diagnostic_report 记录

#### P1 次要功能

1. 数据聚合接口（一次性返回用户概览数据：漏洞数、报告数、教材数）

### 3.3 前端

https://www.figma.com/make/psdZhD3SJbnxU3wwr3upXT/Design-chat-interface?t=2SW9xUKe1bhLKumr-1&preview-route=%2Fselect

#### P0 必做功能

1. **个人中心页面 `/profile`**
   - 4 个 Tab：学情档案 / 知识漏洞 / 历史报告 / 我的教材
   - 顶部展示用户名 + 头像（首字母占位）

2. **学情初始化（首次登录引导）**

   *需要先注册 才能弹出*

   ![image-20260728111633816](C:/Users/Pamela/AppData/Roaming/Typora/typora-user-images/image-20260728111633816.png)

   - 注册后首次登录自动弹出学情填写弹窗
   - 表单：报考学科下拉（计算机/政治/数学/英语/专业课）、备考阶段单选、备考类型单选、核心痛点多选（概念理解困难/输出薄弱/知识碎片化/盲目刷题/自律性差）
   - 可跳过（留空），后续从个人中心进入填写
   - 游客不弹窗，登录后首次才弹

3. **知识漏洞列表**
   - 按状态 Tab：待复习（open）/ 复习中（reviewing）/ 已掌握（resolved）
   - 每条展示：知识点名称、维度、得分、严重程度、创建时间
   - 操作按钮：标记复习中 → 标记已掌握

4. **历史报告列表**
   - 卡片列表：知识点名称、总分、四维评分概览、日期
   - 点击展开报告详情弹窗（复用 ReportDrawer 组件）

5. **我的教材（复用现有上传页逻辑）**
   - 当前登录用户已上传教材列表

---

## 四、完整用户流程

### 4.1 学情初始化流程

1. 用户注册成功 → 自动登录 → 判断学情为空 → 弹出学情初始化弹窗
2. 用户填写：报考学科、备考阶段、备考类型、核心痛点
3. 点击「保存并开始学习」→ 提交 POST /api/v1/user/profile → 跳转上传页
4. 也可点击「稍后填写」→ 关闭弹窗，后续从个人中心进入填写

### 4.2 诊断报告持久化流程

1. 用户完成费曼对话，LangGraph 进入 report 节点生成四维报告
2. report 节点后置钩子：
   - 将 final_report 写入 diagnostic_report 表
   - 遍历四个维度得分，≤ 6 分的写入 knowledge_gap 表（自动去重）
3. 前端收到 `generate_report` 响应，展示报告
4. 用户进入个人中心 → 历史报告 Tab → 看到所有历史报告

### 4.3 知识漏洞管理流程

1. 用户进入个人中心 → 知识漏洞 Tab
2. 默认展示「待复习」漏洞列表（按时间倒序）
3. 每条显示：知识点、维度、得分、严重程度
4. 用户点击「开始复习」→ 状态变为「复习中」，可点击对应知识点重新进入费曼对话
5. 用户确认已掌握 → 状态变为「已掌握」

### 4.4 异常分支处理

1. 学情提交时 Token 过期 → 401 跳转登录页，填写内容不丢失（前端本地缓存）
2. 对话正常结束但漏洞写入失败 → 不阻断用户流程，后端日志记录失败，后续可手动触发同步
3. 同一 kp + 同一维度已存在 open 漏洞 → 不重复插入，更新 score 和 updated_at
4. 游客模式 → 不弹窗学情初始化，不记录漏洞库（所有面向 guest 的漏洞写操作跳过）
5. 个人中心无数据 → 空状态友好提示

---

## 五、数据模型与数据库变更

### 5.1 新增三张表（SQLite）

**负责人说明**：
- 后端 A 负责：user_profile（模型 + DDL）、knowledge_gap（模型 + DDL）
- 后端 B 负责：diagnostic_report（模型 + DDL）
- 建表 DDL 统一在 `core/database.py` 中执行（后端 A 提交时包含三张表，后端 B 只需关心自己那张的模型文件）

#### 1. user_profile 学情表（后端 A）

```sql
CREATE TABLE user_profile (
  user_id         TEXT PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
  nickname        TEXT,
  exam_subject    TEXT,          -- 报考学科：计算机/政治/数学/英语/其他
  exam_sub_category TEXT,        -- 专业方向：如计算机->408统考/自命题
  preparation_stage TEXT,        -- 备考阶段：基础/强化/冲刺
  exam_type       TEXT,          -- 备考类型：应届/二战/在职
  pain_points     TEXT,          -- JSON 数组：["概念理解困难","输出薄弱"]
  target_school   TEXT,          -- 目标院校（可选）
  target_major    TEXT,          -- 目标专业（可选）
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
```

#### 2. knowledge_gap 知识漏洞表（后端 A）

```sql
CREATE TABLE knowledge_gap (
  id              TEXT PRIMARY KEY,     -- gap-xxx
  user_id         TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  kp_id           TEXT NOT NULL,
  kp_name         TEXT NOT NULL,
  material_id     TEXT,
  material_name   TEXT,
  dimension       TEXT NOT NULL,        -- 理解深度/表达完整性/逻辑连贯性/结构化能力
  gap_description TEXT,                 -- 漏洞描述（从报告 analysis 提取）
  severity        INTEGER DEFAULT 3,   -- 严重程度 1-5，基于得分映射
  score           INTEGER NOT NULL,    -- 该维度得分 0-10
  status          TEXT NOT NULL DEFAULT 'open',  -- open/reviewing/resolved
  source_session_id TEXT,
  review_count    INTEGER DEFAULT 0,
  last_reviewed_at TEXT,
  next_review_at  TEXT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX idx_gap_user ON knowledge_gap(user_id);
CREATE INDEX idx_gap_user_status ON knowledge_gap(user_id, status);
CREATE INDEX idx_gap_user_kp ON knowledge_gap(user_id, kp_id, dimension);
```

#### 3. diagnostic_report 诊断报告表（后端 B）

```sql
CREATE TABLE diagnostic_report (
  id              TEXT PRIMARY KEY,     -- rpt-xxx
  user_id         TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  session_id      TEXT,
  kp_id           TEXT NOT NULL,
  kp_name         TEXT NOT NULL,
  material_id     TEXT,
  material_name   TEXT,
  dimensions      TEXT NOT NULL,        -- 完整四维评分 JSON
  total_score     INTEGER NOT NULL,     -- 总分 0-40
  overall_comment TEXT,
  gaps_identified INTEGER DEFAULT 0,    -- 本次发现的漏洞数
  created_at      TEXT NOT NULL
);
CREATE INDEX idx_report_user ON diagnostic_report(user_id);
CREATE INDEX idx_report_user_date ON diagnostic_report(user_id, created_at);
```

### 5.2 核心字段设计约束

1. user_profile 注册时自动创建空记录，所有字段允许为 NULL；
2. 漏洞自动去重规则：同一 user_id + kp_id + dimension + status='open' 的记录不重复创建，仅更新 score；
3. 诊断报告是只读的，写入后不可修改；
4. 游客（user_id='guest'）跳过漏洞和报告写入；
5. severity 映射规则：score 0-3 → severity 5, score 4-5 → severity 4, score 6 → severity 3。

---

## 六、完整接口契约（新增 + 改造接口）

### 6.1 学情模块接口（后端 A）

#### 1. 获取学情 GET /api/v1/user/profile

Header: `Authorization: Bearer {token}`

响应 200：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "user_id": "user-001",
    "nickname": "考研小王",
    "exam_subject": "计算机",
    "exam_sub_category": "408统考",
    "preparation_stage": "基础",
    "exam_type": "应届",
    "pain_points": ["概念理解困难", "输出薄弱"],
    "target_school": "",
    "target_major": ""
  }
}
```

首次注册无数据时响应 200（data 中所有字段为 null，不返回 404）：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "user_id": "user-001",
    "nickname": null,
    "exam_subject": null,
    ...
  }
}
```

#### 2. 提交学情 POST /api/v1/user/profile

请求体：
```json
{
  "nickname": "考研小王",
  "exam_subject": "计算机",
  "exam_sub_category": "408统考",
  "preparation_stage": "基础",
  "exam_type": "应届",
  "pain_points": ["概念理解困难", "输出薄弱"],
  "target_school": "",
  "target_major": ""
}
```

响应 200：
```json
{
  "code": 200,
  "msg": "学情信息已保存",
  "data": {
    "user_id": "user-001",
    "exam_subject": "计算机"
  }
}
```

#### 3. 更新学情 PATCH /api/v1/user/profile

请求体（任意子集）：
```json
{
  "preparation_stage": "强化",
  "pain_points": ["知识碎片化"]
}
```

响应 200：
```json
{
  "code": 200,
  "msg": "学情信息已更新",
  "data": {
    "user_id": "user-001"
  }
}
```

### 6.2 知识漏洞库接口（后端 A）

#### 1. 查询漏洞列表 GET /api/v1/gaps

Query 参数：`status`（可选，默认返回全部），`page`（默认 1），`page_size`（默认 20）

Header: `Authorization: Bearer {token}`

响应 200：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "gap_id": "gap-001",
        "kp_id": "kp-1b7f391d",
        "kp_name": "冒泡排序",
        "dimension": "理解深度",
        "score": 4,
        "severity": 4,
        "status": "open",
        "gap_description": "能描述冒泡排序的步骤，但无法解释其正确性依据和复杂度分析的数学原理",
        "created_at": "2026-07-28T10:30:00"
      }
    ],
    "total": 12,
    "page": 1,
    "page_size": 20
  }
}
```

#### 2. 更新漏洞状态 PATCH /api/v1/gaps/{gap_id}

请求体：
```json
{
  "status": "reviewing"
}
```

或：
```json
{
  "status": "resolved"
}
```

响应 200：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "gap_id": "gap-001",
    "status": "reviewing"
  }
}
```

#### 3. 漏洞统计 GET /api/v1/gaps/stats

Header: `Authorization: Bearer {token}`

响应 200：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "total": 15,
    "by_status": {
      "open": 8,
      "reviewing": 4,
      "resolved": 3
    },
    "by_dimension": {
      "理解深度": 5,
      "表达完整性": 4,
      "逻辑连贯性": 3,
      "结构化能力": 3
    }
  }
}
```

### 6.3 诊断报告接口（后端 B 负责）

#### 1. 历史报告列表 GET /api/v1/reports

Query 参数：`page`（默认 1），`page_size`（默认 20）

Header: `Authorization: Bearer {token}`

响应 200：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "report_id": "rpt-001",
        "kp_id": "kp-1b7f391d",
        "kp_name": "冒泡排序",
        "material_name": "数据结构教材",
        "total_score": 28,
        "dimensions": [
          {"name": "理解深度", "score": 6},
          {"name": "表达完整性", "score": 8},
          {"name": "逻辑连贯性", "score": 7},
          {"name": "结构化能力", "score": 7}
        ],
        "gaps_identified": 1,
        "created_at": "2026-07-28T10:30:00"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20
  }
}
```

#### 2. 报告详情 GET /api/v1/reports/{report_id}

Header: `Authorization: Bearer {token}`

响应 200：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "report_id": "rpt-001",
    "kp_id": "kp-1b7f391d",
    "kp_name": "冒泡排序",
    "material_name": "数据结构教材",
    "session_id": "sess-001",
    "dimensions_full": [
      {
        "name": "理解深度",
        "score": 6,
        "analysis": "能描述冒泡排序的步骤，但无法解释其正确性依据",
        "suggestion": "从循环不变量角度理解冒泡排序的正确性"
      },
      {
        "name": "表达完整性",
        "score": 8,
        "analysis": "覆盖了排序过程和优化方法",
        "suggestion": "补充最好/最坏情况的时间复杂度分析"
      },
      {
        "name": "逻辑连贯性",
        "score": 7,
        "analysis": "逻辑基本通顺",
        "suggestion": "强化步骤之间的因果关系"
      },
      {
        "name": "结构化能力",
        "score": 7,
        "analysis": "结构清晰",
        "suggestion": "使用分点论述会更好"
      }
    ],
    "total_score": 28,
    "overall_comment": "本次讲解体现了对冒泡排序的基础理解...",
    "gaps_identified": 1,
    "created_at": "2026-07-28T10:30:00"
  }
}
```

### 6.4 数据聚合接口（后端 B，P1）

#### 1. 用户概览 GET /api/v1/user/summary

Header: `Authorization: Bearer {token}`

响应 200：
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "profile_exists": true,
    "total_gaps": 12,
    "open_gaps": 8,
    "total_reports": 5,
    "total_materials": 3
  }
}
```

---

## 七、全局 Mock 数据（前后端并行开发专用）

### 7.1 学情 Mock（后端 A）

GET /api/v1/user/profile

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "user_id": "user-demo",
    "nickname": "考研小王",
    "exam_subject": "计算机",
    "exam_sub_category": "408统考",
    "preparation_stage": "基础",
    "exam_type": "应届",
    "pain_points": ["概念理解困难", "输出薄弱"],
    "target_school": "",
    "target_major": ""
  }
}
```

POST /api/v1/user/profile → `{"code": 200, "msg": "学情信息已保存", "data": {"user_id": "user-demo", "exam_subject": "计算机"}}`

### 7.2 漏洞库 Mock（后端 A）

GET /api/v1/gaps

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "gap_id": "gap-demo-1",
        "kp_id": "kp-demo",
        "kp_name": "Dijkstra 算法",
        "dimension": "理解深度",
        "score": 4,
        "severity": 4,
        "status": "open",
        "gap_description": "能描述算法步骤，但无法解释贪心策略的正确性依赖非负权边的前提条件",
        "created_at": "2026-07-28T10:30:00"
      },
      {
        "gap_id": "gap-demo-2",
        "kp_id": "kp-demo",
        "kp_name": "Dijkstra 算法",
        "dimension": "原理证明",
        "score": 3,
        "severity": 5,
        "status": "open",
        "gap_description": "无法证明贪心选择性质，混淆算法正确性和反证法的逻辑",
        "created_at": "2026-07-28T10:30:00"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 20
  }
}
```

GET /api/v1/gaps/stats

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "total": 2,
    "by_status": {"open": 2, "reviewing": 0, "resolved": 0},
    "by_dimension": {
      "理解深度": 1,
      "表达完整性": 0,
      "逻辑连贯性": 0,
      "结构化能力": 1
    }
  }
}
```

PATCH /api/v1/gaps/gap-demo-1 → `{"code": 200, "msg": "success", "data": {"gap_id": "gap-demo-1", "status": "resolved"}}`

### 7.3 历史报告 Mock（后端 B）

GET /api/v1/reports

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "items": [
      {
        "report_id": "rpt-demo-1",
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
        "created_at": "2026-07-28T10:30:00"
      },
      {
        "report_id": "rpt-demo-2",
        "kp_id": "kp-demo2",
        "kp_name": "Floyd 算法",
        "material_name": "数据结构教材",
        "total_score": 32,
        "dimensions": [
          {"name": "理解深度", "score": 8},
          {"name": "表达完整性", "score": 8},
          {"name": "逻辑连贯性", "score": 8},
          {"name": "结构化能力", "score": 8}
        ],
        "gaps_identified": 0,
        "created_at": "2026-07-27T14:20:00"
      }
    ],
    "total": 2,
    "page": 1,
    "page_size": 20
  }
}
```

GET /api/v1/reports/rpt-demo-1 → 返回完整四维报告 JSON

### 7.4 用户概览 Mock（后端 B，P1）

GET /api/v1/user/summary

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "profile_exists": true,
    "total_gaps": 2,
    "open_gaps": 2,
    "total_reports": 2,
    "total_materials": 1
  }
}
```

---

## 八、前端页面交互简要说明

### 8.1 学情初始化弹窗

- 触发时机：注册后首次登录自动弹出（可从 localStorage 判断是否首次）
- 表单字段：
  - 报考学科：下拉选择（计算机/政治/数学/英语/其他）
  - 备考阶段：单选卡片（基础/强化/冲刺）
  - 备考类型：单选卡片（应届/二战/在职）
  - 核心痛点：多选标签（概念理解困难/输出薄弱/知识碎片化/盲目刷题/自律性差）
- 按钮：「保存并开始学习」→ 调 POST profile → 跳转上传页
- 可跳过：「稍后填写」→ 关闭弹窗，入口在个人中心顶部



### 8.2 个人中心页面 `/profile`

- 顶部：用户头像（首字母占位圆）+ 用户名
- 四个 Tab 切换：

**Tab 1：学情档案**
- 展示当前学情信息（学科/阶段/类型/痛点）
- 「编辑」按钮 → 弹出同上学情编辑弹窗

**Tab 2：知识漏洞**
- 三个子 Tab：待复习（open）/ 复习中（reviewing）/ 已掌握（resolved）
- 每条展示：Kp 名称、维度标签（彩色）、得分/满分、严重程度星级
- 操作按钮：「开始复习」→ 状态变 reviewing（可跳转对应 KP 重新讲解）
- 操作按钮：「标记已掌握」→ 状态变 resolved
- 空状态：「暂无知识漏洞，继续保持！」

**Tab 3：历史报告**
- 卡片列表，每条展示：Kp 名称、总分（如 "28/40"）、四维迷你条形图、日期
- 点击卡片 → 展开复用 ReportDrawer 展示完整报告
- 空状态：「暂无历史报告，快去选择一个知识点开始讲解吧」

**Tab 4：我的教材**
- 复用 UploadPage 的教材列表组件
- 仅显示当前登录用户的教材，点击可跳转知识点选择

---

## 九、验收标准

### 9.1 学情初始化

1. 注册后首次登录自动弹窗，填写后保存成功；
2. 点击「稍后填写」弹窗关闭，不阻塞页面跳转；
3. 个人中心可查看/编辑学情信息；
4. 游客登录不弹窗；
5. 存量无学情用户不报错，返回空数据。

### 9.2 知识漏洞库

1. 费曼对话结束后，得分 ≤ 6 的维度自动写入 knowledge_gap 表；
2. 同一 kp + 同一维度已存在 open 记录时更新分数，不重复插入；
3. 漏洞列表按状态过滤正常；
4. 漏洞状态更新（标记已掌握）正常；
5. 统计数据维度分布正确。

### 9.3 诊断报告持久化

1. 每次费曼对话结束后 diagnostic_report 表新增一条记录；
2. 历史报告列表按时间倒序展示正确；
3. 报告详情展开正常显示完整四维评分。

### 9.4 前端

1. 个人中心 4 个 Tab 切换流畅，数据加载正确；
2. 学情初始化弹窗/编辑弹窗交互正常；
3. 漏洞列表状态操作反馈及时；
4. 报告卡片展开/收起正常；
5. 所有页面适配游客/登录用户两套模式。

---

## 十、非功能需求与风险应对

### 10.1 非功能约束

1. 性能：个人中心页面全数据加载 ≤ 2s；
2. 兼容：桌面 Chrome/Edge；
3. 鉴权：所有新增接口统一携带 Bearer Token，无 token 返回 401；
4. 异步：漏洞写入和报告持久化在 LangGraph 节点内同步完成，不引入额外队列（数据量小）；
5. 去重：同一漏洞自动去重，不产生重复记录。

### 10.2 风险与应对方案

| 风险 | 等级 | 应对策略 |
|---|---|---|
| 学情初始化弹窗干扰用户体验 | 低 | 提供「稍后填写」跳过按钮；后续可从个人中心进入 |
| 漏洞写入阻塞对话返回 | 中 | 对话结束后才写入，不阻塞主流程；写入失败仅记录日志 |
| 前端个人中心 4 个 Tab 数据量过大 | 中 | 分页加载（page/page_size）；Tab 懒加载 |
| 存量用户无学情数据 | 低 | 接口返回空字段而非报错，前端渲染空状态 |
| 前后端接口并行依赖 | 中 | 周一先出 Mock 数据（第七章），前端先调 Mock 开发 |

---

## 附录 A：本周砍项（顺延第七周）

1. SRS 间隔复习推送（需定时任务）
2. 个性化复习建议算法（需关联学情画像）
3. 系统预设教材库（等待教材资源）
4. 学科定制化追问 Prompt
5. 错题复盘 / 主观题训练场景
