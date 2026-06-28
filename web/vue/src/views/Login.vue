<template>
  <div class="login-page">
    <div class="login-box">
      <div class="login-logo">
        <img class="login-logo-icon" :src="faviconUrl" alt="Elaina" />
        <h1>Elaina 管理面板</h1>
        <p>请输入管理员密码登录</p>
      </div>
      <div class="login-card">
        <form @submit.prevent="doLogin">
          <div class="form-field">
            <label>密码</label>
            <input
              :type="showPwd ? 'text' : 'password'"
              v-model="password"
              placeholder="管理员密码"
              class="login-input"
              autofocus
            />
            <button type="button" class="toggle-pwd" @click="showPwd = !showPwd">
              {{ showPwd ? '隐藏' : '显示' }}
            </button>
          </div>
          <button type="submit" class="login-btn" :disabled="loading">
            {{ loading ? '登录中...' : '登 录' }}
          </button>
          <div class="login-error" v-if="error">{{ error }}</div>
        </form>
      </div>
      <div class="forgot-row">
        <span class="forgot-link" title="进入项目目录 /config/settings.yaml 修改 web.admin_password 配置并重启框架">忘记密码？</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const faviconUrl = import.meta.env.BASE_URL + 'favicon.svg'
const password = ref('')
const error = ref('')
const loading = ref(false)
const showPwd = ref(false)

async function doLogin() {
  if (!password.value) { error.value = '请输入密码'; return }
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: password.value }),
    })
    const data = await res.json()
    if (data.success && data.token) {
      localStorage.setItem('elaina_token', data.token)
      const redirect = route.query.redirect || '/web/'
      router.push(redirect)
    } else {
      error.value = data.error || '登录失败'
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
  background: var(--bg);
}
.login-box { width: 100%; max-width: 380px; padding: 0 16px; }

.login-logo { text-align: center; margin-bottom: 32px; }
.login-logo-icon { width: 64px; height: 64px; border-radius: 16px; margin: 0 auto 16px; object-fit: contain; }
.login-logo h1 { color: var(--text); font-size: 22px; font-weight: 700; margin: 0 0 4px; }
.login-logo p { color: var(--text2); font-size: 14px; margin: 0; }

.login-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 24px;
}

.form-field { margin-bottom: 16px; position: relative; }
.form-field label { display: block; font-size: 13px; color: var(--text2); margin-bottom: 6px; font-weight: 500; }
.login-input {
  width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px;
  font-size: 14px; outline: none; background: var(--bg); color: var(--text);
}
.login-input:focus { border-color: var(--accent); }
.toggle-pwd {
  position: absolute; right: 10px; top: 32px; background: none; border: none;
  color: var(--text3); font-size: 12px; cursor: pointer;
}
.toggle-pwd:hover { color: var(--text); }

.login-btn {
  width: 100%; padding: 10px; border: none; border-radius: 6px;
  background: linear-gradient(135deg, var(--accent), var(--accent-light));
  color: #fff; font-size: 15px; font-weight: 600; cursor: pointer;
  transition: opacity 0.2s;
}
.login-btn:hover { opacity: 0.9; }
.login-btn:disabled { opacity: 0.5; cursor: default; }

.login-error { color: var(--danger); font-size: 13px; margin-top: 10px; text-align: center; }

.forgot-row { text-align: center; margin-top: 12px; }
.forgot-link { color: var(--text3); font-size: 13px; cursor: pointer; transition: color 0.2s; }
.forgot-link:hover { color: var(--accent); }
</style>
