<script setup>
import { onMounted, ref, nextTick, watch, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chatStore'
import MessageBubble from '@/components/MessageBubble.vue'
import LoadingBubble from '@/components/LoadingBubble.vue'
import ReportCard from '@/components/ReportCard.vue'
import ReportDrawer from '@/components/ReportDrawer.vue'
import ReviewResultPanel from '@/components/ReviewResultPanel.vue'
import ChatInput from '@/components/ChatInput.vue'
import UserBar from '@/components/UserBar.vue'

const router = useRouter()
const store = useChatStore()
const drawerOpen = ref(false)
const messageListEl = ref(null)

function goBack() {
  router.push('/select')
}

/** 滚到底部 */
async function scrollToBottom(smooth = true) {
  await nextTick()
  const el = messageListEl.value
  if (!el) return
  el.scrollTo({
    top: el.scrollHeight,
    behavior: smooth ? 'smooth' : 'auto'
  })
}

/** 监听消息变化：每次新增都滚到底 */
watch(
  () => store.messages.length,
  () => scrollToBottom()
)
/** loading 出现时也滚一下（气泡高度会变） */
watch(
  () => store.isLocked,
  (locked) => locked && scrollToBottom()
)
/** 报告生成时滚到底，展示报告卡片 */
watch(
  () => store.isReportReady,
  (ready) => ready && scrollToBottom()
)
/** 复习结果反馈组件渲染后自动滚到底，确保完整可见 */
watch(
  () => store.reviewResult,
  (result) => result && scrollToBottom()
)

onMounted(async () => {
  await store.bootstrap()
  scrollToBottom(false)
})

// 离开页面时清空复习上下文，避免影响下次普通学习
onBeforeUnmount(() => {
  store.clearReviewContext()
})

async function handleSend(text) {
  const response = await store.sendUserMessage(text)
  if (
    response?.next_action === 'guide_topic' &&
    response?.reply_text?.includes('重新选择知识点')
  ) {
    setTimeout(() => router.push('/select'), 800)
  }
}

async function handleRestart() {
  drawerOpen.value = false
  // 退出复习模式，回到普通学习
  store.clearReviewContext()
  await store.resetSession()
  await store.bootstrap()
  scrollToBottom(false)
}

function openDrawer() {
  if (!store.reportData?.finalReport) return
  drawerOpen.value = true
}

/** 返回个人中心（复习完成后） */
function backToProfile() {
  router.push('/profile?from=review')
}

/** 继续学习其他知识点 */
function continueLearning() {
  store.clearReviewContext()
  router.push('/select')
}
</script>

<template>
  <div class="chat-view">
    <!-- 顶部 Header -->
    <header class="chat-header">
      <button class="back-btn" @click="goBack">
        ← 选择知识点
      </button>
      <h1 class="chat-title">
        {{ store.isReviewMode ? '费曼伴学智能体 — 复习模式' : '费曼伴学智能体 — 数据结构专练' }}
      </h1>
      <UserBar />
    </header>

    <!-- 复习场景提示横幅（第八周 P0） -->
    <!-- 让用户知道当前是复习模式，提示重点维度，不暴露标准答案 -->
    <div v-if="store.isReviewMode && store.reviewFocusDimensions.length > 0" class="review-banner">
      <div class="review-banner-left">
        <span class="review-banner-icon">🎯</span>
        <div class="review-banner-text">
          <span class="review-banner-label">复习模式</span>
          <span class="review-banner-desc">
            本次重点：
            <span
              v-for="dim in store.reviewFocusDimensions"
              :key="dim"
              class="review-focus-tag"
            >{{ dim }}</span>
          </span>
        </div>
      </div>
      <span class="review-banner-hint">针对上次薄弱点重新讲解，不直接给出标准答案</span>
    </div>

    <!-- 消息区 -->
    <main ref="messageListEl" class="chat-main">
      <div class="chat-main__inner">
        <MessageBubble
          v-for="m in store.messages"
          :key="m.id"
          :role="m.role"
          :content="m.content"
        />

        <LoadingBubble v-if="store.isLocked && !store.isReportReady" />

        <!-- 报告卡片：熔断后插入到对话流尾部 -->
        <ReportCard
          v-if="store.isReportReady && store.reportData?.cardPreview"
          :card-preview="store.reportData.cardPreview"
          :final-report="store.reportData.finalReport"
          @click="openDrawer"
        />

        <!-- 复习结果反馈（第八周 P0） -->
        <!-- 报告生成后，若处于复习模式且拉取到 reviewResult，展示维度变化对比 -->
        <ReviewResultPanel
          v-if="store.isReviewMode && store.reviewResult"
          :review-result="store.reviewResult"
          @back-to-profile="backToProfile"
          @continue-learning="continueLearning"
        />
      </div>
    </main>

    <!-- 底部输入区 -->
    <ChatInput
      :locked="store.isLocked"
      :finished="store.isReportReady"
      @send="handleSend"
      @restart="handleRestart"
    />

    <!-- 报告抽屉 -->
    <ReportDrawer
      :open="drawerOpen"
      :report="store.reportData?.finalReport"
      @close="drawerOpen = false"
      @restart="handleRestart"
    />
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: #F5F7FA;
  position: relative;
}

/* Header */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 15px;
  width: 100%;
  height: 52.5px;
  background: #FFFFFF;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}
.back-btn {
  font-size: 13px;
  color: #64748B;
  transition: color 150ms;
  background: transparent;
  border: none;
}

.back-btn:hover {
  color: #1E293B;
}
.chat-title {
  margin: 0;
  font-weight: 600;
  font-size: 14.0625px;
  line-height: 21px;
  letter-spacing: 0.351562px;
  color: #1A1D23;
}

/* 复习场景提示横幅 */
.review-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
  border-bottom: 1px solid #C7D2FE;
  flex-shrink: 0;
}

.review-banner-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.review-banner-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.review-banner-text {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}

.review-banner-label {
  padding: 2px 8px;
  background: #4F46E5;
  color: #FFFFFF;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.review-banner-desc {
  font-size: 13px;
  color: #3730A3;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.review-focus-tag {
  padding: 2px 8px;
  background: rgba(79, 70, 229, 0.12);
  color: #4F46E5;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.review-banner-hint {
  font-size: 12px;
  color: #6366F1;
  flex-shrink: 0;
  white-space: nowrap;
}

/* 消息主区 */
.chat-main {
  flex: 1;
  padding: 22.5px 15px;
  overflow-y: auto;
}
.chat-main__inner {
  display: flex;
  flex-direction: column;
  gap: 18.75px;
}

/* 响应式：小屏下隐藏复习提示的次要文案 */
@media (max-width: 640px) {
  .review-banner-hint {
    display: none;
  }
  .review-banner-desc {
    font-size: 12px;
  }
}
</style>
