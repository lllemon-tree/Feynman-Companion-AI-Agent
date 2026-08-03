# 费曼伴学智能体 第七周 PRD（V1.0）

版本：V1.0

日期：2026-08-03

周期：第七周

范围：痛点感知 Prompt 引擎 + 个性化复习建议 + SRS 复习提醒 + 学情掌握度统计

团队：2 后端 + 1 许嘉琪

前置基线：第六周已完成学情画像/知识漏洞库/诊断报告持久化/个人中心 5 个 Tab

---

## 一、产品概述与本周目标

### 1.1 本周核心目标

在第六周数据闭环基础上，本周聚焦**对话质量提升**和**复习闭环搭建**：

1. **痛点感知 Prompt 引擎**

   当前 LLM evaluate/report 节点使用通用 Prompt，不感知用户在学情画像中填写的 pain_points（概念理解困难/输出薄弱/知识碎片化/盲目刷题/自律性差）和 preparation_stage（基础/强化/冲刺）。本周将 user_profile 中的痛点与阶段信息注入 Prompt 模板，让追问和诊断更具针对性。

2. **个性化复习建议**

   当前对话结束只返回四维评分报告，没有"下一步该做什么"的指引。本周在诊断报告末尾新增"复习计划"内容，自动生成教材重读指引、同类知识点推荐、学习优先级建议。

3. **SRS 间隔复习提醒（无定时任务版）**

   knowledge_gap 表已有 `next_review_at`、`review_count`、`last_reviewed_at` 字段。本周实现：漏洞标记为"复习中"时自动计算下次复习时间（1/3/7/14/30 天），许嘉琪新增「今日待复习」入口查询到期漏洞，用户手动进入复习。

4. **学情掌握度统计**

   对 diagnostic_report 表做聚合查询，Profile 页展示：已讲解 KP 数、各维度平均分、薄弱维度分布、总分趋势。

### 1.2 本周非目标（顺延后续迭代）

1. 学科定制化追问 Prompt（数学/政治/计算机/英语差异化策略——等教材覆盖更多学科后启动）
2. SRS 定时推送通知（需后台调度 + 通知渠道，P2）
3. 错题复盘 / 主观题训练场景（独立大模块，第八周+）
4. 系统预设教材库（等待教材资源就绪）

### 1.3 成功指标

| 指标 | 目标值 |
|---|---|
| 痛点 Prompt 注入后 evaluate/report 正常返回 | 100%（无格式错误/无空值） |
| 无学情画像用户使用默认 Prompt，不报错 | 100% |
| 报告末尾复习计划正常返回 | 100% |
| SRS next_review_at 自动计算正确（1/3/7/14/30 天） | 100% |
| 今日待复习查询返回正确到期漏洞列表 | 100% |
| 学情统计接口返回正确聚合数据 | 100% |
| 后端现有 30 个测试全部通过 | 100% |

---

## 二、团队分工

| 角色 | 负责模块 |
|---|---|
| 马茗燕 | ① 痛点感知 Prompt 引擎（学情画像 → Prompt 指令）；② 对话后的个性化复习计划生成；③ LangGraph evaluate/report 节点改造 |
| 陈艺博 | ① SRS 间隔复习提醒（next_review_at 自动计算 + 今日待复习查询）；② 学情掌握度统计（诊断报告聚合查询） |
| 许嘉琪 | ① 诊断报告底部新增复习计划展示；② 知识漏洞 Tab 新增「今日待复习」入口；③ Profile 页新增学情统计概览 |

---

## 三、功能点清单

### 3.1 马茗燕：痛点感知 Prompt + 个性化复习建议（P0）

#### 1. Prompt 构建器抽离 —— `services/prompt_builder.py`

当前 evaluate/report 的 Prompt 拼装逻辑散落在 `deepseek_client.py` 和 `mock_llm.py` 中，本周抽到独立的 `prompt_builder.py`：

```
prompt_builder.py
├── build_system_prompt(profile) → str        # 系统角色 + 痛点指令 + 阶段指令
├── build_evaluate_prompt(profile, kp, history, grounding_chunks) → str
└── build_report_prompt(profile, kp, history) → str
```

#### 2. 痛点 → Prompt 指令映射

从 `user_profile.pain_points` 读取，映射为追加指令：

| 痛点 | 追加 Prompt 指令 |
|---|---|
| 概念理解困难 | "学习者对抽象概念理解有困难。追问时多用生活类比和具体例子引导，避免纯术语堆砌。评价时重点关注'是否能用大白话解释核心原理'。" |
| 输出薄弱 | "学习者口头表达/文字输出能力弱、不善组织语言。追问时采用'先简后详'策略——第一轮让用户一句话概括，第二轮扩展到段落，第三轮要求完整讲解。评价时不过度扣表达完整性的分，但引导用户逐步输出。" |
| 知识碎片化 | "学习者知识点分散、不成体系。追问时强调知识之间的关联，例如'这个概念和你之前学的 X 有什么联系？''它在整个章节中处于什么位置？'" |
| 盲目刷题 | "学习者倾向机械刷题而非理解原理。追问时少给题目、多问'为什么'。评价时重点扣'理解深度'维度，引导用户关注原理而非答案。" |
| 自律性差 | "学习者需要外部激励和明确指引。追问语气温暖坚定，多给正向反馈和阶段性肯定（如'这一步理解得很好'），并在每轮结束时明确告知下一步要做什么。" |

#### 3. 备考阶段 → Prompt 指令映射

| 阶段 | 追加 Prompt 指令 |
|---|---|
| 基础 | "学习者处于基础阶段，刚接触该学科。追问侧重概念定义和基本流程的确认，不要求严格证明和跨知识点关联。评分时适当放宽'理解深度'标准。" |
| 强化 | "学习者处于强化阶段，已完成一轮基础复习。追问侧重跨知识点关联、方法对比和适用条件辨析。评分标准正常。" |
| 冲刺 | "学习者处于冲刺阶段，临近考试。追问侧重易错点辨析、高频考点的深度理解和实战应用。评分时严格对待概念混淆问题。" |

#### 4. 无画像 / 游客兼容

- `user_profile` 为空或 `pain_points` 为空 → 使用默认 Prompt，不追加任何痛点/阶段指令
- 游客模式 → 使用默认 Prompt
- 注入失败 → 不阻断对话，降级为默认 Prompt

#### 5. 画像数据注入位置

在 `feynman_graph.py` 的 `_load_context` 节点中加载 profile，通过 `FeynmanGraphState` 全链路传递：

```python
# _load_context 新增
from backend.app.services.user_profile_service import UserProfileService

profile = UserProfileService.get_profile_by_user_id(session_db, session.user_id)
state["user_profile"] = profile  # 后续 evaluate/report 节点可用
```

#### 6. 个性化复习建议 —— `review_plan` 字段

在 `models/feynman.py` 的 `FinalReport` 或 `FeynmanChatData` 中新增 `review_plan` 字段：

```json
{
  "review_plan": {
    "reread_guide": [
      {
        "priority": 1,
        "material_name": "数据结构教材",
        "page_hint": "第 3 章 第 30-33 页",
        "focus": "贪心策略的正确性证明——反证法推导过程",
        "reason": "理解深度得分偏低（4/10），未能解释为何非负权边是前提条件"
      }
    ],
    "related_kps": [
      { "kp_id": "kp-xxx", "kp_name": "Floyd 算法", "relation": "同为最短路径算法，对比较多源与单源的区别" }
    ],
    "priority_order": [
      { "rank": 1, "dimension": "理解深度", "kp_name": "Dijkstra 算法", "suggestion": "优先复习贪心策略正确性证明" }
    ]
  }
}
```

生成逻辑放在 `prompt_builder.py` 或 `diagnostic_report_service.py` 中，由 report 节点调用 LLM 生成（与四维评分用同一轮 LLM 调用，不额外增加请求）。

### 3.2 陈艺博：SRS 复习提醒 + 学情统计（P0）

#### 1. SRS 复习提醒

**自动计算 next_review_at**

在 `knowledge_gap_service.py` 的 `update_gap_status` 中，当 status 变为 `reviewing` 时自动计算下次复习时间：

| review_count | 间隔 | 含义 |
|---|---|---|
| 1 | 1 天 | 第一次复习 |
| 2 | 3 天 | 第二次复习 |
| 3 | 7 天 | 第三次复习 |
| 4 | 14 天 | 第四次复习 |
| 5+ | 30 天 | 长期复习 |

同时在 `startReviewKp`（许嘉琪调用）或后端接口中，当用户点击"开始复习"时递增 review_count 并写入 next_review_at。

**今日待复习查询**

在 `api/knowledge_gap.py` 中新增接口或扩展现有 `GET /api/v1/gaps`：

```
GET /api/v1/gaps/review-due
```

Query 参数：无额外参数，按当前用户 + `next_review_at <= today` 过滤，按优先级（severity DESC）排序。

返回格式与 `GET /api/v1/gaps` 一致。

#### 2. 学情掌握度统计 API

新增聚合接口：

```
GET /api/v1/user/stats
```

Header: `Authorization: Bearer {token}`

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "total_kps_learned": 12,
    "total_sessions": 18,
    "avg_total_score": 28.5,
    "dimension_avg": {
      "理解深度": 6.8,
      "表达完整性": 7.2,
      "逻辑连贯性": 7.0,
      "结构化能力": 7.5
    },
    "weakest_dimension": "理解深度",
    "recent_trend": [
      { "date": "2026-07-28", "total_score": 24 },
      { "date": "2026-07-30", "total_score": 28 },
      { "date": "2026-08-01", "total_score": 32 }
    ]
  }
}
```

实现：对 `diagnostic_report` 表做 SQL 聚合查询即可。

### 3.3 许嘉琪（P0）

> 以下为许嘉琪功能需求描述，许嘉琪同学根据交互逻辑自行设计 UI 原型和布局细节。

#### 1. 诊断报告展示复习建议

**场景**：用户完成费曼对话，看到诊断报告。

**新增内容**：报告底部增加「📋 复习建议」区域，展示 `review_plan` 的三块内容：
- **教材重读指引**：卡片形式，显示优先级序号、教材名、页码提示、重点关注内容、原因
- **同类知识点推荐**：标签/列表形式，显示知识点名称和关联说明，点击可跳转开始新对话
- **学习优先级排序**：编号列表，按维度+KP给出复习顺序

**已有组件复用**：`ReportDrawer.vue` 和 `ReportCard.vue` 中需要在现有四维评分下方追加此区域。

#### 2. 知识漏洞 Tab 新增「今日待复习」

**场景**：用户打开 Profile → 知识漏洞 Tab。

**新增入口**：在三个状态子 Tab（待复习/复习中/已掌握）上方或旁边新增「🔔 今日待复习（N）」入口。

**交互逻辑**：
- 点击后展示 `GET /api/v1/gaps/review-due` 返回的到期漏洞列表
- 每条显示：KP 名称 + 上次复习时间 + 严重程度
- 每张 KP 卡片有「开始复习」按钮 → 调用 PATCH 更新状态为 reviewing + 自动计算 next_review_at
- 列表中 KP 卡片可点击展开查看四个维度详情（复用已有折叠逻辑）
- 空状态：「🎉 今天没有需要复习的内容，继续保持！」

**状态转换规则**：
- 用户点击「开始复习」→ 该 KP 下所有 open 维度 → reviewing，review_count +1，next_review_at 按 SRS 规则计算
- 用户再次进入费曼对话讲解该 KP → 对话结束 → 新报告覆盖 → 对应的 gap 状态更新

#### 3. Profile 页新增学情统计概览

**场景**：用户进入 Profile 页面。

**位置**：用户信息卡片下方、Tab 切换上方（或作为学情档案 Tab 的顶部区域）。

**展示内容**（调用 `GET /api/v1/user/stats`）：
- 已学习知识点数 / 总对话次数
- 四维度平均分（迷你柱状图或进度条）
- 最薄弱维度高亮提示
- 最近几次总分趋势（折线图或迷你条形图，可选——许嘉琪自行判断是否用 echarts mini chart）

**空状态**：无学习记录时显示"尚未开始学习，去选择一个知识点开始吧" + 跳转按钮。

---

## 四、完整用户流程

### 4.1 痛点感知对话流程（以"输出薄弱+基础阶段"为例）

1. 用户已填写学情：pain_points=["输出薄弱", "概念理解困难"]，preparation_stage="基础"
2. 选择知识点"冒泡排序" → 进入费曼对话
3. greeting 引导语正常
4. 用户第一轮讲解（简短一句话）
5. 后端 evaluate：Prompt 注入"输出薄弱"策略 → LLM 追问："说得不错！你能再扩展一下吗？冒泡排序具体每一步发生了什么？"
6. 用户第二轮扩展讲解
7. 后端 evaluate：Prompt 继续引导输出 → LLM 追问："很好，比刚才详细多了。那如果数组已经排好序了，冒泡排序还会继续比较吗？"
8. 用户第三轮完整讲解
9. 生成报告：评分时考虑"基础阶段"，不因缺少复杂度证明而过度扣分
10. 报告末尾附带 review_plan（重读指引 + 同类 KP + 优先级）

### 4.2 SRS 复习流程

1. 用户 8月3日 对话结束，Dijkstra 算法"理解深度"得分 4 分 → gap 入库，状态 open
2. 用户在 Profile → 知识漏洞 → 点击 KP 卡片的「开始复习」
3. gap 状态 → reviewing，review_count = 1，next_review_at = 8月4日
4. 用户 8月4日 打开 Profile → 知识漏洞 → 「今日待复习（1）」有红点
5. 点击进入 → 看到 Dijkstra 待复习 → 点击「开始复习」→ review_count = 2，next_review_at = 8月7日
6. 用户进入费曼对话重新讲解 → 系统评分 ≥ 6 → 标记为 resolved

### 4.3 异常分支处理

1. **痛点为空的存量用户**：使用默认 Prompt，不报错
2. **LLM 生成 review_plan 失败**：review_plan 字段为 null，报告其余部分正常返回
3. **SRS next_review_at 计算失败**：默认设为 1 天后
4. **游客访问统计接口**：返回 401
5. **统计接口无数据**：返回全 0 值，许嘉琪展示空状态

---

## 五、数据模型变更

### 5.1 新增字段（knowledge_gap 表已有，确认使用）

`knowledge_gap` 表已包含 SRS 所需字段，无需 DDL 变更：

- `review_count` INTEGER DEFAULT 0 — 复习次数
- `last_reviewed_at` TEXT — 上次复习时间
- `next_review_at` TEXT — 下次推荐复习时间

### 5.2 新增模型（feynman.py）

```python
class ReviewPlanItem(BaseModel):
    priority: int
    material_name: str
    page_hint: str
    focus: str
    reason: str

class RelatedKp(BaseModel):
    kp_id: str
    kp_name: str
    relation: str

class PriorityItem(BaseModel):
    rank: int
    dimension: str
    kp_name: str
    suggestion: str

class ReviewPlan(BaseModel):
    reread_guide: list[ReviewPlanItem] = []
    related_kps: list[RelatedKp] = []
    priority_order: list[PriorityItem] = []
```

`FeynmanChatData` 新增字段：
```python
review_plan: Optional[ReviewPlan] = None
```

---

## 六、验收标准

### 6.1 痛点感知 Prompt

1. `prompt_builder.py` 独立模块，包含 `build_system_prompt` / `build_evaluate_prompt` / `build_report_prompt`
2. evaluate 和 report 节点的 Prompt 包含用户痛点/阶段指令（当 profile 存在且非空时）
3. 无画像/游客时降级为默认 Prompt，不报错
4. 现有 30 个后端测试全部通过（特别注意 feynman 相关测试不受影响）

### 6.2 个性化复习建议

1. `generate_report` 响应中 `review_plan` 字段正常返回（非 null）
2. `review_plan.reread_guide` 至少包含 1 条重读指引（当存在低分维度时）
3. `review_plan.related_kps` 包含同一教材/章节的其他 KP（当存在时）

### 6.3 SRS 复习提醒

1. 点击「开始复习」后 review_count 递增，next_review_at 按 1/3/7/14/30 规则正确计算
2. `GET /api/v1/gaps/review-due` 正确返回到期漏洞列表
3. 许嘉琪「今日待复习」入口正确展示到期数量和列表

### 6.4 学情统计

1. `GET /api/v1/user/stats` 返回正确的聚合数据
2. 无数据时返回全 0，不报错
3. 许嘉琪统计概览正常展示（有数据时）/ 空状态展示（无数据时）

---

## 附录 A：本周砍项（顺延第八周+）

1. 学科定制化追问（数学/政治/计算机/英语）—— 等教材库覆盖多学科后启动
2. SRS 定时推送通知 —— 需后台调度 + 推送渠道
3. 错题复盘 / 主观题训练场景 —— 独立大模块
4. 系统预设教材库 —— 等待教材资源
5. 知识图谱 / 双模型核验 —— V3 远期
