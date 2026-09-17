<script setup>
import MarkdownContent from '@/components/MarkdownContent.vue'

defineProps({
  role: {
    type: String,
    required: true
  },
  content: {
    type: String,
    default: ''
  }
})
</script>

<template>
  <div v-if="role === 'system'" class="bubble-system">
    <span class="bubble-system__inner">{{ content }}</span>
  </div>

  <div
    v-else
    class="bubble-row"
    :class="[`bubble-row--${role}`]"
  >
    <div class="bubble-avatar" v-if="role === 'ai'">
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

    <div class="bubble" :class="[`bubble--${role}`]">
      <div v-if="role === 'ai'" class="bubble__content">
        <MarkdownContent :content="content" />
      </div>
      <div v-else class="bubble__content">{{ content }}</div>
    </div>

    <div class="bubble-avatar bubble-avatar--user" v-if="role === 'user'">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="8" r="4" fill="#fff" fillOpacity="0.9" />
        <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" stroke="#fff" strokeWidth="2" strokeLinecap="round" fill="none" />
      </svg>
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  max-width: 80%;
  margin-bottom: 20px;
}

.bubble-row--user {
  margin-left: auto;
}

.bubble-avatar {
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

.bubble-avatar--user {
  background: #6366F1;
}

.bubble {
  padding: 12px 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  font-size: 15px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}

.bubble--ai {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 16px 16px 16px 4px;
  color: #1E293B;
}

.bubble--user {
  background: #2563EB;
  border-radius: 16px 16px 4px 16px;
  color: #FFFFFF;
}

.bubble-system {
  text-align: center;
  margin: 16px 0;
}

.bubble-system__inner {
  display: inline-block;
  padding: 6px 12px;
  font-size: 12px;
  color: #64748B;
  background: #F1F5F9;
  border-radius: 9999px;
}

.bubble__content {
  font-size: 15px;
  line-height: 1.6;
}
</style>
