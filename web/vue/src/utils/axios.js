import axios from 'axios'

const instance = axios.create({
  baseURL: '',
  timeout: 30000,
})

instance.interceptors.request.use(config => {
  const token = localStorage.getItem('elaina_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

instance.interceptors.response.use(
  res => res,
  error => {
    const url = error.config?.url || ''
    // 登录接口的 401 表示"密码错误", 应交给登录页展示提示, 不能触发跳转
    const isAuthEndpoint = url.includes('/api/auth/login')
    if (error.response?.status === 401 && !isAuthEndpoint) {
      localStorage.removeItem('elaina_token')
      window.location.href = '/web/login'
    }
    return Promise.reject(error)
  }
)

export default instance
