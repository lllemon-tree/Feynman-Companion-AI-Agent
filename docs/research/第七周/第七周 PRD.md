# 费曼伴学智能体 第七周 PRD（V1.0）

版本：V1.0

日期：2026-08-03

周期：第七周

范围：LLM 对话逻辑优化（痛点感知 Prompt）+ 学科定制追问 + 教材回显修复 + Mock/联调开关治理

团队：后端 + 前端

前置基线：第六周已完成学情画像、知识漏洞库、诊断报告持久化、个人中心 5 个 Tab

---

## 一、产品概述与本周目标

### 1.1 本周核心目标

在第六周数据闭环基础上，本周聚焦**对话质量提升**和**联调体验优化**：

1. **痛点感知 Prompt 引擎**

   当前 LLM evaluate 节点使用通用 Prompt，不感知用户画像（备考阶段、核心痛点）。本周将 user_profile 中的 pain_points / exam_subject / preparation_stage 注入 Prompt 模板，让追问和诊断更具针对性。例如：标注"输出薄弱"的用户，追问侧重引导其多轮输出；标注"概念理解困难"的用户，追问侧重类比和生活化解释。

2. **学科定制化追问与诊断**

   当前四维诊断对所有学科使用同一套维度和追问策略。本周按学科（计算机/数学/政治/英语）区分 Prompt 侧重点：
   - 计算机：侧重算法正确性证明、复杂度分析
   - 数学：侧重定理条件验证、反例构造
   - 政治：侧重概念辨析、时政关联
   - 英语：侧重语法规则应用、句式变换

3. **联调 Mock/开关治理**

   当前 `.env.development` 默认 `VITE_USE_FEYNMAN_MOCK=true`，导致前端注册、教材列表等功能未真正走后端。本周统一清理 Mock 开关策略：开发阶段 Mock 仅用于 LLM 对话降级，CRUD 操作（注册/登录/学情/漏洞/报告/教材列表）全部走真实 API。

4. **前端缺陷修复与体验优化**

   - 修复 "我的教材" Tab 不回显真实上传教材（去掉 Mock 硬编码）
   - 知识漏洞列表按 kp_id 分组展示（一张卡片包含四个维度评分）
   - 登录/注册页 Mock 开关提示

### 1.2 本周非目标（顺延后续迭代）

1. SRS 间隔复习推送（需定时任务 + 复习提醒 UI）
2. 错题复盘 / 主观题训练场景
3. 系统预设教材库（等待资源就绪）
4. 移动端适配

### 1.3 成功指标

| 指标 | 目标值 |
|---|---|
| 痛点感知 Prompt 注入后，用户追问轮次有效性提升 | 低分维度（≤6）占比下降 ≥ 10% |
| 学科定制 Prompt 切换正确率（按 exam_subject 匹配） | 100% |
| 前端注册/登录走真实 API 成功率 | ≥ 98% |
| "我的教材" Tab 回显真实上传教材 | 100% |
| 知识漏洞按 KP 聚合展示 | 100% |
| 后端对话日志清爽（仅含 user_input + chunk_ids） | 每轮 ≤ 3 行 |

---

## 二、团队分工

| 角色 | 负责模块 | 操作文件 |
|---|---|---|
| 后端 A | 1. Prompt 模板重构（痛点感知 + 学科定制）；2. user_profile 注入 evaluate/report 节点；3. Prompt 管理模块抽离 | **新建**：`services/prompt_builder.py` **修改**：`graphs/feynman_graph.py`、`services/deepseek_client.py`、`services/mock_llm.py` |
| 后端 B | 1. 后端 MATERIAL_MOCK 环境变量清理；2. 联调 bug 修复；3. 对话日志精简 | **修改**：`services/feynman_service.py`、`graphs/feynman_graph.py`（日志）、`core/config.py` |
| 前端 | 1. 注册/登录去掉 Mock 走真实 API；2. 知识漏洞按 KP 分组 UI；3. "我的教材" 真实数据回显 | **修改**：`views/AuthPage.vue`、`views/ProfilePage.vue`、`api/feynman.js`、`.env.development` |

---

## 三、功能点清单

### 3.1 后端 A：痛点感知 Prompt 引擎（P0）

#### 1. Prompt 构建器抽离

将当前散落在 `deepseek_client.py` / `mock_llm.py` 中的 evaluate prompt 拼装逻辑抽到 `services/prompt_builder.py`：

```
prompt_builder.py
├── build_system_prompt(profile, subject) → str     # 系统角色 + 学科定向
├── build_evaluate_prompt(profile, kp, history, chunks) → str  # 评估追问
└── build_report_prompt(profile, kp, history) → str  # 四维诊断
```

#### 2. 痛点注入规则

从 `user_profile` 读取 `pain_points`，映射为 Prompt 指令：

| 痛点 | Prompt 追加指令 |
|---|---|
| 概念理解困难 | "学习者对抽象概念理解有困难，追问时多用生活类比和具体例子，避免纯术语堆砌" |
| 输出薄弱 | "学习者口头表达/文字输出能力弱，追问时引导其多轮输出，从一句话逐步扩展到完整段落" |
| 知识碎片化 | "学习者知识点分散不成体系，追问时强调知识之间的关联和层级结构" |
| 盲目刷题 | "学习者倾向机械刷题而非理解原理，追问时少给题目、多问'为什么'" |
| 自律性差 | "学习者需要外部激励，追问时多给正向反馈和阶段性肯定" |

#### 3. 备考阶段感知

| 阶段 | Prompt 追加指令 |
|---|---|
| 基础 | "学习者处于基础阶段，追问侧重概念定义和基本流程，不要求严格证明" |
| 强化 | "学习者处于强化阶段，追问侧重跨知识点关联和方法对比" |
| 冲刺 | "学习者处于冲刺阶段，追问侧重易错点辨析和实战应用" |

#### 4. 学科定制 Prompt

不同学科的 evaluate 和 report 指令差异化：

- **计算机**：重点是算法正确性证明、复杂度分析、数据结构选择理由
- **数学**：重点是定理条件验证（缺条件是否成立）、反例构造、证明步骤严密性
- **政治**：重点是概念辨析（如"人民"vs"公民"）、核心观点串联、时政材料分析
- **英语**：重点是语法规则应用（为什么用这个时态）、句式变换后的语义变化

#### 5. Prompt 注入时机

在 `feynman_graph.py` 的 `_load_context` 节点中，新增 `user_profile` 加载：

```python
# _load_context 新增步骤
profile = user_profile_service.get_profile_by_user_id(session_db, session.user_id)
state["user_profile"] = profile  # 全链路传递
```

后续 `_evaluate` 和 `_report` 节点调用 `prompt_builder` 时传入 profile。

### 3.2 后端 B：联调治理 + 日志精简（P0）

#### 1. MATERIAL_MOCK 环境变量清理

当前 `config.py` 中有 `MATERIAL_MOCK` 设置项，后端 `/material/tree` 和 `/material/upload` 的 mock 分支应统一由 `LLM_PROVIDER` 控制：LLM 不可用时只降级对话部分，CRUD 操作永不 mock。

#### 2. 对话日志精简

已完成（本周提前修）：
- `feynman_service.py`：只打印 `📝 user_input: {前120字}`
- `feynman_graph.py`：只打印 `📚 grounding chunks (N): [chunk_id, ...]`

#### 3. 未登录用户引导优化

游客点击 Profile 各 Tab 时统一提示"登录后查看"，不在前端请求 API（避免 401 刷屏）。

### 3.3 前端（P0）

#### 1. Mock 开关治理

`.env.development` 默认值调整：

```env
# 之前：所有功能走 Mock → 注册/登录/教材等都不走后端
VITE_USE_FEYNMAN_MOCK=true

# 之后：仅 LLM 对话降级走 Mock，CRUD 走真实 API
VITE_USE_FEYNMAN_MOCK=false   # 注册/登录/学情/漏洞/报告/教材 走真实后端
```

API 层改造：
- `login()` / `register()` / `getUserProfile()` / `saveUserProfile()` / `getGaps()` / `updateGapStatus()` / `getReports()` / `getReportDetail()` → 去掉 `USE_FEYNMAN_MOCK` 分支，直接调后端
- `chatWithAgent()` / `fetchGreeting()` → 保留 Mock 降级（DeepSeek 不可用时）
- `uploadMaterial()` / `getMaterialStatus()` / `getKnowledgeTree()` → 去掉 Mock 分支

#### 2. "我的教材" Tab 修复

已完成（本周提前修）：
- `loadMaterials()` 不再依赖 `VITE_USE_MATERIAL_MOCK`
- 先调 `fetchSubjects()` 获取用户所有学科
- 再逐学科调 `getKnowledgeTree(subject)` 拼装教材列表

#### 3. 知识漏洞按 KP 分组展示

已完成（本周提前修）：
- 新增 `groupedGaps` computed 属性按 `kp_id` 聚合
- 每张卡片展示一个 KP，内含四个维度的得分条 + 描述 + 操作按钮
- 每个维度独立状态管理（open/reviewing/resolved）

#### 4. 注册/登录页 Mock 提示

在 AuthPage 底部增加一行小字："当前环境：{Mock 模式 / 后端联调模式}"，帮助开发者辨别当前状态。从 `.env.development` 的 `VITE_USE_FEYNMAN_MOCK` 读取。

---

## 四、完整用户流程

### 4.1 痛点感知对话流程

1. 用户已填写学情画像（pain_points: ["输出薄弱", "概念理解困难"]，preparation_stage: "基础"）
2. 用户选择知识点"冒泡排序" → 进入费曼对话
3. 后端 `_load_context` 加载 user_profile
4. `prompt_builder` 拼装 Prompt：
   - 系统指令追加："学习者对抽象概念理解有困难…学习者口头表达能力弱…"
   - 阶段指令追加："学习者处于基础阶段，追问侧重概念定义和基本流程"
   - 学科指令追加："计算机学科，侧重算法步骤描述和基本复杂度概念"
5. LLM 生成追问：倾向引导用户逐步输出、用类比解释，不要求严格证明
6. 3 轮后生成报告：四维评分注释中体现痛点针对性建议

### 4.2 学科定制诊断流程

1. 用户学情 exam_subject = "数学"
2. 选择知识点"极限的定义" → 进入对话
3. 后端识别学科 = 数学 → Prompt 侧重定理条件验证和反例
4. 追问示例："如果去掉 ε>0 这个条件，极限定义还成立吗？你能否构造一个反例？"
5. 报告维度中"理解深度"侧重条件的必要性分析

### 4.3 联调模式注册流程（修复后）

1. 前端 `VITE_USE_FEYNMAN_MOCK=false`
2. 用户填写注册表单 → 点击注册
3. 前端发送 `POST /api/v1/auth/register` → 后端写入 SQLite
4. 注册成功自动登录 → 弹出学情初始化弹窗
5. 上传教材 → PDF 解析 → 知识点抽取 → 向量化入库
6. 进入 Profile → "我的教材" Tab → 看到刚上传的教材

---

## 五、技术设计要点

### 5.1 Prompt Builder 架构

```
                    ┌─────────────────┐
                    │  PromptBuilder   │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                 ▼
     build_system()   build_evaluate()   build_report()
            │                │                 │
            ▼                ▼                 ▼
     ┌──────────┐    ┌──────────────┐   ┌──────────────┐
     │ 角色设定  │    │ user_input    │   │ 对话历史      │
     │ 学科定向  │    │ 对话历史      │   │ KP 原文       │
     │ 痛点指令  │    │ KP 原文       │   │ grounding     │
     │ 阶段指令  │    │ grounding     │   │ 痛点诊断侧重  │
     └──────────┘    │ 追问引导      │   │ 学科评分标准  │
                     └──────────────┘   └──────────────┘
```

### 5.2 profile 缓存策略

`user_profile` 在单次会话中不变，在 `_load_context` 中加载一次后通过 state 全链路传递，避免每个节点重复查库。

### 5.3 Mock 开关分层

```
层级 1 (永不 Mock)：auth、user_profile、knowledge_gap、diagnostic_report、material CRUD
层级 2 (LLM 故障时降级 Mock)：feynman/chat、feynman/greeting
层级 3 (开发阶段可选 Mock)：material/upload 进度模拟（通过后端 MATERIAL_MOCK 控制）
```

---

## 六、验收标准

### 6.1 痛点感知 Prompt

1. `prompt_builder.py` 独立模块，包含 `build_system_prompt` / `build_evaluate_prompt` / `build_report_prompt`
2. 在 `_load_context` 中加载 user_profile，注入 state 全链路传递
3. evaluate 和 report 节点的 Prompt 包含用户痛点指令
4. 无学情画像时使用默认 Prompt，不报错
5. 游客模式使用默认 Prompt

### 6.2 学科定制

1. 四门学科（计算机/数学/政治/英语）有独立的 Prompt 指令片段
2. 根据 user_profile.exam_subject 自动选择对应指令
3. 未填学科时默认走通用 Prompt

### 6.3 联调治理

1. 前端 CRUD 类 API（注册/登录/学情/漏洞/报告/教材）不带 Mock 分支
2. 前端"我的教材"Tab 能回显用户真实上传的教材
3. 知识漏洞按 KP 分组展示，每个 KP 一张卡片含四维度
4. 后端对话日志每条 ≤ 3 行，仅含 user_input 和 chunk_ids
5. 游客访问 Profile 不发送 API 请求

### 6.4 整体回归

1. 第六周全量功能不受影响（学情/漏洞/报告/个人中心）
2. 后端现有 30 个测试全部通过
3. 新增 prompt_builder 单元测试 ≥ 5 个

---

## 附录 A：本周砍项（顺延第八周）

1. SRS 间隔复习推送（需定时任务 + 复习提醒 UI）
2. 错题复盘 / 主观题训练场景
3. 系统预设教材库（等待教材资源）
4. 知识漏洞的 SRS 复习调度算法
