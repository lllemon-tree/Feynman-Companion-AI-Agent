<script setup>
// AI 思考中的三圆点气泡
</script>

<template>
  <div class="loading-row">
    <div class="loading-avatar">AI</div>
    <div class="loading-bubble">
      <span class="loading-text">AI 小白正在梳理你的讲解逻辑…</span>
      <span class="dot" />
      <span class="dot" />
      <span class="dot" />
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
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-accent-soft);
  color: var(--color-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}
.loading-bubble {
  background: var(--color-bg-ai);
  border: 1px solid var(--color-border);
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  border-top-left-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: var(--shadow-sm);
}
.loading-text {
  font-size: 14px;
  color: var(--color-text-soft);
}
.dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-muted);
  animation: bounce-dot 1.2s infinite ease-in-out;
}
.dot:nth-child(2) { animation-delay: 0.15s; }
.dot:nth-child(3) { animation-delay: 0.30s; }
.dot:nth-child(4) { animation-delay: 0.45s; }
</style>
