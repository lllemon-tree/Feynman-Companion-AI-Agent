<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import {
  createConversation,
  finishFreeExplanation,
  getConversation,
  getConversationModels,
  streamConversationMessage
} from '@/api/feynman'
import { enterAction } from '@/utils/imeKeydown'
import AppIcon from '@/components/AppIcon.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const mode = ref('expert')
const draft = ref('')
const notice = ref('')
const modelMenuOpen = ref(false)
const availableModels = ref([])
const selectedModel = ref('')
const activeConversation = ref(null)
const messages = ref([])
const messageListEl = ref(null)
const sending = ref(false)
const assessing = ref(false)
const loadingConversation = ref(false)
let loadSequence = 0

const isGuest = computed(() => !authStore.isLoggedIn && localStorage.getItem('feynman_guest') === 'true')
const isExpert = computed(() => mode.value === 'expert')
const modelLabel = computed(() => availableModels.value.find(item => item.id === selectedModel.value)?.name || '选择模型')
const modelName = (id) => availableModels.value.find(item => item.id === id)?.name || id
const hasBeginnerExplanation = computed(() => messages.value.some(item => item.role === 'user' && item.mode === 'beginner'))
const suggestions = computed(() => isExpert.value
  ? ['什么是迪杰斯特拉算法？', 'Git 的 commit 保存了什么？', '解释一下数据库事务的隔离级别']
  : ['我来讲讲迪杰斯特拉算法', '我想用自己的话解释 Git commit', '请听我解释数据库事务'])

async function scrollToBottom() {
  await nextTick()
  const el = messageListEl.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(() => route.query.conversation, async (id) => {
  const sequence = ++loadSequence
  if (!id) {
    activeConversation.value = null
    messages.value = []
    loadingConversation.value = false
    return
  }
  if (isGuest.value) {
    notice.value = '请先登录，才能保存并继续自由对话。'
    return
  }
  // 首次发送会先创建对话再写消息，不让空对话的异步读取覆盖刚写入的消息。
  if (sending.value && id === activeConversation.value?.id) return
  loadingConversation.value = true
  try {
    const conversation = await getConversation(id)
    if (sequence !== loadSequence) return
    activeConversation.value = conversation
    messages.value = conversation.messages || []
    if (messages.value.length) {
      mode.value = messages.value.at(-1).mode
      if (messages.value.at(-1).model) selectedModel.value = messages.value.at(-1).model
    }
    notice.value = ''
    scrollToBottom()
  } catch (error) {
    if (sequence === loadSequence) notice.value = error.message || '读取对话失败'
  } finally {
    if (sequence === loadSequence) loadingConversation.value = false
  }
}, { immediate: true })

onMounted(() => {
  loadModelCatalog()
  window.addEventListener('feynman:new-chat', handleNewChat)
  window.addEventListener('feynman:before-navigate', preventNavigationWhileBusy)
})

async function loadModelCatalog() {
  try {
    const catalog = await getConversationModels()
    availableModels.value = catalog.models || []
    const saved = selectedModel.value || localStorage.getItem('feynman_chat_model')
    selectedModel.value = availableModels.value.some(item => item.id === saved)
      ? saved
      : catalog.default_model
    if (!selectedModel.value || !availableModels.value.length) notice.value = '当前没有可用的对话模型。'
  } catch (error) {
    notice.value = error.message || '模型列表加载失败，请检查后端服务。'
  }
}

function selectModel(modelId) {
  selectedModel.value = modelId
  localStorage.setItem('feynman_chat_model', modelId)
  modelMenuOpen.value = false
  notice.value = ''
}
onUnmounted(() => {
  window.removeEventListener('feynman:new-chat', handleNewChat)
  window.removeEventListener('feynman:before-navigate', preventNavigationWhileBusy)
})

function preventNavigationWhileBusy(event) {
  if (sending.value || assessing.value) {
    event.preventDefault()
    notice.value = '请等当前回复或评估完成后再切换页面。'
  }
}

function setMode(nextMode) {
  mode.value = nextMode
  notice.value = ''
}

function handleNewChat(event) {
  if (sending.value || assessing.value) {
    event.preventDefault()
    notice.value = '请等当前回复或评估完成后再切换对话。'
    return
  }
  draft.value = ''
  notice.value = ''
  modelMenuOpen.value = false
  if (route.query.conversation) router.push('/home')
}

function selectSuggestion(text) {
  draft.value = text
  notice.value = ''
  document.getElementById('home-chat-input')?.focus()
}

async function sendMessage() {
  const content = draft.value.trim()
  const selectedMode = mode.value
  const chosenModel = selectedModel.value
  if (!content || sending.value || assessing.value || loadingConversation.value) return
  if (!chosenModel) {
    notice.value = '请先选择可用模型。'
    return
  }
  if (isGuest.value) {
    notice.value = '请先登录，才能使用并保存自由对话。教材知识点学习仍可从左侧进入。'
    return
  }
  sending.value = true
  notice.value = ''
  draft.value = ''
  let id = activeConversation.value?.id
  const initialMessageCount = messages.value.length
  const pendingUserId = `pending-user-${Date.now()}`
  const pendingAssistantId = `pending-assistant-${Date.now()}`
  try {
    messages.value.push(
      { id: pendingUserId, role: 'user', mode: selectedMode, model: chosenModel, content },
      { id: pendingAssistantId, role: 'assistant', mode: selectedMode, model: chosenModel, content: '' }
    )
    scrollToBottom()
    if (!id) {
      const created = await createConversation()
      id = created.id
      activeConversation.value = created
      router.replace({ path: '/home', query: { conversation: id } })
    }
    const result = await streamConversationMessage(id, content, selectedMode, chosenModel, (delta) => {
      const pending = messages.value.find(item => item.id === pendingAssistantId)
      if (pending) pending.content += delta
      scrollToBottom()
    })
    const pendingIndex = messages.value.findIndex(item => item.id === pendingUserId)
    if (pendingIndex >= 0) messages.value.splice(pendingIndex, 2, result.user_message, result.assistant_message)
    activeConversation.value.title = activeConversation.value.title === '新对话'
      ? content.slice(0, 36) + (content.length > 36 ? '…' : '')
      : activeConversation.value.title
    window.dispatchEvent(new Event('feynman:conversations-updated'))
    scrollToBottom()
  } catch (error) {
    messages.value = messages.value.filter(item => item.id !== pendingUserId && item.id !== pendingAssistantId)
    // 末尾的完成事件若在网络中丢失，先对照服务端历史，避免用户重试后产生重复消息。
    let recovered = false
    if (id) {
      try {
        const saved = await getConversation(id)
        if (saved.messages?.length >= initialMessageCount + 2 &&
            saved.messages.at(-2)?.role === 'user' &&
            saved.messages.at(-2)?.content === content &&
            saved.messages.at(-1)?.role === 'assistant') {
          messages.value = saved.messages
          activeConversation.value = saved
          draft.value = ''
          recovered = true
          window.dispatchEvent(new Event('feynman:conversations-updated'))
        }
      } catch (_) { /* 原错误更有诊断价值。 */ }
    }
    if (!recovered) {
      if (!draft.value) draft.value = content
      notice.value = error.message || '发送失败，请重试。输入内容已恢复。'
    }
  } finally {
    sending.value = false
  }
}

async function finishExplanation() {
  if (!activeConversation.value?.id || !hasBeginnerExplanation.value || assessing.value || sending.value) return
  const chosenModel = selectedModel.value
  if (!chosenModel) {
    notice.value = '请先选择可用模型。'
    return
  }
  assessing.value = true
  notice.value = ''
  try {
    const result = await finishFreeExplanation(activeConversation.value.id, chosenModel)
    messages.value.push(result)
    window.dispatchEvent(new Event('feynman:conversations-updated'))
    scrollToBottom()
  } catch (error) {
    notice.value = error.message || '评估失败，请稍后重试'
  } finally {
    assessing.value = false
  }
}

let homeCompositionEndedAt = -Infinity
const homeIsComposing = ref(false)

function handleInputKeydown(event) {
  const action = enterAction(event, homeIsComposing.value, homeCompositionEndedAt)
  if (action === 'skip') {
    event.preventDefault()
    return
  }
  if (action === 'send') {
    event.preventDefault()
    sendMessage()
  }
}
</script>

<template>
  <div class="home-main">
      <header class="home-header">
        <div class="header-left">
          <h1 :title="activeConversation?.title || '新对话'">{{ activeConversation?.title || '新对话' }}</h1>
          <span class="header-divider"></span>
          <div class="mode-switch" role="group" aria-label="选择学习模式">
            <button
              type="button"
              :class="{ 'mode-active': isExpert }"
              :aria-pressed="isExpert"
              @click="setMode('expert')"
            >
              <AppIcon name="sparkles" :size="15" />专家模式
            </button>
            <button
              type="button"
              :class="{ 'mode-active': !isExpert }"
              :aria-pressed="!isExpert"
              @click="setMode('beginner')"
            >
              <AppIcon name="graduate" :size="15" />小白模式
            </button>
          </div>
        </div>
        <span class="header-caption">{{ isExpert ? '自由提问' : '讲给小白听' }}</span>
      </header>

      <main ref="messageListEl" class="home-conversation" :class="{ 'home-conversation--active': messages.length }">
        <p v-if="loadingConversation" class="reply-pending">正在读取对话…</p>
        <section v-else-if="!messages.length" class="welcome" aria-live="polite">
          <div class="welcome-mark"><AppIcon :name="isExpert ? 'sparkles' : 'graduate'" :size="27" /></div>
          <h2>{{ isExpert ? '今天想弄懂什么？' : '把你的理解讲给我听' }}</h2>
          <p>
            {{ isExpert
              ? '不限教材，提出问题后由专家模式帮你梳理概念与思路。'
              : '不必先选教材知识点。你来讲，我来追问并帮助检查理解。' }}
          </p>
          <div class="suggestions">
            <button v-for="text in suggestions" :key="text" type="button" @click="selectSuggestion(text)">
              <span>{{ text }}</span><AppIcon name="chevron" :size="15" />
            </button>
          </div>
          <p v-if="sending" class="welcome-pending">正在思考…</p>
        </section>
        <div v-else class="conversation-stream" aria-live="polite">
          <article
            v-for="message in messages"
            :key="message.id"
            class="conversation-message"
            :class="{ 'conversation-message--user': message.role === 'user' }"
          >
            <div v-if="message.role === 'assistant'" class="message-mark"><AppIcon name="book" :size="15" /></div>
            <div class="message-content">
              <div v-if="message.role === 'assistant'" class="message-meta">
                {{ message.mode === 'expert' ? '专家模式' : '小白模式' }}<span v-if="message.model"> · {{ modelName(message.model) }}</span>
              </div>
              <p v-if="!message.assessment" class="message-text">{{ message.content }}</p>
              <div v-else class="assessment-card">
                <div class="assessment-heading">讲解反馈 <span>无指定教材 · 不给数值分数</span></div>
                <p class="assessment-topic">主题：{{ message.assessment.topic }}</p>
                <div v-if="message.assessment.strengths.length" class="assessment-section">
                  <strong>讲清楚的部分</strong>
                  <p v-for="(item, index) in message.assessment.strengths" :key="`strength-${index}`">{{ item }}</p>
                </div>
                <div v-if="message.assessment.gaps.length" class="assessment-section">
                  <strong>还需要补充</strong>
                  <p v-for="(item, index) in message.assessment.gaps" :key="`gap-${index}`">{{ item }}</p>
                </div>
                <div class="assessment-section">
                  <strong>依据你的原话</strong>
                  <blockquote v-for="(item, index) in message.assessment.evidence" :key="`evidence-${index}`">
                    “{{ item.quote }}”<span>{{ item.observation }}</span>
                  </blockquote>
                </div>
                <p class="assessment-next">下一步：{{ message.assessment.next_step }}</p>
              </div>
            </div>
          </article>
          <p v-if="assessing || (sending && !messages.at(-1)?.content)" class="reply-pending">{{ assessing ? '正在核对讲解依据…' : '正在思考…' }}</p>
        </div>
      </main>

      <div class="composer-wrap">
        <p v-if="notice" class="connection-notice" role="status">
          {{ notice }}
          <button type="button" aria-label="关闭提示" @click="notice = ''"><AppIcon name="close" :size="15" /></button>
        </p>
        <form class="composer" @submit.prevent="sendMessage">
          <textarea
            id="home-chat-input"
            v-model="draft"
            :placeholder="isExpert ? '输入你的问题…' : '用自己的话讲一讲你的理解…'"
            rows="2"
            maxlength="2000"
            aria-label="对话输入"
            :disabled="sending || assessing || loadingConversation"
            @keydown="handleInputKeydown"
            @compositionstart="homeIsComposing = true"
            @compositionend="homeIsComposing = false; homeCompositionEndedAt = performance.now()"
          ></textarea>
          <div class="composer-footer">
            <div class="model-picker-wrap">
              <button
                class="model-picker"
                type="button"
                :aria-expanded="modelMenuOpen"
                :disabled="sending || assessing || !availableModels.length"
                @click="modelMenuOpen = !modelMenuOpen"
              >
                <AppIcon name="sparkles" :size="16" />
                <span>{{ modelLabel }}</span>
                <AppIcon name="down" :size="14" />
              </button>
              <div v-if="modelMenuOpen" class="model-popover" role="group" aria-label="选择对话模型">
                <button v-for="item in availableModels" :key="item.id" type="button"
                  class="model-option" :class="{ 'model-option--active': selectedModel === item.id }"
                  :aria-pressed="selectedModel === item.id" @click="selectModel(item.id)">
                  {{ item.name }}
                </button>
              </div>
            </div>
            <div class="composer-right">
              <button
                v-if="!isExpert && hasBeginnerExplanation"
                class="assessment-button"
                type="button"
                :disabled="sending || assessing"
                @click="finishExplanation"
              >{{ assessing ? '评估中…' : '完成讲解并评估' }}</button>
              <span class="composer-hint">Enter 发送 · Shift + Enter 换行</span>
              <button class="send-button" type="submit" :disabled="!draft.trim() || sending || assessing || loadingConversation" aria-label="发送消息">
                <AppIcon name="send" :size="18" />
              </button>
            </div>
          </div>
        </form>
        <p class="composer-disclaimer">AI 回答可能有误；无教材讲解评估不引用教材，也不与教材评分混用。</p>
      </div>
  </div>
</template>

<style scoped>
.home-main { min-width: 0; min-height: 0; flex: 1; height: 100%; display: flex; flex-direction: column; background: #fff; color: #17233b; }
.home-header { height: 68px; flex: 0 0 68px; display: flex; align-items: center; justify-content: space-between; padding: 0 34px; border-bottom: 1px solid #edf0f5; }
.header-left { display: flex; align-items: center; min-width: 0; gap: 17px; }
.home-header h1 { max-width: min(31vw, 350px); overflow: hidden; text-overflow: ellipsis; font-size: 16px; font-weight: 650; white-space: nowrap; }
.header-divider { height: 22px; width: 1px; background: #e1e8f2; }
.mode-switch { display: flex; align-items: center; padding: 3px; border: 1px solid #e5ebf4; border-radius: 10px; background: #f7f9fc; }
.mode-switch button { min-height: 32px; display: flex; align-items: center; gap: 7px; padding: 0 11px; border-radius: 7px; color: #718099; font-size: 12px; font-weight: 600; white-space: nowrap; }
.mode-switch button.mode-active { color: #245bd4; background: #fff; box-shadow: 0 1px 4px rgba(30, 64, 130, .1); }
.header-caption { color: #94a0b3; font-size: 12px; }
.home-conversation { flex: 1; min-height: 0; overflow-y: auto; display: grid; place-items: center; padding: 36px 24px 20px; }
.home-conversation--active { display: block; }
.conversation-stream { width: min(100%, 850px); margin: 0 auto; padding: 16px 0 26px; }
.conversation-message { display: flex; align-items: flex-start; gap: 13px; margin: 0 0 25px; }
.conversation-message--user { justify-content: flex-end; }
.conversation-message--user .message-content { max-width: min(82%, 620px); padding: 11px 15px; border-radius: 13px; background: #edf3ff; }
.message-mark { width: 28px; height: 28px; flex: 0 0 28px; display: grid; place-items: center; border-radius: 8px; background: #eaf1ff; color: #245bd4; }
.message-content { max-width: min(100%, 760px); }
.message-meta { margin: 1px 0 7px; color: #7c8ba2; font-size: 11px; font-weight: 600; }
.message-text { color: #243149; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 14px; line-height: 1.75; }
.assessment-card { border: 1px solid #e2eaf7; border-radius: 12px; padding: 17px 18px; background: #fbfcff; }
.assessment-heading { display: flex; align-items: baseline; gap: 12px; font-size: 15px; font-weight: 700; }
.assessment-heading span { color: #8390a4; font-size: 11px; font-weight: 400; }
.assessment-topic { margin: 7px 0 14px; color: #67768c; font-size: 12px; }
.assessment-section { margin: 12px 0; }
.assessment-section strong { display: block; margin-bottom: 5px; color: #3d526e; font-size: 12px; }
.assessment-section p { color: #485970; font-size: 13px; line-height: 1.6; }
.assessment-section blockquote { display: grid; gap: 3px; margin: 6px 0; padding: 8px 11px; border-left: 2px solid #95b6f2; background: #f2f6fe; color: #274879; font-size: 13px; }
.assessment-section blockquote span { color: #596d88; font-size: 12px; }
.assessment-next { margin-top: 14px; color: #315aa1; font-size: 13px; }
.reply-pending { margin-left: 41px; color: #8090aa; font-size: 12px; }
.welcome { width: min(100%, 730px); margin-top: -22px; text-align: center; }
.welcome-mark { width: 52px; height: 52px; display: grid; place-items: center; margin: 0 auto 20px; border-radius: 15px; color: #245fe1; background: linear-gradient(145deg, #f1f6ff, #e8efff); }
.welcome h2 { font-size: clamp(22px, 2.2vw, 30px); font-weight: 650; letter-spacing: -.03em; }
.welcome p { margin: 10px 0 28px; color: #748198; font-size: 14px; }
.suggestions { display: flex; flex-wrap: wrap; justify-content: center; gap: 9px; }
.suggestions button { display: flex; align-items: center; gap: 8px; max-width: 100%; min-height: 38px; padding: 8px 12px; border: 1px solid #e7edf6; border-radius: 9px; background: #fff; color: #5c6b83; font-size: 12px; text-align: left; }
.suggestions button:hover { border-color: #b8cbef; color: #245bd4; background: #f8fbff; }
.suggestions button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.welcome-pending { margin-top: 20px; color: #61789d; font-size: 12px; }
.composer-wrap { width: min(100% - 56px, 850px); margin: 0 auto 19px; }
.composer { border: 1px solid #dce5f2; border-radius: 15px; background: #fff; box-shadow: 0 10px 32px rgba(30, 60, 110, .06); padding: 12px 13px 10px; }
.composer:focus-within { border-color: #a9c2f0; }
.composer textarea { display: block; width: 100%; min-height: 58px; max-height: 170px; resize: vertical; padding: 4px 6px; border: 0; background: transparent; color: #17233b; font-size: 14px; line-height: 1.55; }
.composer textarea::placeholder { color: #9aa8ba; }
.composer-footer, .composer-right { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.composer-footer { padding-top: 6px; }
.model-picker-wrap { position: relative; }
.model-picker { min-height: 31px; display: flex; align-items: center; gap: 7px; padding: 0 9px; border-radius: 8px; color: #4e648b; font-size: 12px; font-weight: 600; }
.model-picker:hover { background: #f1f5fc; }
.model-picker:disabled { opacity: .5; cursor: not-allowed; }
.model-popover { position: absolute; bottom: 39px; left: 0; width: 225px; display: grid; gap: 3px; padding: 6px; border: 1px solid #e1e8f3; border-radius: 10px; background: #fff; box-shadow: 0 10px 26px rgba(30, 60, 110, .12); z-index: 2; }
.model-option { width: 100%; padding: 9px 10px; border-radius: 7px; color: #607087; font-size: 12px; text-align: left; }
.model-option:hover, .model-option--active { color: #245bd4; background: #eef4ff; }
.assessment-button { min-height: 31px; padding: 0 10px; border: 1px solid #b9cdf3; border-radius: 8px; color: #245bd4; font-size: 12px; font-weight: 600; white-space: nowrap; }
.assessment-button:hover:not(:disabled) { background: #f3f7ff; }
.assessment-button:disabled { opacity: .55; cursor: not-allowed; }
.composer-hint { color: #a0aabc; font-size: 11px; }
.send-button { width: 33px; height: 33px; display: grid; place-items: center; border-radius: 9px; background: #2563eb; color: #fff; }
.send-button:not(:disabled):hover { background: #1d4ed8; }
.send-button:disabled { opacity: .45; cursor: not-allowed; }
.composer-disclaimer { margin-top: 9px; color: #9aa5b5; text-align: center; font-size: 11px; }
.connection-notice { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; margin-bottom: 9px; padding: 10px 12px; border: 1px solid #cbdcf8; border-radius: 10px; background: #f4f8ff; color: #31548d; font-size: 12px; line-height: 1.5; }
.connection-notice button { flex: 0 0 auto; display: grid; place-items: center; }
@media (max-width: 760px) {
  .home-header { height: 61px; flex-basis: 61px; padding: 0 16px; }
  .home-header h1 { max-width: 96px; }
  .header-left { gap: 9px; }
  .header-divider, .header-caption { display: none; }
  .mode-switch button { gap: 4px; padding: 0 7px; font-size: 11px; }
  .mode-switch svg { display: none; }
  .home-conversation { padding: 22px 16px 16px; }
  .welcome { margin-top: 0; }
  .welcome p { font-size: 12px; }
  .suggestions { display: grid; justify-content: stretch; }
  .composer-wrap { width: calc(100% - 24px); margin-bottom: 12px; }
  .composer-hint { display: none; }
  .assessment-button { max-width: 120px; font-size: 11px; }
}
</style>
