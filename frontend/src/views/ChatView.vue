<script setup>
import { onMounted, ref, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chatStore'
import MessageBubble from '@/components/MessageBubble.vue'
import LoadingBubble from '@/components/LoadingBubble.vue'
import ReportCard from '@/components/ReportCard.vue'
import ReportDrawer from '@/components/ReportDrawer.vue'
import ChatInput from '@/components/ChatInput.vue'

const store = useChatStore()
const router = useRouter()
const drawerOpen = ref(false)
const messageListEl = ref(null)

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

onMounted(async () => {
  await store.bootstrap()
  scrollToBottom(false)
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
  await store.resetSession()
  await store.bootstrap()
  scrollToBottom(false)
}

function openDrawer() {
  if (!store.reportData?.finalReport) return
  drawerOpen.value = true
}
</script>

<template>
  <div class="chat-view">
    <!-- 顶部 Header -->
    <header class="chat-header">
      <h1 class="chat-title">费曼伴学智能体 — 数据结构专练</h1>
    </header>

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
          @click="openDrawer"
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
  justify-content: center;
  padding: 0 15px;
  width: 100%;
  height: 52.5px;
  background: #FFFFFF;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}
.chat-title {
  margin: 0;
  font-weight: 600;
  font-size: 14.0625px;
  line-height: 21px;
  letter-spacing: 0.351562px;
  color: #1A1D23;
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
</style>
