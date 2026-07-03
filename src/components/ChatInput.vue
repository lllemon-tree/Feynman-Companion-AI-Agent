<script setup>
import { ref, nextTick, watch, computed } from 'vue'

const props = defineProps({
  locked: { type: Boolean, default: false },
  finished: { type: Boolean, default: false }
})
const emit = defineEmits(['send', 'restart'])

const MAX_LENGTH = 500
const text = ref('')
const textareaEl = ref(null)

const charCount = computed(() => text.value.length)
const isOverLimit = computed(() => charCount.value > MAX_LENGTH)

function autoGrow() {
  const el = textareaEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

function handleSubmit() {
  const value = text.value.trim()
  if (!value || props.locked || props.finished || isOverLimit.value) return
  emit('send', value)
  text.value = ''
  nextTick(autoGrow)
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSubmit()
  } else if (e.key === 'Enter' && e.shiftKey) {
    e.preventDefault()
    const el = textareaEl.value
    if (el) {
      const start = el.selectionStart
      const end = el.selectionEnd
      text.value = text.value.substring(0, start) + '\n' + text.value.substring(end)
      nextTick(() => {
        autoGrow()
        el.selectionStart = el.selectionEnd = start + 1
      })
    }
  }
}

function handleInput() {
  if (text.value.length > MAX_LENGTH) {
    text.value = text.value.substring(0, MAX_LENGTH)
  }
  autoGrow()
}

watch(text, () => nextTick(autoGrow))
</script>

<template>
  <div class="chat-input">
    <div v-if="finished" class="input-finished">
      <span class="finished-text">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" fill="#10B981"/>
          <path d="M6 8l1.5 1.5L10 6" stroke="#fff" stroke-width="1.666" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>本次费曼学习训练已完成</span>
      </span>
      <button class="restart-btn" @click="$emit('restart')">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M7 3V5C4.79 5 3 6.79 3 9c0 1.66 1.34 3 3 3" stroke="#6B7280" stroke-width="1.28" stroke-linecap="round"/>
          <path d="M7 11V9c2.21 0 4-1.79 4-4c0-1.66-1.34-3-3-3" stroke="#6B7280" stroke-width="1.28" stroke-linecap="round"/>
          <path d="M11 1L13 3L11 5" stroke="#6B7280" stroke-width="1.28" stroke-linecap="round"/>
          <path d="M3 13L1 11L3 9" stroke="#6B7280" stroke-width="1.28" stroke-linecap="round"/>
        </svg>
        <span>重新开始</span>
      </button>
    </div>

    <div v-else class="input-box">
      <textarea
        ref="textareaEl"
        v-model="text"
        rows="1"
        :placeholder="locked ? 'AI 小白正在努力思考你的逻辑…' : '请开始你的费曼讲解...'"
        :disabled="locked"
        @keydown="handleKeydown"
        @input="handleInput"
      />
      <div class="input-footer">
        <span class="char-count" :class="{ 'char-count--over': isOverLimit }">
          {{ charCount }}/{{ MAX_LENGTH }}
        </span>
        <button
          class="send-btn"
          :disabled="locked || !text.trim() || isOverLimit"
          @click="handleSubmit"
        >
          发送
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-input {
  padding: 15px;
  background: #fff;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

/* 已完成态 */
.input-finished {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 11.25px 15px;
  border-radius: 13.375px;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.2);
}
.finished-text {
  display: flex;
  align-items: center;
  gap: 7.5px;
  font-size: 14.0625px;
  color: #10B981;
  font-weight: 500;
}
.restart-btn {
  display: flex;
  align-items: center;
  gap: 6.25px;
  background: transparent;
  color: #6B7280;
  padding: 6.25px 15px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 9.375px;
  font-size: 13.125px;
  font-weight: 500;
  transition: background 0.15s;
}
.restart-btn:hover { 
  background: rgba(0, 0, 0, 0.04);
}

/* 输入态 */
.input-box {
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 13.375px;
  padding: 7.5px 11.25px;
  box-shadow: 0px 1px 3px rgba(0, 0, 0, 0.06);
  transition: border-color 0.15s;
}
.input-box:focus-within {
  border-color: #2563EB;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

textarea {
  flex: 1;
  resize: none;
  min-height: 22.5px;
  max-height: 160px;
  padding: 6.25px 0;
  font-size: 14.0625px;
  line-height: 23px;
  background: transparent;
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.char-count {
  font-size: 12.1875px;
  color: #6B7280;
  transition: color 0.2s;
}
.char-count--over {
  color: #EF4444;
}

.send-btn {
  flex: 0 0 auto;
  background: #2563EB;
  color: #fff;
  padding: 6.25px 15px;
  border-radius: 9.375px;
  font-size: 13.125px;
  font-weight: 600;
  transition: opacity 0.15s;
  border: none;
}
.send-btn:not(:disabled):hover { opacity: 0.9; }
.send-btn:not(:disabled):active { opacity: 0.8; }
.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
