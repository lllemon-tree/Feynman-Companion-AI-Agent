# 第10周优化点 · 前端修改计划（收窄版）

## 一、范围界定

**仅做纯前端条目，只修改 `frontend/` 目录。**

纳入本次修改（共 5 组）：

| 优化点 | 本次前端工作 |
|--------|--------------|
| #2 知识点状态、文案统一 | SelectPage 知识点徽标改为"待复习/已掌握"；卡片弹窗按钮文案统一 |
| #5 历史会话入口改造 | 入口放进"学习历史"页（原"学习报告"）：页面显示学习历史卡片，每张卡片可查看历史会话与学习报告 |
| #6 知识点学习 / 教材切片解析差异化 | 仅做标题、眉标、配色的轻量区分 |
| #7 复习相关知识卡片 | 进入复习后自动显示、复习完成时刷新再显示；带"关闭"按钮；结果面板可手动重开 |
| #9 删除"复习中"状态 | 只留"待复习/已掌握"；reviewing 项暂不在任何分组中展示 |
| #11 学习报告更名与改 UI | 侧栏与页面名称"学习报告"改为"学习历史"；历史页 UI 配合历史会话入口重排。**"个人中心入口移植"本次忽略** |

**明确不做：**

- #1（PDF 要求/解析速度）：属后端，本次不动。
- #4（低分自动加入）、#10（手动/自动来源）：接口与按钮现状已满足，仅在冒烟中验证，不写改动。
- #12（登出按钮）：侧栏下拉中已有，不再新增。
- #3（主动评估按钮）：ChatView 已具备，仅验证。
- 侧栏 SRS 数量角标：收窄去掉。

## 二、仓库调研结论

- 技术栈：Vue 3 `<script setup>` + Pinia + Vue Router + axios + ECharts + Vite。
- 关键文件：
  - [ProfilePage.vue](file:///d:/homework/Feynman/Feynman/Feynman/Feynman-Companion-AI-Agent/frontend/src/views/ProfilePage.vue)：一个页面内含 profile/gaps/sessions/reports/materials/favorites 六个 tab；学习报告当前为 reports tab 下的简单列表。
  - [SelectPage.vue](file:///d:/homework/Feynman/Feynman/Feynman/Feynman-Companion-AI-Agent/frontend/src/views/SelectPage.vue)：四级选择 + 内嵌知识卡片弹窗；知识点徽标在 L469-473，当前显示"未学习/已学习"；卡片弹窗 footer 按钮 L579-581 当前文案"开始费曼讲解"。
  - [ChatView.vue](file:///d:/homework/Feynman/Feynman/Feynman/Feynman-Companion-AI-Agent/frontend/src/views/ChatView.vue)：复习模式状态齐备（isReviewMode、reviewId、reviewSessionId、reviewResult），已支持 `?sessionId=` 恢复。
  - [ReviewResultPanel.vue](file:///d:/homework/Feynman/Feynman/Feynman/Feynman-Companion-AI-Agent/frontend/src/components/ReviewResultPanel.vue)：底部 next-actions 目前只有"返回个人中心/继续学习"。
  - [KnowledgePage.vue](file:///d:/homework/Feynman/Feynman/Feynman/Feynman-Companion-AI-Agent/frontend/src/views/KnowledgePage.vue)：教材知识点管理与原文切片预览。
- 可复用接口（[feynman.js](file:///d:/homework/Feynman/Feynman/Feynman/Feynman-Companion-AI-Agent/frontend/src/api/feynman.js)）：
  - `getSessionList()`：项含 session_id、kp_name、material_title、created_at（**无 kp_id**）。
  - `getSessionDetail(id)`：含 chat_history、report_data。
  - `getReports()`：items 含 report_id、**kp_id**、kp_name、material_name、total_score、dimensions、created_at。
  - `getReportDetail(id)`、`getKnowledgeCard(kpId)`、`getGaps(status)`、`getReviewDueGaps()`、`getUserStats()`。
- 磁盘版 [ReportCard.vue](file:///d:/homework/Feynman/Feynman/Feynman/Feynman-Companion-AI-Agent/frontend/src/components/ReportCard.vue) 已含"添加到复习列表"按钮及自动加入文案，#4 无需改造。

## 三、具体 UI 设计与文件改动

### 改动 1："学习报告"更名为"学习历史" + 历史页 UI 重排

文件：
- `frontend/src/components/AppSidebar.vue`：导航项 L22 `{ label: '学习报告', ... }` label 改为"**学习历史**"（跳转地址不变，仍为 /profile?tab=reports）。
- `frontend/src/views/ProfilePage.vue`：pageTitle（L17-24）reports 对应文案改为"学习历史"；reports tab 区块（约 L1053-1129）整体重排。

布局（替换现有简单报告列表；不做个人中心入口列）：

```
┌─ profile-main（max-width 960px） ──────────────────────────────┐
│ 区块标题"学习历史"（卡片总数在右侧）                            │
│ ┌─ 学习历史卡片（两列网格，宽屏 2 列 / 窄屏 1 列）──────────┐  │
│ │ Dijkstra 算法                              24 / 40（徽标）│  │
│ │ 数据结构教材 · 7月28日                                      │  │
│ │ 四维迷你条：■■■ ■■ ■■■ ■■■                                  │  │
│ │            [ 历史会话 ]            [ 学习报告 ]             │  │
│ └────────────────────────────────────────────────────────────┘  │
│ …（卡片按时间倒序）                                             │
└────────────────────────────────────────────────────────────────┘
```

交互细节：

- 进入 reports tab 时 `Promise.all([getSessionList(), getReports()])` 并行加载。
- **学习历史卡片合并规则**：以 reports 为主表（含 kp_id、分数、四维）生成卡片；再追加 sessions 中按 `kp_name + 同一自然日 created_at` 匹配不到任何 report 的会话（保证无报告的学习也有卡片）；统一按时间倒序。
- 卡片内容：KP 名称 + 总分徽标（total_score/40；≥32 绿、24-31 蓝、<24 橙）；教材名与日期；有报告时显示四条维度迷你进度条（复用 reports 现有 dim-bar 样式）。
- 卡片按钮：
  - **历史会话**：打开既有"会话详情"抽屉（复用 viewSessionDetail 逻辑：对话历史 + 继续对话 → `/study?sessionId=`）；匹配不到会话时按钮置灰，提示"暂无会话记录"。
  - **学习报告**：调用 viewReportDetail 打开 ReportDrawer；无报告时置灰，提示"暂无学习报告"。
- 空状态：保留现有 empty 版式，主按钮"开始学习"→ `/select`。

### 改动 2：复习计划（gaps tab）只保留两态 + SRS 自动展开

文件：`frontend/src/views/ProfilePage.vue`

- `gapStatusTabs`（L225-229）删除 `{ key: 'reviewing', label: '复习中' }`，只留：
  - 待复习（open，红色）、已掌握（resolved，绿色）；各带计数（优先 gapStats.by_status，兜底用当前列表长度）。
- **reviewing 项不在任何分组展示**：两个 tab 分别调 `getGaps('open')` 与 `getGaps('resolved')`，不做前端合并；处于 active 复习中的漏洞仅通过"今日待复习"区块进入。
- 进入 gaps tab 时自动执行 `getReviewDueGaps()` 并展开"🔔 今日待复习"区块（现状需手点按钮）；区块保留折叠按钮；空列表显示现有空态。

### 改动 3：SelectPage 知识点两态与文案

文件：`frontend/src/views/SelectPage.vue`

- L469-473 徽标逻辑改为直接映射 `learning_status`：
  - `unlearned` → **待复习**（新增样式：琥珀底 #FFF7ED、字 #C2680B）；
  - `learned` → **已掌握**（沿用绿色 learned 样式）。
- 卡片弹窗 footer（L579-581）"开始费曼讲解"→"**开始费曼学习**"；底部主按钮文案已是"开始费曼学习"，保持。

### 改动 4：复习相关知识卡片（进入复习、复习完成两个时机显示）

文件：
- 新增 `frontend/src/components/KnowledgeCardDialog.vue`
- `frontend/src/views/SelectPage.vue`、`frontend/src/views/ChatView.vue`、`frontend/src/components/ReviewResultPanel.vue`
- `frontend/src/api/feynman.js`：`getKnowledgeCard(kpId, { force })` 增加 force 时拼时间戳绕过缓存。

做法：

1. 先把 SelectPage 内现有知识卡片弹窗整体抽成 **KnowledgeCardDialog**（props：`kpId`、`open`；内部自管 loading/error/轮询/收藏；右上角保留"× 关闭"按钮；footer 保留"开始费曼学习"），SelectPage 改为引用它，行为不变。
2. ChatView 中：
   - **进入复习后**：onMounted/bootstrap 检测到 isReviewMode 时，自动打开 KnowledgeCardDialog（force 拉取当前卡片），用户可点"关闭"开始对话；关闭不影响复习流程。
   - **复习完成时**：watch 到 `store.reviewResult`（status=completed）后，force 重新拉取卡片并再次自动弹出。
3. ReviewResultPanel 底部 next-actions 增加文字按钮"**查看知识卡片**"，emit `view-card`，供用户手动重开；ChatView 接收后打开同一弹窗。

### 改动 5：知识点学习 / 教材切片解析轻量差异化

- [KnowledgePage.vue](file:///d:/homework/Feynman/Feynman/Feynman/Feynman-Companion-AI-Agent/frontend/src/views/KnowledgePage.vue)：页头标题旁加眉标"**教材解析 · 原文切片**"，强调页码、切片、rubric 生成状态（沿用琥珀/灰色管理色系）。
- [SelectPage.vue](file:///d:/homework/Feynman/Feynman/Feynman/Feynman-Companion-AI-Agent/frontend/src/views/SelectPage.vue)：眉标统一为"**费曼学习 · 讲给小白听**"（蓝色系）。
- 仅文案与色系区分，不改页面结构。

## 四、实施顺序

1. API：`getKnowledgeCard` 增加 force 参数。
2. 抽取 KnowledgeCardDialog；SelectPage 切用（纯重构，先验证页面行为不变）。
3. SelectPage 两态徽标 + 文案（改动 3、5 的 SelectPage 部分）。
4. KnowledgePage 眉标差异化。
5. ProfilePage：gaps 两态改造 + SRS 自动展开。
6. AppSidebar 导航更名"学习历史"；ProfilePage：reports tab 更名与卡片网格重排（合并/匹配逻辑）。
7. ChatView + ReviewResultPanel：复习卡片两个时机自动显示与手动重开。

## 五、验证

- `cd frontend && npm run build` 通过；`node --test tests/` 既有两个单测不受影响。
- 手动冒烟（dev）：
  1. 侧栏导航显示"学习历史"，进入后页面标题一致；卡片网格正常渲染；"历史会话"打开会话详情且可继续；"学习报告"打开 ReportDrawer；无报告/无会话时按钮置灰；
  2. 复习计划：只剩两个状态 tab；reviewing 项不出现；进入页面今日待复习自动展开；
  3. 选择页：待复习/已掌握徽标正确；弹窗按钮文案为"开始费曼学习"；
  4. 复习流程：进入复习即弹卡片可关闭；完成后卡片再次自动弹出且内容为最新；结果面板"查看知识卡片"可重开；
  5. KnowledgePage 与 SelectPage 眉标/色系差异一眼可辨。

## 六、风险与应对

- **R1（会话与报告匹配）**：sessions 无 kp_id，用 kp_name+同日匹配可能错配 → 仅用于合并展示，错配时只是卡片少一个按钮；匹配结果不做数据写操作。
- **R2（自动弹卡片打扰）**：两个时机自动弹出，靠"关闭"按钮消除；不做"本次不再提示"记忆，保持实现简单。
- **R3（弹窗组件抽取回归）**：抽取步骤单独提交/验证，SelectPage 行为确认不变后再做后续改动。
- **R4（mock 兼容）**：mock 模式下 sessions 与 reports 各只有 1-2 条，合并逻辑需在 mock 数据上验证空态与置灰态。
