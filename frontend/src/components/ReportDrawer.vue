<script setup>
import { onBeforeUnmount, watch } from 'vue'
import RadarChart from './RadarChart.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  report: { type: Object, default: null }
})
const emit = defineEmits(['close', 'restart'])

function handleEsc(e) {
  if (e.key === 'Escape' && props.open) emit('close')
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      document.body.style.overflow = 'hidden'
      window.addEventListener('keydown', handleEsc)
    } else {
      document.body.style.overflow = ''
      window.removeEventListener('keydown', handleEsc)
    }
  }
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', handleEsc)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="open" class="drawer-mask" @click.self="$emit('close')">
        <div class="diagnosis-modal" role="dialog" aria-modal="true">
          <header class="modal-header">
            <span class="header-title">费曼诊断报告</span>
            <button class="close-btn" @click="$emit('close')" aria-label="关闭">
              <svg class="close-icon" viewBox="0 0 16 16" fill="none">
                <path d="M4 4L12 12" stroke="#6B7280" stroke-width="1.5" stroke-linecap="round"/>
                <path d="M12 4L4 12" stroke="#6B7280" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </header>

          <div v-if="report" class="modal-body">
            <div class="body-row-1">
              <div class="radar-box">
                <RadarChart :dimensions="report.dimensions" />
              </div>
              <div class="summary-wrap">
                <span class="sub-title-sm">综合评价</span>
                <p class="summary-text">{{ report.overall_comment }}</p>
              </div>
            </div>

            <div class="divider-line"></div>

            <div class="dimensions-wrap">
              <span class="sub-title-sm">分维度分析</span>
              <div class="dimensions-list">
                <div class="dimension-item" v-for="(dim, i) in report.dimensions" :key="i">
                  <div class="dimension-header">
                    <span class="dimension-name">{{ dim.name }}</span>
                    <span class="dimension-score">{{ dim.score }}分</span>
                  </div>
                  <div class="dimension-analysis">{{ dim.analysis }}</div>
                  <div class="dimension-suggestion">{{ dim.suggestion }}</div>
                </div>
              </div>
            </div>

            <div v-if="report.review_plan" class="divider-line"></div>

            <div v-if="report.review_plan" class="review-plan-wrap">
              <span class="sub-title-sm">📋 复习建议</span>
              <div class="review-plan-content">
                <!-- 教材重读指引 -->
                <div class="review-item" v-if="report.review_plan.reread_guide && report.review_plan.reread_guide.length > 0">
                  <span class="review-label">教材重读指引</span>
                  <div class="reread-list">
                    <div v-for="item in report.review_plan.reread_guide" :key="item.priority" class="reread-card">
                      <div class="reread-header">
                        <span class="reread-priority">优先级 {{ item.priority }}</span>
                        <span class="reread-material">{{ item.material_name }}</span>
                      </div>
                      <div class="reread-page">{{ item.page_hint }}</div>
                      <div class="reread-focus">重点关注：{{ item.focus }}</div>
                      <div class="reread-reason">{{ item.reason }}</div>
                    </div>
                  </div>
                </div>
                <!-- 同类知识点推荐 -->
                <div class="review-item" v-if="report.review_plan.related_kps && report.review_plan.related_kps.length > 0">
                  <span class="review-label">同类知识点推荐</span>
                  <div class="related-kps">
                    <span v-for="kp in report.review_plan.related_kps" :key="kp.kp_id" class="kp-tag">
                      <span class="kp-name">{{ kp.kp_name }}</span>
                      <span class="kp-relation">{{ kp.relation }}</span>
                    </span>
                  </div>
                </div>
                <!-- 学习优先级排序 -->
                <div class="review-item" v-if="report.review_plan.priority_order && report.review_plan.priority_order.length > 0">
                  <span class="review-label">学习优先级排序</span>
                  <div class="priority-list">
                    <div v-for="item in report.review_plan.priority_order" :key="item.rank" class="priority-item">
                      <span class="priority-num">{{ item.rank }}</span>
                      <div class="priority-info">
                        <span class="priority-dim">{{ item.dimension }}</span>
                        <span class="priority-kp">{{ item.kp_name }}</span>
                        <span class="priority-suggestion">{{ item.suggestion }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="modal-body">
            <div style="padding: 40px; text-align: center; color: #6B7280;">报告数据缺失</div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fade-in 0.2s ease;
}

.diagnosis-modal {
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 0;
  width: 630px;
  max-width: 630px;
  max-height: 85vh;
  background: #FFFFFF;
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0px 25px 50px -12px rgba(0, 0, 0, 0.25);
  border-radius: 15px;
  flex-shrink: 0;
}

.modal-header {
  box-sizing: border-box;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  padding: 15px 22.5px;
  width: 100%;
  height: 60.94px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}
.header-title {
  font-family: 'Noto Sans SC', sans-serif;
  font-weight: 600;
  font-size: 15px;
  line-height: 22px;
  letter-spacing: 0.375px;
  color: #1A1D23;
}
.close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 9.375px;
  flex-shrink: 0;
  cursor: pointer;
  border: none;
  background: transparent;
}
.close-btn:hover {
  background: rgba(0, 0, 0, 0.04);
}
.close-icon {
  width: 16px;
  height: 16px;
}

.modal-body {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 18.75px 22.5px;
  gap: 22.5px;
  width: 100%;
  flex: 1;
  overflow-y: auto;
}

.body-row-1 {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 18.75px;
  width: 100%;
  flex-shrink: 0;
}
.radar-box {
  width: 200px;
  max-width: 200px;
  height: 200px;
  max-height: 200px;
  flex-shrink: 0;
}
.summary-wrap {
  display: flex;
  flex-direction: column;
  width: calc(100% - 218.75px);
}
.sub-title-sm {
  font-family: 'Noto Sans SC', sans-serif;
  font-weight: 600;
  font-size: 11.25px;
  line-height: 17px;
  letter-spacing: 0.5625px;
  text-transform: uppercase;
  color: #6B7280;
}
.summary-text {
  margin-top: 7.5px;
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 13.5px;
  line-height: 22px;
  color: #1A1D23;
  margin-bottom: 0;
}

.divider-line {
  width: 100%;
  height: 1px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}

.dimensions-wrap {
  width: 100%;
  display: flex;
  flex-direction: column;
}
.dimensions-list {
  margin-top: 11.25px;
  display: flex;
  flex-direction: column;
  gap: 13.5px;
}
.dimension-item {
  box-sizing: border-box;
  padding: 13.5px 15px;
  background: #F9FAFB;
  border-radius: 13.375px;
}
.dimension-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 7.5px;
}
.dimension-name {
  font-family: 'Noto Sans SC', sans-serif;
  font-weight: 600;
  font-size: 13.5px;
  color: #1A1D23;
}
.dimension-score {
  font-family: 'Noto Sans SC', sans-serif;
  font-weight: 600;
  font-size: 13.5px;
  color: #2563EB;
}
.dimension-analysis {
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 13.125px;
  line-height: 20px;
  color: #4B5563;
  margin-bottom: 5.625px;
}
.dimension-suggestion {
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 12.1875px;
  line-height: 18px;
  color: #6B7280;
  padding-left: 11.25px;
  border-left: 2px solid #DBEAFE;
}

.review-plan-wrap {
  width: 100%;
  display: flex;
  flex-direction: column;
}
.review-plan-content {
  margin-top: 11.25px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.review-item {
  box-sizing: border-box;
  padding: 13.5px 15px;
  background: #F9FAFB;
  border-radius: 13.375px;
}
.review-label {
  display: block;
  font-family: 'Noto Sans SC', sans-serif;
  font-weight: 600;
  font-size: 13.5px;
  color: #1A1D23;
  margin-bottom: 7.5px;
}
.review-text {
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 13.125px;
  line-height: 20px;
  color: #4B5563;
  margin: 0;
}
.reread-list {
  display: flex;
  flex-direction: column;
  gap: 7.5px;
}
.reread-card {
  padding: 7.5px 11.25px;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 9px;
}
.reread-header {
  display: flex;
  align-items: center;
  gap: 7.5px;
  margin-bottom: 4px;
}
.reread-priority {
  font-size: 11px;
  font-weight: 600;
  color: #2563EB;
  background: rgba(37, 99, 235, 0.1);
  padding: 2px 7px;
  border-radius: 6px;
}
.reread-material {
  font-size: 12px;
  font-weight: 600;
  color: #1A1D23;
}
.reread-page {
  font-size: 12px;
  color: #6B7280;
  margin-bottom: 3px;
}
.reread-focus {
  font-size: 12px;
  color: #4B5563;
  margin-bottom: 3px;
}
.reread-reason {
  font-size: 11px;
  color: #6B7280;
  padding-left: 7.5px;
  border-left: 2px solid #DBEAFE;
}
.related-kps {
  display: flex;
  flex-wrap: wrap;
  gap: 7.5px;
}
.kp-tag {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 11.25px;
  background: rgba(37, 99, 235, 0.08);
  border-radius: 9px;
}
.kp-name {
  font-family: 'Noto Sans SC', sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: #2563EB;
}
.kp-relation {
  font-size: 11px;
  color: #6B7280;
}
.priority-list {
  display: flex;
  flex-direction: column;
  gap: 7.5px;
}
.priority-item {
  display: flex;
  align-items: flex-start;
  gap: 7.5px;
  padding: 7.5px 11.25px;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 9px;
}
.priority-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  background: #2563EB;
  color: #FFFFFF;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
}
.priority-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.priority-dim {
  font-size: 12px;
  font-weight: 600;
  color: #1A1D23;
}
.priority-kp {
  font-size: 11px;
  color: #6B7280;
}
.priority-suggestion {
  font-size: 11px;
  color: #4B5563;
}

.drawer-enter-from,
.drawer-leave-to { opacity: 0; }
.drawer-enter-from .diagnosis-modal,
.drawer-leave-to .diagnosis-modal { transform: translateY(20px); }
</style>