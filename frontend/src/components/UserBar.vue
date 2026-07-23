<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'

const router = useRouter()
const authStore = useAuthStore()
const dropdownOpen = ref(false)
const dropdownRef = ref(null)

const isLoggedIn = computed(() => authStore.isLoggedIn)
const username = computed(() => authStore.username)

function handleLogin() {
  router.push('/login')
}

function handleLogout() {
  authStore.logout()
  dropdownOpen.value = false
  router.push('/upload')
}

function toggleDropdown() {
  dropdownOpen.value = !dropdownOpen.value
}

function closeDropdown() {
  dropdownOpen.value = false
}

function handleClickOutside(e) {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target)) {
    dropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div ref="dropdownRef" class="user-bar">
    <template v-if="isLoggedIn">
      <button
        class="user-btn"
        @click.stop="toggleDropdown"
      >
        <div class="user-avatar">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <span class="user-name">{{ username }}</span>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ 'rotate-180': dropdownOpen }">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      <div v-if="dropdownOpen" class="user-dropdown">
        <button class="dropdown-item dropdown-item--danger" @click.stop="handleLogout">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          <span>退出登录</span>
        </button>
      </div>
    </template>

    <button v-else class="login-btn" @click="handleLogin">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M11 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-5" />
        <polyline points="11 5 17 5 17 11" />
      </svg>
      <span>去登录</span>
    </button>
  </div>
</template>

<style scoped>
.user-bar {
  position: relative;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.login-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 10px;
  border: 1px solid rgba(37, 99, 235, 0.3);
  background: rgba(37, 99, 235, 0.06);
  font-size: 14px;
  font-weight: 600;
  color: #2563EB;
  transition: all 150ms;
}

.login-btn:hover {
  background: rgba(37, 99, 235, 0.12);
  border-color: rgba(37, 99, 235, 0.5);
}

.user-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #E2E8F0;
  background: #FFFFFF;
  font-size: 14px;
  font-weight: 500;
  color: #1E293B;
  transition: all 150ms;
}

.user-btn:hover {
  background: #F1F5F9;
}

.user-btn:focus-visible {
  outline: none;
  border-color: #2563EB;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.user-avatar {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(37, 99, 235, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2563EB;
}

.user-name {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  width: 144px;
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.08), 0 1px 4px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  z-index: 50;
}

.dropdown-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  text-align: left;
  font-size: 14px;
  color: #1E293B;
  transition: all 150ms;
}

.dropdown-item:hover {
  background: #F1F5F9;
}

.dropdown-item--danger {
  color: #EF4444;
}

.dropdown-item--danger:hover {
  background: rgba(239, 68, 68, 0.06);
}

.rotate-180 {
  transform: rotate(180deg);
  transition: transform 150ms;
}
</style>
