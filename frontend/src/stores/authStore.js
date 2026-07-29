import { defineStore } from 'pinia'
import { login, register, getCurrentUser as apiGetCurrentUser } from '@/api/feynman'

const TOKEN_KEY = 'feynman_token'
const USER_KEY = 'feynman_user'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
    isLoading: false,
    errorMsg: ''
  }),

  getters: {
    isLoggedIn: (state) => !!state.token && !!state.user,
    username: (state) => state.user?.username || '',
    userId: (state) => state.user?.user_id || ''
  },

  actions: {
    setToken(token) {
      this.token = token
      localStorage.setItem(TOKEN_KEY, token)
    },

    setUser(user) {
      this.user = user
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },

    clearAuth() {
      this.token = ''
      this.user = null
      this.errorMsg = ''
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      localStorage.removeItem('feynman_guest')
    },

    async login(username, password) {
      this.isLoading = true
      this.errorMsg = ''

      try {
        const data = await login(username, password)
        
        this.setToken(data.token)
        this.setUser({
          user_id: data.user_id,
          username: data.username
        })
        return true
      } catch (e) {
        this.errorMsg = e.message || '登录失败，请稍后重试'
        return false
      } finally {
        this.isLoading = false
      }
    },

    async register(username, password) {
      this.isLoading = true
      this.errorMsg = ''

      try {
        const data = await register(username, password)
        return true
      } catch (e) {
        this.errorMsg = e.message || '注册失败，请稍后重试'
        return false
      } finally {
        this.isLoading = false
      }
    },

    async getCurrentUser() {
      if (!this.token) return null

      try {
        const data = await apiGetCurrentUser()
        this.setUser(data)
        return data
      } catch (e) {
        this.clearAuth()
        return null
      }
    },

    logout() {
      this.clearAuth()
    }
  }
})