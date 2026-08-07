<script setup>
import { computed } from 'vue'

const props = defineProps({
  cardPreview: {
    type: Object,
    required: true
  },
  finalReport: {
    type: Object,
    default: null
  }
})
defineEmits(['click'])

const displayScore = computed(() => {
  const dimensions = props.finalReport?.dimensions
  if (Array.isArray(dimensions) && dimensions.length > 0) {
    const total = dimensions.reduce((sum, dimension) => {
      const score = Number(dimension?.score)
      return sum + (Number.isFinite(score) ? score : 0)
    }, 0)
    return (total / dimensions.length).toFixed(1)
  }

  const total = Number(props.cardPreview?.total_score)
  return (Number.isFinite(total) ? total / 4 : 0).toFixed(1)
})
</script>

<template>
  <div class="report-wrap" @click="$emit('click')">
    <div class="report-avatar">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="5" y="8" width="14" height="10" rx="2" fill="#2563EB" />
        <rect x="9" y="11" width="2.5" height="2.5" rx="0.5" fill="#fff" />
        <rect x="12.5" y="11" width="2.5" height="2.5" rx="0.5" fill="#fff" />
        <rect x="9.5" y="15" width="5" height="1" rx="0.5" fill="#93C5FD" />
        <rect x="10.5" y="5" width="3" height="3" rx="1" fill="#2563EB" />
        <rect x="11.5" y="4" width="1" height="2" rx="0.5" fill="#2563EB" />
        <circle cx="11.5" cy="4" r="1" fill="#60A5FA" />
        <rect x="3" y="10" width="2" height="4" rx="1" fill="#93C5FD" />
        <rect x="19" y="10" width="2" height="4" rx="1" fill="#93C5FD" />
      </svg>
    </div>

    <div class="report-card">
      <div class="card-header">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="text-white">
          <polyline points="20 6 9 17 4 12" />
        </svg>
        <span class="card-header-title">本次费曼训练已完成</span>
      </div>

      <div class="card-body">
        <div class="score-row">
          <span class="score-num">{{ displayScore }}</span>
          <span class="score-total">/ 10</span>
          <div class="score-desc">综合评分</div>
        </div>

        <div class="divider"></div>

        <div class="error-item">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" class="text-amber-500">
            <path d="M12 9v4M12 17h.01" />
            <circle cx="12" cy="12" r="10" />
          </svg>
          <div>
            <div class="error-label">核心盲区</div>
            <div class="error-name">{{ cardPreview.summary }}</div>
          </div>
        </div>

        <button class="card-btn">
          <span>查看完整四维诊断</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.report-wrap {
  display: flex;
  gap: 10px;
  width: 100%;
  align-items: flex-start;
}

.report-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #DBEAFE;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.report-card {
  width: 100%;
  max-width: 340px;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.05);
  border-radius: 16px;
  overflow: hidden;
}

.card-header {
  padding: 20px 20px 16px;
  background: linear-gradient(90deg, #2563EB 0%, #4F46E5 100%);
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-header-title {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #FFFFFF;
}

.card-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.score-row {
  position: relative;
}

.score-num {
  font-size: 32px;
  font-weight: 700;
  color: #1E293B;
  line-height: 1;
}

.score-total {
  font-size: 16px;
  font-weight: 500;
  color: #64748B;
  margin-left: 4px;
}

.score-desc {
  font-size: 12.5px;
  color: #64748B;
  margin-top: 4px;
}

.divider {
  width: 100%;
  height: 1px;
  background: #E2E8F0;
}

.error-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.error-item svg {
  margin-top: 2px;
  flex-shrink: 0;
}

.error-label {
  font-size: 12px;
  color: #64748B;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-weight: 600;
  margin-bottom: 4px;
}

.error-name {
  font-size: 14px;
  font-weight: 600;
  color: #1E293B;
}

.card-btn {
  width: 100%;
  padding: 10px 0;
  background: #2563EB;
  border-radius: 12px;
  border: none;
  color: #FFFFFF;
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: all 150ms;
}

.card-btn:hover {
  background: #1D4ED8;
}

.card-btn:active {
  transform: scale(0.98);
}
</style>
