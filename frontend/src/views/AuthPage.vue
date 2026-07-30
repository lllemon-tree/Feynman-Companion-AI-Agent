<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'

const router = useRouter()
const authStore = useAuthStore()

const activeTab = ref('login')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const errors = ref({})
const showPassword = ref(false)
const showConfirmPassword = ref(false)

const isLogin = computed(() => activeTab.value === 'login')
const isLoading = computed(() => authStore.isLoading)

watch(activeTab, () => {
  errors.value = {}
  showPassword.value = false
  showConfirmPassword.value = false
})

function validateForm() {
  errors.value = {}
  
  if (!username.value.trim()) {
    errors.value.username = '请输入用户名'
  } else if (username.value.length < 4 || username.value.length > 16) {
    errors.value.username = '用户名长度为4-16位'
  }
  
  if (!password.value) {
    errors.value.password = '请输入密码'
  } else if (password.value.length < 6) {
    errors.value.password = '密码长度至少6位'
  }
  
  if (!isLogin.value && password.value !== confirmPassword.value) {
    errors.value.confirmPassword = '两次输入的密码不一致'
  }
  
  return Object.keys(errors.value).length === 0
}

async function handleSubmit() {
  if (!validateForm()) return
  
  let success = false
  
  if (isLogin.value) {
    success = await authStore.login(username.value.trim(), password.value)
    if (success) {
      const redirect = router.currentRoute.value.query.redirect || '/upload'
      router.push(redirect)
    }
  } else {
    success = await authStore.register(username.value.trim(), password.value)
    if (success) {
      // 注册成功后自动登录
      const loginSuccess = await authStore.login(username.value.trim(), password.value)
      if (loginSuccess) {
        const redirect = router.currentRoute.value.query.redirect || '/upload'
        router.push(redirect)
      }
    }
  }
}

function handleGuestMode() {
  localStorage.setItem('feynman_guest', 'true')
  router.push('/select')
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-logo-btn" @click="router.push('/select')">费曼伴学</div>
    <div class="auth-container">
      <div class="auth-header">
        <h1 class="auth-title">费曼伴学</h1>
        <p class="auth-subtitle">登录你的学习账号，保存教材与讲解记录</p>
      </div>

      <div class="auth-tabs">
        <div class="tab-indicator" :style="{ transform: isLogin ? 'translateX(0%)' : 'translateX(100%)' }"></div>
        <button
          class="tab-btn"
          :class="{ 'tab-btn--active': isLogin }"
          @click="activeTab = 'login'"
        >
          登录
        </button>
        <button
          class="tab-btn"
          :class="{ 'tab-btn--active': !isLogin }"
          @click="activeTab = 'register'"
        >
          注册
        </button>
      </div>

      <form class="auth-form" @submit.prevent="handleSubmit">
        <div class="form-group">
          <div class="input-wrapper" :class="{ 'input-wrapper--error': errors.username }">
            <input
              v-model="username"
              type="text"
              class="form-input"
              placeholder="请输入用户名（4-16位字母/数字）"
              :disabled="isLoading"
              autocomplete="username"
            />
          </div>
          <p v-if="errors.username" class="error-message">{{ errors.username }}</p>
        </div>

        <div class="form-group">
          <div class="input-wrapper" :class="{ 'input-wrapper--error': errors.password }">
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              class="form-input"
              placeholder="请输入密码（最少6位）"
              :disabled="isLoading"
              autocomplete="current-password"
            />
            <button
              type="button"
              class="eye-toggle"
              @click="showPassword = !showPassword"
              :disabled="isLoading"
            >
              <svg v-if="showPassword" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M9.87 9.87a3 3 0 1 0 4.24 4.24" />
                <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
                <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7c1.49 0 2.93-.26 4.24-.73" />
                <line x1="2" y1="2" x2="22" y2="22" />
              </svg>
              <svg v-else width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          </div>
          <p v-if="errors.password" class="error-message">{{ errors.password }}</p>
        </div>

        <div v-if="!isLogin" class="form-group">
          <div class="input-wrapper" :class="{ 'input-wrapper--error': errors.confirmPassword }">
            <input
              v-model="confirmPassword"
              :type="showConfirmPassword ? 'text' : 'password'"
              class="form-input"
              placeholder="再次输入密码"
              :disabled="isLoading"
              autocomplete="new-password"
            />
            <button
              type="button"
              class="eye-toggle"
              @click="showConfirmPassword = !showConfirmPassword"
              :disabled="isLoading"
            >
              <svg v-if="showConfirmPassword" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M9.87 9.87a3 3 0 1 0 4.24 4.24" />
                <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
                <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7c1.49 0 2.93-.26 4.24-.73" />
                <line x1="2" y1="2" x2="22" y2="22" />
              </svg>
              <svg v-else width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          </div>
          <p v-if="errors.confirmPassword" class="error-message">{{ errors.confirmPassword }}</p>
        </div>

        <p v-if="authStore.errorMsg" class="form-error">{{ authStore.errorMsg }}</p>

        <button
          type="submit"
          class="submit-btn"
          :disabled="isLoading"
        >
          <svg v-if="isLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner">
            <circle cx="12" cy="12" r="10" stroke-linecap="round" stroke-dasharray="16 16" />
          </svg>
          <span>{{ isLoading ? (isLogin ? '登录中' : '注册中') : (isLogin ? '登录' : '注册') }}</span>
        </button>

        <p class="auth-link">
          {{ isLogin ? '还没有账号？' : '已有账号？' }}
          <button type="button" class="link-btn" @click="activeTab = isLogin ? 'register' : 'login'">
            {{ isLogin ? '去注册' : '去登录' }}
          </button>
        </p>

      </form>

      <div class="guest-section">
        <div class="divider">
          <span>或</span>
        </div>
        <button class="guest-btn" @click="handleGuestMode">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          <span>游客模式体验</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  background: linear-gradient(160deg, #f8f9fc 0%, #eef1f7 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 16px;
  font-family: 'Noto Sans SC', 'Inter', sans-serif;
}

.auth-logo-btn {
  position: fixed;
  top: 0;
  left: 0;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
  color: #1E293B;
  cursor: pointer;
  z-index: 20;
  transition: color 150ms;
}

.auth-logo-btn:hover {
  color: #2563EB;
}

.auth-container {
  width: 100%;
  max-width: 420px;
  background: #FFFFFF;
  border-radius: 12px;
  padding: 40px 32px;
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.08), 0 1px 4px rgba(0, 0, 0, 0.04);
}

.auth-header {
  text-align: left;
  margin-bottom: 24px;
}

.auth-title {
  font-size: 24px;
  font-weight: 700;
  color: #1E293B;
  margin: 0 0 6px;
}

.auth-subtitle {
  font-size: 14px;
  color: #64748B;
  margin: 0;
}

.auth-tabs {
  position: relative;
  display: flex;
  border-bottom: 1px solid #E2E8F0;
  margin-bottom: 24px;
}

.tab-indicator {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 2px;
  width: 50%;
  background: #2563EB;
  transition: transform 200ms ease-out;
}

.tab-btn {
  flex: 1;
  padding: 0 0 12px;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 600;
  color: #64748B;
  transition: color 150ms;
}

.tab-btn--active {
  color: #2563EB;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.input-wrapper {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
  background: #FFFFFF;
  transition: all 150ms;
}

.input-wrapper:focus-within {
  border-color: #2563EB;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2);
}

.input-wrapper--error {
  border-color: #F87171;
}

.input-wrapper--error:focus-within {
  box-shadow: 0 0 0 2px rgba(248, 113, 113, 0.2);
}

.form-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 15px;
  color: #1E293B;
  background: transparent;
}

.form-input::placeholder {
  color: #94A3B8;
}

.form-input:disabled {
  opacity: 0.6;
}

.eye-toggle {
  padding: 2px;
  border: none;
  background: transparent;
  color: #94A3B8;
  cursor: pointer;
  transition: color 150ms;
}

.eye-toggle:hover:not(:disabled) {
  color: #1E293B;
}

.eye-toggle:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-left: 4px;
  font-size: 12px;
  color: #EF4444;
}

.form-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 12px;
  font-size: 14px;
  color: #DC2626;
}

.submit-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  background: #2563EB;
  color: #FFFFFF;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2);
  transition: all 150ms;
}

.submit-btn:hover:not(:disabled) {
  background: #1D4ED8;
}

.submit-btn:active:not(:disabled) {
  transform: scale(0.99);
}

.submit-btn:disabled {
  background: #CBD5E1;
  color: #94A3B8;
  cursor: not-allowed;
  box-shadow: none;
}

.auth-link {
  text-align: center;
  font-size: 13px;
  color: #64748B;
  margin: 4px 0 0;
}

.link-btn {
  border: none;
  background: transparent;
  color: #2563EB;
  font-weight: 500;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 4px;
  transition: color 150ms;
}

.link-btn:hover {
  color: #1D4ED8;
}

.spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.guest-section {
  margin-top: 20px;
}

.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #E2E8F0;
}

.divider span {
  font-size: 12px;
  color: #94A3B8;
}

.guest-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #64748B;
  background: #FFFFFF;
  transition: all 150ms;
}

.guest-btn:hover {
  background: #F8FAFC;
  border-color: #CBD5E1;
}

.guest-btn svg {
  color: #94A3B8;
}
</style>