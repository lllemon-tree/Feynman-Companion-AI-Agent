<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { getSessionList, listConversations } from '@/api/feynman'
import { historyModeForPath, normalizeHistoryItems } from '@/utils/sidebarHistory'
import AppIcon from './AppIcon.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const open = ref(false)
const conversations = ref([])
const profileDropdownOpen = ref(false)
const profileDropdownRef = ref(null)
const isGuest = computed(() => !authStore.isLoggedIn && localStorage.getItem('feynman_guest') === 'true')
const displayName = computed(() => isGuest.value ? '访客' : (authStore.username || '同学'))
const historyMode = computed(() => historyModeForPath(route.path))
const navigation = [
  { label: '学习对话', icon: 'chat', to: '/home', paths: ['/home'] },
  { label: '我的教材', icon: 'book', to: '/upload', paths: ['/upload', '/knowledge'] },
  { label: '知识点学习', icon: 'layers', to: '/select', paths: ['/select', '/study'] },
  { label: '复习计划', icon: 'calendar', to: '/profile?tab=gaps', tab: 'gaps' },
  { label: '学习历史', icon: 'chart', to: '/profile?tab=reports', tab: 'reports' }
]

function active(item) {
  return item.tab
    ? route.path === '/profile' && route.query.tab === item.tab
    : item.paths.includes(route.path)
}
async function refreshConversations() {
  const mode = historyMode.value
  if (isGuest.value || !mode) {
    conversations.value = []
    return
  }
  try {
    const records = mode === 'knowledge' ? await getSessionList() : await listConversations()
    if (historyMode.value === mode) conversations.value = normalizeHistoryItems(mode, records)
  }
  catch {
    if (historyMode.value === mode) conversations.value = []
  }
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
function toggleProfileDropdown() {
  profileDropdownOpen.value = !profileDropdownOpen.value
}
function handleLogout() {
  authStore.logout()
  profileDropdownOpen.value = false
  router.push('/login')
}
function handleProfile() {
  profileDropdownOpen.value = false
  navigate('/profile')
}
function handleLogin() {
  profileDropdownOpen.value = false
  router.push('/login')
}
function closeProfileDropdown(e) {
  if (profileDropdownRef.value && !profileDropdownRef.value.contains(e.target)) {
    profileDropdownOpen.value = false
  }
}
function openConversation(conversation) {
  if (!window.dispatchEvent(new Event('feynman:before-navigate', { cancelable: true }))) return
  open.value = false
  router.push(conversation.route)
}
function isActiveConversation(conversation) {
  return (
    (route.path === '/home' && conversation.id === route.query.conversation) ||
    (route.path === '/study' && conversation.id === route.query.sessionId)
  )
}
watch(() => route.path, () => {
  open.value = false
  refreshConversations()
})
onMounted(() => {
  refreshConversations()
  window.addEventListener('feynman:conversations-updated', refreshConversations)
  window.addEventListener('feynman:sessions-updated', refreshConversations)
  document.addEventListener('click', closeProfileDropdown)
})
onUnmounted(() => {
  window.removeEventListener('feynman:conversations-updated', refreshConversations)
  window.removeEventListener('feynman:sessions-updated', refreshConversations)
  document.removeEventListener('click', closeProfileDropdown)
})
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
    <div v-if="historyMode" class="history">
      <div class="section-title">最近对话</div>
      <div v-if="conversations.length" class="history-list">
        <button v-for="conversation in conversations" :key="conversation.id" type="button"
          class="history-item"
          :class="{ 'history-item--active': isActiveConversation(conversation) }"
          :title="conversation.title" @click="openConversation(conversation)">
          <AppIcon name="chat" :size="16" /><span>{{ conversation.title }}</span>
        </button>
      </div>
      <p v-else class="history-empty">{{ isGuest ? '登录后保存对话' : '暂无对话记录' }}</p>
    </div>
    <div v-if="!isGuest" ref="profileDropdownRef" class="profile-wrapper">
      <button class="profile" type="button" @click.stop="toggleProfileDropdown">
        <span class="avatar">{{ displayName.slice(0, 1).toUpperCase() }}</span>
        <span class="profile-name">{{ displayName }}</span>
        <AppIcon name="chevron" :size="16" :class="{ 'rotate-180': profileDropdownOpen }" />
      </button>
      <div v-if="profileDropdownOpen" class="profile-dropdown">
        <button class="dropdown-item" type="button" @click.stop="handleProfile">
          <AppIcon name="user" :size="14" /><span>个人中心</span>
        </button>
        <button class="dropdown-item dropdown-item--danger" type="button" @click.stop="handleLogout">
          <AppIcon name="logout" :size="14" /><span>退出登录</span>
        </button>
      </div>
    </div>
    <button v-else class="profile profile--login" type="button" @click="handleLogin">
      <span class="avatar">访</span>
      <span class="profile-name">去登录</span>
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
.profile-wrapper { position: relative; margin-top: auto; padding-top: 1px; border-top: 1px solid #e5ebf4; }
.profile { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 51px; padding: 8px; color: #17233b; text-align: left; }
.profile:hover { color: #1d4ed8; }
.profile--login { border-top: 1px solid #e5ebf4; }
.profile-dropdown { position: absolute; bottom: calc(100% + 6px); left: 8px; right: 8px; background: #fff; border: 1px solid #e5ebf4; border-radius: 12px; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08); overflow: hidden; z-index: 50; }
.dropdown-item { width: 100%; display: flex; align-items: center; gap: 8px; padding: 10px 16px; text-align: left; font-size: 14px; color: #17233b; transition: all 150ms; }
.dropdown-item:hover { background: #edf3fc; }
.dropdown-item--danger { color: #ef4444; }
.dropdown-item--danger:hover { background: rgba(239, 68, 68, 0.06); }
.rotate-180 { transform: rotate(180deg); transition: transform 150ms; }
.avatar { width: 30px; height: 30px; display: grid; place-items: center; border-radius: 50%; background: #dfe8f8; color: #325aa6; font-size: 12px; font-weight: 700; }
.profile-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 600; }
.scrim { display: none; }
@media (max-width: 760px) {
  .sidebar { position: fixed; top: 0; bottom: 0; left: 0; z-index: 20; transform: translateX(-100%); transition: transform .2s ease; box-shadow: 12px 0 28px rgba(25, 45, 80, .08); }
  .sidebar--open { transform: translateX(0); }
  .scrim { display: block; position: fixed; inset: 0; z-index: 19; background: rgba(20, 35, 60, .25); }
}
</style>
