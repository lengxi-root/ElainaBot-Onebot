<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const message = useMessage()
const auth = useAuthStore()

const loading = ref(false)
const form = reactive({ password: '' })

async function handleLogin() {
  if (!form.password) { message.warning('请输入密码'); return }
  loading.value = true
  try {
    await auth.login(form.password)
    message.success('登录成功')
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    message.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-box">
      <div class="login-logo">
        <img class="login-logo-icon" src="/favicon.svg" alt="Elaina" />
        <h1>Elaina 管理面板</h1>
        <p>请输入管理员密码登录</p>
      </div>
      <n-card class="login-card" :bordered="false">
        <n-form ref="formRef" :model="form" @submit.prevent="handleLogin">
          <n-form-item label="密码" path="password">
            <n-input
              v-model:value="form.password"
              type="password"
              show-password-on="click"
              placeholder="管理员密码"
              size="large"
            />
          </n-form-item>
          <n-button type="primary" block size="large" :loading="loading" @click="handleLogin" class="login-btn">
            登 录
          </n-button>
        </n-form>
        <div class="forgot-row">
          <n-tooltip trigger="hover" placement="bottom">
            <template #trigger>
              <span class="forgot-link">忘记密码？</span>
            </template>
            如果忘记密码，请进入项目目录 /config/settings.yaml 中修改 web.admin_password 配置项并重启框架
          </n-tooltip>
        </div>
      </n-card>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height:100vh;
  display:flex;
  align-items:center;
  justify-content:center;
  background:var(--bg)
}
.login-box {
  width:100%;
  max-width:380px;
  padding:0 16px
}
.login-logo {
  text-align:center;
  margin-bottom:32px
}
.login-logo-icon {
  width:64px;
  height:64px;
  border-radius:16px;
  margin:0 auto 16px;
  -o-object-fit:contain;
  object-fit:contain
}
.login-logo h1 {
  color:var(--text);
  font-size:22px;
  font-weight:700;
  margin:0 0 4px
}
.login-logo p {
  color:var(--text2);
  font-size:14px;
  margin:0
}
.login-card {
  background:var(--bg2)!important;
  border:1px solid var(--border)!important
}
.login-btn {
  background-color:var(--accent, #5865f2)!important;
  background-image:linear-gradient(135deg, var(--accent, #5865f2), var(--accent-light, #7289da))!important;
  border:none!important;
  color:#fff!important
}
.forgot-row {
  text-align:center;
  margin-top:12px
}
.forgot-link {
  color:var(--text3);
  font-size:13px;
  cursor:pointer;
  transition:color .2s
}
.forgot-link:hover {
  color:var(--accent)
}
</style>
