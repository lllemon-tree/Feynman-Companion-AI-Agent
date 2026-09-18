<script setup>
import { onMounted, ref, nextTick, watch, onBeforeUnmount, computed, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chatStore'
import MessageBubble from '@/components/MessageBubble.vue'
import LoadingBubble from '@/components/LoadingBubble.vue'
import ReportCard from '@/components/ReportCard.vue'
import ChatInput from '@/components/ChatInput.vue'
import KnowledgeCardDialog from '@/components/KnowledgeCardDialog.vue'
import { addReportToReviewList, getKnowledgeCard } from '@/api/feynman'

const router = useRouter()
const ReportDrawer = defineAsyncComponent(() => import('@/components/DetailedReportDrawer.vue'))
const ReviewResultPanel = defineAsyncComponent(() => import('@/components/ReviewResultPanel.vue'))
const route = useRoute()
const store = useChatStore()
const drawerOpen = ref(false)
const messageListEl = ref(null)
const pinnedToBottom = ref(true)
const reviewAdding = ref(false)
const knowledgeCardOpen = ref(false)
const knowledgeCardLoading = ref(false)
const knowledgeCardError = ref('')
const knowledgeCard = ref(null)
const contextLabel = computed(() => [store.subject, store.materialTitle, store.chapterTitle].filter(Boolean).join(' / '))
const hasVisiblePendingReply = computed(() => {
  const lastMessage = store.messages.at(-1)
  return lastMessage?.role === 'ai' && Boolean(lastMessage.content)
})
const canFinishEarly = computed(() =>
  !store.isLocked &&
  !store.isReportReady &&
  store.messages.some(item => item.role === 'user' && item.content.trim())
)

function goBack() {
  router.push('/select')
}

async function openKnowledgeCard() {
  if (!store.kpId) return
  knowledgeCardOpen.value = true
  knowledgeCardLoading.value = !knowledgeCard.value
  knowledgeCardError.value = ''
  try {
    knowledgeCard.value = await getKnowledgeCard(store.kpId)
  } catch (error) {
    knowledgeCardError.value = error.message || '知识卡片加载失败'
  } finally {
    knowledgeCardLoading.value = false
  }
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

function handleScroll() {
  const el = messageListEl.value
  if (el) pinnedToBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 100
}

/** 监听消息变化：每次新增都滚到底 */
watch(
  () => store.messages.length,
  () => scrollToBottom()
)
watch(
  () => store.messages.at(-1)?.content,
  () => { if (store.isLocked && pinnedToBottom.value) scrollToBottom(false) }
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
  const resumeId = route.query.sessionId || (store.isReviewMode ? store.reviewSessionId : '')
  if (resumeId) {
    try {
      await store.restoreSession(resumeId)
    } catch (error) {
      store.resetLocalState()
      store.isLocked = true
      store.setError(error.message || '历史会话恢复失败')
      store.pushMessage('system', '未能恢复历史会话，请返回学习记录后重试。')
    }
  } else {
    await store.bootstrap()
  }
  scrollToBottom(false)
})

watch(
  () => route.query.sessionId,
  async (sessionId) => {
    if (!sessionId || sessionId === store.sessionId) return
    store.clearReviewContext()
    drawerOpen.value = false
    knowledgeCardOpen.value = false
    knowledgeCard.value = null
    try {
      await store.restoreSession(sessionId)
    } catch (error) {
      store.resetLocalState()
      store.isLocked = true
      store.setError(error.message || '历史会话恢复失败')
      store.pushMessage('system', '未能恢复历史会话，请返回知识点选择后重试。')
    }
    scrollToBottom(false)
  }
)

// 离开页面时清空复习上下文，避免影响下次普通学习
onBeforeUnmount(() => {
  store.clearReviewContext()
})

async function handleSend(text, acknowledge) {
  const response = await store.sendUserMessage(text)
  acknowledge?.(Boolean(response))
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

async function finishAndEvaluate() {
  await store.finishAndEvaluate()
}

async function addCurrentReportToReviewList() {
  if (reviewAdding.value || store.reportData?.reviewListAdded) return
  if (!store.reportData?.reportId) {
    store.setError('报告编号尚未保存，请稍后刷新历史报告后再试。')
    return
  }
  reviewAdding.value = true
  try {
    await addReportToReviewList(store.reportData.reportId)
    store.reportData.reviewListAdded = true
    store.reportData.reviewListSource = null
  } catch (error) {
    store.setError(error.message || '加入复习列表失败')
  } finally {
    reviewAdding.value = false
  }
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
    <header class="chat-header">
      <button class="back-btn" type="button" aria-label="返回知识点选择" @click="goBack">←</button>
      <div class="header-copy">
        <div class="header-title-row">
          <h1 class="chat-title">{{ store.kpName || '知识点讲解' }}</h1>
          <span class="header-mode">{{ store.isReviewMode ? '专项复习' : '教材陪练' }}</span>
        </div>
        <p>{{ contextLabel || '选定知识点 · 费曼讲解' }}</p>
      </div>
      <div class="header-actions">
        <button v-if="store.isReviewMode" class="knowledge-card-button" type="button" @click="openKnowledgeCard">知识卡片</button>
        <button class="header-switch" type="button" @click="goBack">切换知识点</button>
      </div>
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
    <main ref="messageListEl" class="chat-main" @scroll="handleScroll">
      <div class="chat-main__inner">
        <div class="study-intro">
          <span class="study-intro__eyebrow">知识点学习 · {{ store.isReviewMode ? '巩固' : '讲给小白听' }}</span>
          <h2>{{ store.kpName || '开始你的讲解' }}</h2>
          <p>先用自己的话讲一个你确定的点。我会结合教材追问，最后给出有依据的诊断和复习建议。</p>
        </div>
        <p v-if="store.errorMsg" class="chat-error" role="alert">{{ store.errorMsg }}</p>
        <MessageBubble
          v-for="m in store.messages.filter(item => item.role !== 'ai' || item.content)"
          :key="m.id"
          :role="m.role"
          :content="m.content"
        />

        <LoadingBubble
          v-if="store.isLocked && !store.isReportReady && !store.errorMsg && !hasVisiblePendingReply"
          :status="store.streamStatus || '正在处理…'"
        />
        <p v-if="store.isLocked && store.messages.at(-1)?.role === 'ai' && store.messages.at(-1)?.content" class="stream-status">
          {{ store.streamStatus || '正在完成本轮讲解…' }}
        </p>

        <!-- 报告卡片：熔断后插入到对话流尾部 -->
        <ReportCard
          v-if="store.isReportReady && store.reportData?.cardPreview"
          :card-preview="store.reportData.cardPreview"
          :final-report="store.reportData.finalReport"
          :fallback-used="store.reportData.fallbackUsed"
          :provider="store.reportData.provider"
          :review-list-added="store.reportData.reviewListAdded"
          :review-adding="reviewAdding"
          :show-review-action="Boolean(store.reportData.reportId)"
          @click="openDrawer"
          @add-review="addCurrentReportToReviewList"
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
    <div class="composer-wrap">
      <div v-if="!store.isReportReady" class="finish-row">
        <span>觉得已经讲清楚了？可以主动结束，不必等系统继续追问。</span>
        <button type="button" :disabled="!canFinishEarly" @click="finishAndEvaluate">
          完成讲解并评估
        </button>
      </div>
      <ChatInput
        :locked="store.isLocked"
        :finished="store.isReportReady"
        @send="handleSend"
        @restart="handleRestart"
      />
      <p class="composer-note">Enter 发送 · Shift + Enter 换行 · 拼音选字不会发送</p>
    </div>

    <!-- 报告抽屉 -->
    <ReportDrawer
      v-if="drawerOpen"
      :open="drawerOpen"
      :report="store.reportData?.finalReport"
      :review-plan="store.reportData?.reviewPlan"
      :card-preview="store.reportData?.cardPreview"
      :fallback-used="store.reportData?.fallbackUsed"
      :provider="store.reportData?.provider"
      :review-list-added="store.reportData?.reviewListAdded"
      :review-adding="reviewAdding"
      :show-review-action="Boolean(store.reportData?.reportId)"
      @close="drawerOpen = false"
      @restart="handleRestart"
      @add-review="addCurrentReportToReviewList"
    />
    <KnowledgeCardDialog
      :open="knowledgeCardOpen"
      :card="knowledgeCard"
      :fallback-name="store.kpName"
      :loading="knowledgeCardLoading"
      :error="knowledgeCardError"
      :show-favorite="false"
      primary-label="继续复习"
      footer-text="对照知识卡片，重新组织自己的讲解。"
      @close="knowledgeCardOpen = false"
      @retry="openKnowledgeCard"
      @primary="knowledgeCardOpen = false"
    />
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  width: 100%;
  min-height: 0;
  flex: 1;
  background: #fff;
  position: relative;
}
.chat-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 28px;
  width: 100%;
  min-height: 76px;
  background: #fff;
  border-bottom: 1px solid #e9edf5;
  flex-shrink: 0;
}
.back-btn {
  display: grid;
  place-items: center;
  flex: none;
  width: 34px;
  height: 34px;
  border: 1px solid #e5ebf4;
  border-radius: 10px;
  background: #fff;
  color: #50627f;
  font-size: 20px;
}
.back-btn:hover { background: #f5f8fd; color: #265ce0; }
.header-copy { min-width: 0; flex: 1; }
.header-title-row { display: flex; align-items: center; gap: 10px; min-width: 0; }
.chat-title {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 700;
  font-size: 17px;
  line-height: 1.35;
  color: #17233b;
}
.header-copy p { margin: 4px 0 0; color: #8290a6; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.header-mode { flex: none; padding: 4px 8px; border-radius: 7px; background: #eef4ff; color: #2861d5; font-size: 11px; font-weight: 650; }
.header-actions { display: flex; align-items: center; gap: 10px; flex: none; }
.knowledge-card-button { padding: 7px 11px; border: 1px solid #cfddf4; border-radius: 9px; background: #f6f9ff; color: #315fc4; font-size: 12px; font-weight: 650; }
.knowledge-card-button:hover { border-color: #9eb8ea; background: #eaf1ff; }
.header-switch { flex: none; background: transparent; color: #60728f; font-size: 12px; border: 0; }
.header-switch:hover { color: #265ce0; }

.review-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 28px;
  background: #f5f7ff;
  border-bottom: 1px solid #e2e8ff;
  flex-shrink: 0;
}
.review-banner-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.review-banner-icon { font-size: 17px; flex-shrink: 0; }
.review-banner-text { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; min-width: 0; }
.review-banner-label {
  padding: 3px 7px;
  background: #5665d9;
  color: #fff;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 650;
}
.review-banner-desc { font-size: 12px; color: #555da1; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.review-focus-tag { padding: 3px 7px; background: #e6e9ff; color: #555bc6; border-radius: 5px; font-size: 11px; font-weight: 600; }
.review-banner-hint { font-size: 11px; color: #7882ad; flex-shrink: 0; white-space: nowrap; }

.chat-main {
  flex: 1;
  min-height: 0;
  padding: 34px 30px 25px;
  overflow-y: auto;
}
.chat-main__inner {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 840px;
  margin: 0 auto;
}
.study-intro { padding: 2px 0 24px; border-bottom: 1px solid #edf1f7; margin-bottom: 10px; }
.study-intro__eyebrow { color: #3268df; font-size: 11px; font-weight: 700; letter-spacing: .07em; }
.study-intro h2 { margin: 10px 0 8px; font-size: clamp(22px, 2.5vw, 29px); line-height: 1.35; color: #17233b; letter-spacing: -.02em; }
.study-intro p { margin: 0; font-size: 13px; color: #7b89a0; line-height: 1.65; }
.chat-error { margin: 0; padding: 10px 13px; border-radius: 10px; background: #fff6f3; color: #a84a36; font-size: 12px; }
.stream-status { margin: -8px 0 0 43px; color: #91a0b6; font-size: 11px; }
.composer-wrap { flex: none; padding: 0 30px 16px; background: linear-gradient(180deg, rgba(255,255,255,0), #fff 15%); }
.finish-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; max-width: 840px; margin: 0 auto 10px; padding: 9px 12px; border: 1px solid #e5ebf5; border-radius: 10px; background: #f8faff; }
.finish-row span { color: #7b899f; font-size: 11px; line-height: 1.5; }
.finish-row button { flex: none; padding: 7px 11px; border-radius: 8px; background: #edf3ff; color: #2d61cb; font-size: 11px; font-weight: 650; }
.finish-row button:disabled { color: #a0adbf; background: #f1f4f8; cursor: not-allowed; }
.composer-wrap :deep(.chat-input) { max-width: 840px; margin: 0 auto; padding: 0; border: 0; background: transparent; }
.composer-wrap :deep(.input-box) { padding: 10px 13px; border: 1px solid #dbe4f4; border-radius: 15px; box-shadow: 0 8px 28px rgba(39,79,150,.06); }
.composer-wrap :deep(textarea) { padding: 8px 3px; min-height: 48px; font-size: 14px; }
.composer-wrap :deep(.send-btn) { padding: 8px 17px; border-radius: 9px; }
.composer-note { max-width: 840px; margin: 7px auto 0; text-align: right; color: #a0adbe; font-size: 11px; }
.chat-main :deep(.bubble-row) { max-width: 100%; width: 100%; margin: 0; align-items: flex-start; gap: 12px; }
.chat-main :deep(.bubble-row--user) { justify-content: flex-end; }
.chat-main :deep(.bubble-avatar) { width: 31px; height: 31px; background: #edf3ff; box-shadow: none; }
.chat-main :deep(.bubble-avatar--user) { display: none; }
.chat-main :deep(.bubble) { max-width: min(78%, 680px); padding: 13px 17px; font-size: 14px; line-height: 1.7; box-shadow: none; }
.chat-main :deep(.bubble--ai) { background: #f7f9fd; border: 0; border-radius: 5px 15px 15px 15px; color: #22324e; }
.chat-main :deep(.bubble--user) { background: #eaf1ff; border-radius: 15px 15px 5px 15px; color: #18345e; }
.chat-main :deep(.bubble__content) { font-size: 14px; line-height: 1.7; }
.chat-main :deep(.bubble-system) { margin: 0; }
@media (max-width: 640px) {
  .chat-header { min-height: 68px; padding: 10px 16px; }
  .header-switch, .review-banner-hint { display: none; }
  .review-banner { padding: 8px 16px; }
  .chat-main { padding: 24px 16px 18px; }
  .composer-wrap { padding: 0 12px 10px; }
  .chat-main :deep(.bubble) { max-width: 88%; }
  .composer-note { font-size: 10px; }
}
</style>
