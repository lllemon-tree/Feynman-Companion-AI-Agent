<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { listConversations } from '@/api/feynman'
import AppIcon from './AppIcon.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const open = ref(false)
const conversations = ref([])
const isGuest = computed(() => !authStore.isLoggedIn && localStorage.getItem('feynman_guest') === 'true')
const displayName = computed(() => isGuest.value ? '访客' : (authStore.username || '同学'))
const navigation = [
  { label: '学习对话', icon: 'chat', to: '/home', paths: ['/home'] },
  { label: '我的教材', icon: 'book', to: '/upload', paths: ['/upload', '/knowledge'] },
  { label: '知识点学习', icon: 'layers', to: '/select', paths: ['/select', '/study'] },
  { label: '复习计划', icon: 'calendar', to: '/profile?tab=gaps', tab: 'gaps' },
  { label: '学习报告', icon: 'chart', to: '/profile?tab=reports', tab: 'reports' }
]

function active(item) {
  return item.tab
    ? route.path === '/profile' && route.query.tab === item.tab
    : item.paths.includes(route.path)
}
async function refreshConversations() {
  if (isGuest.value) {
    conversations.value = []
    return
  }
  try { conversations.value = await listConversations() }
  catch { conversations.value = [] }
}
function navigate(to) {
  if (!window.dispatchEvent(new Event('feynman:before-navigate', { cancelable: true }))) return
  open.value = false
  router.push(to)
}
function newChat() {
  open.value = false
  if (!window.dispatchEvent(new Event('feynman:new-chat', { cancelable: true }))) return
  router.push('/home')
}
function openConversation(id) {
  if (!window.dispatchEvent(new Event('feynman:before-navigate', { cancelable: true }))) return
  open.value = false
  router.push({ path: '/home', query: { conversation: id } })
}
watch(() => route.path, path => {
  open.value = false
  if (path === '/home') refreshConversations()
})
onMounted(() => {
  refreshConversations()
  window.addEventListener('feynman:conversations-updated', refreshConversations)
})
onUnmounted(() => window.removeEventListener('feynman:conversations-updated', refreshConversations))
defineExpose({ openMenu: () => { open.value = true } })
</script>

<template>
  <button v-if="open" class="scrim" type="button" aria-label="关闭导航菜单" @click="open = false"></button>
  <aside class="sidebar" :class="{ 'sidebar--open': open }">
    <button class="brand" type="button" @click="navigate('/home')">
      <span class="brand-mark"><AppIcon name="book" :size="22" /></span><span>费曼伴学</span>
    </button>
    <button class="new-chat" type="button" @click="newChat"><AppIcon name="plus" :size="18" />新对话</button>
    <nav class="nav" aria-label="功能导航">
      <button v-for="item in navigation" :key="item.label" type="button"
        class="nav-item" :class="{ 'nav-item--active': active(item) }"
        :aria-current="active(item) ? 'page' : undefined" @click="navigate(item.to)">
        <AppIcon :name="item.icon" :size="19" /><span>{{ item.label }}</span>
      </button>
    </nav>
    <div class="history">
      <div class="section-title">最近对话</div>
      <div v-if="conversations.length" class="history-list">
        <button v-for="conversation in conversations" :key="conversation.id" type="button"
          class="history-item"
          :class="{ 'history-item--active': route.path === '/home' && conversation.id === route.query.conversation }"
          :title="conversation.title" @click="openConversation(conversation.id)">
          <AppIcon name="chat" :size="16" /><span>{{ conversation.title }}</span>
        </button>
      </div>
      <p v-else class="history-empty">{{ isGuest ? '登录后保存对话' : '暂无对话记录' }}</p>
    </div>
    <button class="profile" type="button" @click="navigate('/profile')">
      <span class="avatar">{{ displayName.slice(0, 1).toUpperCase() }}</span>
      <span class="profile-name">{{ displayName }}</span><AppIcon name="chevron" :size="16" />
    </button>
  </aside>
</template>

<style scoped>
.sidebar { width: 258px; flex: 0 0 258px; height: 100dvh; display: flex; flex-direction: column; padding: 28px 16px 16px; background: #f8fafd; border-right: 1px solid #e9eef6; color: #17233b; }
.brand { display: flex; align-items: center; gap: 11px; height: 40px; margin: 0 11px 28px; padding: 0; color: #17233b; font-size: 19px; font-weight: 700; letter-spacing: .02em; text-align: left; }
.brand-mark { width: 34px; height: 34px; display: grid; place-items: center; color: #fff; background: #2563eb; border-radius: 10px; }
.new-chat { height: 42px; display: flex; align-items: center; justify-content: center; gap: 9px; margin: 0 4px 21px; color: #244d99; background: #fff; border: 1px solid #cbdaf5; border-radius: 10px; font-weight: 600; }
.new-chat:hover { border-color: #76a5f8; background: #f6f9ff; }
.nav { display: grid; gap: 4px; }
.nav-item { display: flex; align-items: center; gap: 13px; width: 100%; min-height: 43px; padding: 0 14px; text-align: left; color: #56657d; border-radius: 10px; font-weight: 500; }
.nav-item:hover, .history-item:hover { background: #edf3fc; color: #1e4faa; }
.nav-item--active { color: #245bd4; background: #eaf1ff; font-weight: 650; }
.history { margin: 24px 9px 0; border-top: 1px solid #e5ebf4; padding-top: 22px; min-height: 90px; overflow-y: auto; }
.section-title { padding: 0 5px 10px; color: #8792a5; font-size: 12px; font-weight: 600; }
.history-list { display: grid; gap: 3px; }
.history-item { width: 100%; display: flex; align-items: center; gap: 10px; min-height: 37px; padding: 0 7px; color: #66758d; border-radius: 8px; text-align: left; font-size: 13px; }
.history-item span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-item--active { background: #eaf1ff; color: #245bd4; }
.history-empty { padding: 4px 5px; color: #a1adbe; font-size: 12px; }
.profile { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 51px; margin-top: auto; padding: 8px; border-top: 1px solid #e5ebf4; color: #17233b; text-align: left; }
.profile:hover { color: #1d4ed8; }
.avatar { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 50%; background: #dfe8f8; color: #325aa6; font-size: 12px; font-weight: 700; }
.profile-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 600; }
.scrim { display: none; }
@media (max-width: 760px) {
  .sidebar { position: fixed; top: 0; bottom: 0; left: 0; z-index: 20; transform: translateX(-100%); transition: transform .2s ease; box-shadow: 12px 0 28px rgba(25, 45, 80, .08); }
  .sidebar--open { transform: translateX(0); }
  .scrim { display: block; position: fixed; inset: 0; z-index: 19; background: rgba(20, 35, 60, .25); }
}
</style>
