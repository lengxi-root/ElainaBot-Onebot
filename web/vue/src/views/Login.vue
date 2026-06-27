<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="login-header">
        <div class="login-logo">E</div>
        <h1>Elaina Panel</h1>
        <p>OneBot 管理面板</p>
      </div>
      <form @submit.prevent="handleLogin" class="login-form">
        <div class="input-group">
          <input
            v-model="password"
            type="password"
            placeholder="输入管理密码"
            class="input"
            autofocus
          />
        </div>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button type="submit" class="btn btn-primary login-btn" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'

const router = useRouter()
const store = useAppStore()
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const res = await store.postApi('/auth/login', { password: password.value })
    if (res && res.success) {
      localStorage.setItem('elaina_token', res.token)
      router.push('/web/')
    } else {
      error.value = res?.error || '登录失败'
    }
  } catch (e) {
    error.value = '网络错误'
  }
  loading.value = false
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f8f9fc 0%, #eef0ff 100%);
}

.login-card {
  width: 380px;
  padding: 40px;
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-logo {
  width: 56px;
  height: 56px;
  margin: 0 auto 16px;
  background: linear-gradient(135deg, var(--color-primary), #7c3aed);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 24px;
}

.login-header h1 {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 4px;
}

.login-header p {
  color: var(--color-text-muted);
  font-size: 14px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  outline: none;
  transition: border-color var(--transition);
  background: var(--color-bg);
}

.input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(88, 101, 242, 0.1);
}

.login-btn {
  width: 100%;
  padding: 12px;
  font-size: 15px;
  justify-content: center;
}

.error-text {
  color: var(--color-danger);
  font-size: 13px;
  text-align: center;
}
</style>
