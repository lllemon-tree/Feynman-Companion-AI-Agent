<script setup>
import { computed } from 'vue'

/**
 * 复习结果反馈组件（第八周 P0）
 * 展示本次复习相较上次的维度变化：
 * - 哪些维度已改善并掌握（mastered）
 * - 哪些维度仍需继续复习（continue）
 * - 分数变化（previous_score -> current_score，delta）
 * - 下一步复习时间
 *
 * 数据来源：GET /api/v1/reviews/{review_id} 的 dimension_changes
 * 不直接展示用于评分的完整 Rubric 或标准答案
 */
const props = defineProps({
  reviewResult: { type: Object, default: null }
})

const emit = defineEmits(['back-to-profile', 'continue-learning'])

const kpName = computed(() => props.reviewResult?.kp_name || '当前知识点')

const status = computed(() => props.reviewResult?.status || '')

const isCompleted = computed(() => status.value === 'completed')

const dimensionChanges = computed(() => props.reviewResult?.dimension_changes || [])

const masteredList = computed(() =>
  dimensionChanges.value.filter(d => d.result === 'mastered')
)

const continueList = computed(() =>
  dimensionChanges.value.filter(d => d.result === 'continue')
)

const unchangedList = computed(() =>
  dimensionChanges.value.filter(d => d.result === 'unchanged')
)

// 汇总信息：本次复习整体表现
const summaryText = computed(() => {
  if (!isCompleted.value) return '复习进行中，完成对话后将生成对比结果。'
  const mastered = masteredList.value.length
  const cont = continueList.value.length
  if (mastered > 0 && cont === 0) {
    return `太棒了！本次复习中 ${mastered} 个薄弱维度已全部达到掌握标准（≥7分），漏洞已关闭。`
  }
  if (mastered > 0 && cont > 0) {
    return `本次复习有进步：${mastered} 个维度已掌握，${cont} 个维度仍需继续复习。`
  }
  if (mastered === 0 && cont > 0) {
    return `本次复习尚未达到掌握标准，${cont} 个维度仍需继续巩固，继续加油！`
  }
  return '本次复习结果已生成。'
})

function formatNextReview(dateStr) {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })
  } catch (e) {
    return dateStr
  }
}

function deltaClass(delta) {
  if (delta === null || delta === undefined) return 'delta-zero'
  if (delta > 0) return 'delta-up'
  if (delta < 0) return 'delta-down'
  return 'delta-zero'
}

function deltaText(delta) {
  if (delta === null || delta === undefined) return '—'
  if (delta > 0) return `+${delta}`
  return `${delta}`
}

function resultLabel(result) {
  if (result === 'mastered') return '已掌握'
  if (result === 'continue') return '仍需复习'
  return '无变化'
}

function resultClass(result) {
  if (result === 'mastered') return 'result-mastered'
  if (result === 'continue') return 'result-continue'
  return 'result-unchanged'
}

function scoreClass(score) {
  if (score === null || score === undefined) return 'score-null'
  if (score >= 7) return 'score-high'
  return 'score-low'
}

// 分数变化条的宽度计算（0-10分制）
function barWidth(score) {
  if (score === null || score === undefined) return '0%'
  return `${Math.min(100, Math.max(0, (score / 10) * 100))}%`
}
</script>

<template>
  <section v-if="reviewResult" class="review-result-panel">
    <header class="panel-header">
      <div class="panel-title-row">
        <span class="panel-icon">🎯</span>
        <h3 class="panel-title">复习效果反馈</h3>
        <span v-if="isCompleted" class="status-tag status-completed">已完成</span>
        <span v-else class="status-tag status-active">进行中</span>
      </div>
      <p class="panel-subtitle">{{ kpName }}</p>
    </header>

    <div class="panel-body">
      <!-- 总体说明 -->
      <div class="summary-box" :class="{ 'summary-completed': isCompleted }">
        <p class="summary-text">{{ summaryText }}</p>
      </div>

      <!-- 仍为 active，无对比数据 -->
      <div v-if="!isCompleted" class="active-hint">
        <p>当前复习尚未完成，完成对话并生成诊断报告后，这里会展示：</p>
        <ul>
          <li>每个薄弱维度的分数变化（上次 vs 本次）</li>
          <li>哪些维度已经改善并掌握</li>
          <li>哪些维度仍需继续复习及下次复习时间</li>
        </ul>
      </div>

      <!-- 已完成：展示维度变化 -->
      <div v-else class="changes-section">
        <!-- 已掌握维度 -->
        <div v-if="masteredList.length > 0" class="change-group group-mastered">
          <div class="group-header">
            <span class="group-dot dot-mastered"></span>
            <span class="group-title">已改善并掌握</span>
            <span class="group-count">{{ masteredList.length }}</span>
          </div>
          <div class="change-cards">
            <div v-for="item in masteredList" :key="item.gap_id" class="change-card">
              <div class="change-card-head">
                <span class="dim-name">{{ item.dimension }}</span>
                <span :class="['result-badge', resultClass(item.result)]">
                  {{ resultLabel(item.result) }}
                </span>
              </div>
              <div class="score-compare">
                <div class="score-col">
                  <span class="score-label">上次</span>
                  <span :class="['score-value', scoreClass(item.previous_score)]">
                    {{ item.previous_score === null || item.previous_score === undefined ? '—' : item.previous_score }}
                  </span>
                  <div class="score-bar">
                    <div class="bar-fill bar-prev" :style="{ width: barWidth(item.previous_score) }"></div>
                  </div>
                </div>
                <div class="arrow-col">
                  <span class="arrow-text">→</span>
                </div>
                <div class="score-col">
                  <span class="score-label">本次</span>
                  <span :class="['score-value', scoreClass(item.current_score)]">
                    {{ item.current_score === null || item.current_score === undefined ? '—' : item.current_score }}
                  </span>
                  <div class="score-bar">
                    <div class="bar-fill bar-curr" :style="{ width: barWidth(item.current_score) }"></div>
                  </div>
                </div>
                <div class="delta-col">
                  <span :class="['delta-value', deltaClass(item.delta)]">{{ deltaText(item.delta) }}</span>
                </div>
              </div>
              <div class="change-card-foot">
                <span class="foot-tag">已复习 {{ item.review_count }} 次</span>
                <span class="foot-tag foot-done">无需再次复习</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 仍需复习维度 -->
        <div v-if="continueList.length > 0" class="change-group group-continue">
          <div class="group-header">
            <span class="group-dot dot-continue"></span>
            <span class="group-title">仍需继续复习</span>
            <span class="group-count">{{ continueList.length }}</span>
          </div>
          <div class="change-cards">
            <div v-for="item in continueList" :key="item.gap_id" class="change-card">
              <div class="change-card-head">
                <span class="dim-name">{{ item.dimension }}</span>
                <span :class="['result-badge', resultClass(item.result)]">
                  {{ resultLabel(item.result) }}
                </span>
              </div>
              <div class="score-compare">
                <div class="score-col">
                  <span class="score-label">上次</span>
                  <span :class="['score-value', scoreClass(item.previous_score)]">
                    {{ item.previous_score === null || item.previous_score === undefined ? '—' : item.previous_score }}
                  </span>
                  <div class="score-bar">
                    <div class="bar-fill bar-prev" :style="{ width: barWidth(item.previous_score) }"></div>
                  </div>
                </div>
                <div class="arrow-col">
                  <span class="arrow-text">→</span>
                </div>
                <div class="score-col">
                  <span class="score-label">本次</span>
                  <span :class="['score-value', scoreClass(item.current_score)]">
                    {{ item.current_score === null || item.current_score === undefined ? '—' : item.current_score }}
                  </span>
                  <div class="score-bar">
                    <div class="bar-fill bar-curr" :style="{ width: barWidth(item.current_score) }"></div>
                  </div>
                </div>
                <div class="delta-col">
                  <span :class="['delta-value', deltaClass(item.delta)]">{{ deltaText(item.delta) }}</span>
                </div>
              </div>
              <div class="change-card-foot">
                <span class="foot-tag">已复习 {{ item.review_count }} 次</span>
                <span v-if="item.next_review_at" class="foot-tag foot-next">
                  下次复习：{{ formatNextReview(item.next_review_at) }}
                </span>
                <span v-else class="foot-tag foot-next">下次复习时间待定</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 无变化维度（仅展示分数，不作为漏洞） -->
        <div v-if="unchangedList.length > 0" class="change-group group-unchanged">
          <div class="group-header">
            <span class="group-dot dot-unchanged"></span>
            <span class="group-title">其他维度</span>
            <span class="group-count">{{ unchangedList.length }}</span>
          </div>
          <div class="unchanged-grid">
            <div v-for="item in unchangedList" :key="item.gap_id || item.dimension" class="unchanged-item">
              <span class="dim-name">{{ item.dimension }}</span>
              <span class="unchanged-scores">
                {{ item.previous_score === null || item.previous_score === undefined ? '—' : item.previous_score }}
                →
                {{ item.current_score === null || item.current_score === undefined ? '—' : item.current_score }}
              </span>
            </div>
          </div>
        </div>

        <!-- 下一步入口 -->
        <div class="next-actions">
          <button class="action-btn action-primary" @click="emit('back-to-profile')">
            返回个人中心
          </button>
          <button class="action-btn action-secondary" @click="emit('continue-learning')">
            继续学习其他知识点
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.review-result-panel {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 14px;
  overflow: hidden;
  font-family: 'Noto Sans SC', 'Inter', sans-serif;
}

.panel-header {
  padding: 16px 20px;
  background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
  border-bottom: 1px solid #C7D2FE;
}

.panel-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-icon {
  font-size: 18px;
}

.panel-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #1E293B;
}

.status-tag {
  margin-left: auto;
  padding: 3px 10px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.status-completed {
  background: rgba(16, 185, 129, 0.15);
  color: #059669;
}

.status-active {
  background: rgba(245, 158, 11, 0.15);
  color: #D97706;
}

.panel-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #475569;
}

.panel-body {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* 总体说明 */
.summary-box {
  padding: 12px 14px;
  border-radius: 10px;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
}

.summary-box.summary-completed {
  background: rgba(16, 185, 129, 0.06);
  border-color: rgba(16, 185, 129, 0.2);
}

.summary-text {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.6;
  color: #1E293B;
}

/* active 提示 */
.active-hint {
  padding: 14px;
  background: #FFFBEB;
  border: 1px solid #FDE68A;
  border-radius: 10px;
  color: #92400E;
  font-size: 13px;
  line-height: 1.6;
}

.active-hint p {
  margin: 0 0 8px;
}

.active-hint ul {
  margin: 0;
  padding-left: 18px;
}

.active-hint li {
  margin-bottom: 4px;
}

/* 变化分组 */
.change-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-mastered {
  background: #10B981;
}

.dot-continue {
  background: #F59E0B;
}

.dot-unchanged {
  background: #94A3B8;
}

.group-title {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
}

.group-count {
  padding: 1px 8px;
  background: #F1F5F9;
  color: #475569;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
}

/* 变化卡片 */
.change-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.change-card {
  padding: 12px 14px;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
}

.change-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.dim-name {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
}

.result-badge {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}

.result-mastered {
  background: rgba(16, 185, 129, 0.15);
  color: #059669;
}

.result-continue {
  background: rgba(245, 158, 11, 0.15);
  color: #D97706;
}

.result-unchanged {
  background: #F1F5F9;
  color: #64748B;
}

/* 分数对比 */
.score-compare {
  display: flex;
  align-items: center;
  gap: 8px;
}

.score-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.score-label {
  font-size: 11px;
  color: #94A3B8;
}

.score-value {
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
}

.score-high {
  color: #10B981;
}

.score-low {
  color: #EF4444;
}

.score-null {
  color: #94A3B8;
}

.score-bar {
  height: 5px;
  background: #E2E8F0;
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 400ms ease;
}

.bar-prev {
  background: #CBD5E1;
}

.bar-curr {
  background: #2563EB;
}

.arrow-col {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding-top: 14px;
}

.arrow-text {
  font-size: 16px;
  color: #94A3B8;
  font-weight: 600;
}

.delta-col {
  flex-shrink: 0;
  min-width: 36px;
  text-align: center;
  padding-top: 14px;
}

.delta-value {
  font-size: 15px;
  font-weight: 700;
}

.delta-up {
  color: #10B981;
}

.delta-down {
  color: #EF4444;
}

.delta-zero {
  color: #94A3B8;
}

.change-card-foot {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #E2E8F0;
}

.foot-tag {
  padding: 2px 8px;
  background: #F1F5F9;
  color: #64748B;
  border-radius: 6px;
  font-size: 11px;
}

.foot-done {
  background: rgba(16, 185, 129, 0.1);
  color: #059669;
}

.foot-next {
  background: rgba(245, 158, 11, 0.1);
  color: #D97706;
}

/* 无变化维度 */
.unchanged-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.unchanged-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
}

.unchanged-scores {
  font-size: 12px;
  color: #64748B;
  font-weight: 500;
}

/* 下一步入口 */
.next-actions {
  display: flex;
  gap: 10px;
  padding-top: 6px;
}

.action-btn {
  flex: 1;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms;
  border: none;
}

.action-primary {
  background: #2563EB;
  color: #FFFFFF;
}

.action-primary:hover {
  background: #1D4ED8;
}

.action-secondary {
  background: #F1F5F9;
  color: #475569;
}

.action-secondary:hover {
  background: #E2E8F0;
}
</style>
