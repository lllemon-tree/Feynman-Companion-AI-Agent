<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

defineProps({ status: { type: String, default: '正在处理…' } })
const startedAt = Date.now()
const elapsedSeconds = ref(0)
let timer
onMounted(() => {
  timer = window.setInterval(() => {
    elapsedSeconds.value = Math.floor((Date.now() - startedAt) / 1000)
  }, 1000)
})
onUnmounted(() => window.clearInterval(timer))
</script>

<template>
  <div class="loading-row">
    <div class="loading-avatar">
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
    <div class="loading-bubble" role="status" aria-live="polite">
      <span class="loading-text">{{ status }}</span>
      <span class="dot" />
      <span class="dot" />
      <span class="dot" />
      <span v-if="elapsedSeconds >= 3" class="elapsed">{{ elapsedSeconds }} 秒</span>
    </div>
  </div>
</template>

<style scoped>
.loading-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin: 14px 0;
  animation: fade-in 0.2s ease;
}

.loading-avatar {
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

.loading-bubble {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  padding: 12px 16px;
  border-radius: 16px;
  border-top-left-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.loading-text {
  font-size: 14px;
  color: #64748B;
}

.elapsed {
  color: #94A3B8;
  font-size: 12px;
  white-space: nowrap;
  margin-left: 4px;
}

.dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #64748B;
  animation: bounce-dot 1.2s infinite ease-in-out;
}

.dot:nth-child(2) { animation-delay: 0.15s; }
.dot:nth-child(3) { animation-delay: 0.30s; }
.dot:nth-child(4) { animation-delay: 0.45s; }
</style>
