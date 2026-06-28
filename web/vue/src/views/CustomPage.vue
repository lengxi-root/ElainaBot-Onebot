<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import axios from '../utils/axios'

const route = useRoute()
const iframeSrc = computed(() => {
  const key = route.params.key
  if (!key) return ''
  const token = localStorage.getItem('elaina_token') || ''
  return `${axios.defaults.baseURL}/api/web-pages/${key}?token=${token}`
})
</script>

<template>
  <div class="custom-page">
    <iframe v-if="iframeSrc" :src="iframeSrc" frameborder="0" class="custom-iframe" />
    <n-empty v-else description="页面加载中..." />
  </div>
</template>

<style scoped>
.custom-page {
  height:calc(100vh - 100px);
  display:flex;
  flex-direction:column
}
.custom-iframe {
  flex:1;
  width:100%;
  border:none;
  border-radius:8px;
  background:var(--bg2)
}
</style>
