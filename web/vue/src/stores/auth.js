import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from '../utils/axios'

const WEAK_PASSWORDS = new Set(['admin', '123456', 'password', 'admin123', '12345678'])

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('elaina_token') || '')
  const isLoggedIn = computed(() => !!token.value)
  const isWeakPassword = ref(localStorage.getItem('elaina_weak_pwd') === '1')

  async function login(password) {
    try {
      const res = await axios.post('/api/auth/login', { password })
      if (res.data.success) {
        token.value = res.data.token
        localStorage.setItem('elaina_token', token.value)
        const weak = WEAK_PASSWORDS.has(password)
        isWeakPassword.value = weak
        if (weak) localStorage.setItem('elaina_weak_pwd', '1')
        else localStorage.removeItem('elaina_weak_pwd')
        return true
      }
      throw new Error(res.data.error || '登录失败')
    } catch (e) {
      const msg = e.response?.data?.error || e.message || '登录失败'
      throw new Error(msg)
    }
  }

  function logout() {
    token.value = ''
    localStorage.removeItem('elaina_token')
    localStorage.removeItem('elaina_weak_pwd')
    isWeakPassword.value = false
  }

  async function checkSession() {
    if (!token.value) return false
    try {
      return (await axios.get('/api/auth/check')).data.success
    } catch {
      logout()
      return false
    }
  }

  return { token, isLoggedIn, isWeakPassword, login, logout, checkSession }
})
