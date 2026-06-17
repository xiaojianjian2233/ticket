// axios 封装：统一 baseURL / JWT 注入 / {code,message,data} 解包 / 401-403 处理
import axios from 'axios'
import { ElMessage } from 'element-plus'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 60000,
})

service.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

service.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      if (body.code === 401) {
        localStorage.removeItem('token')
        ElMessage.error('登录已过期，请重新登录')
        if (!location.hash.includes('/login')) location.href = import.meta.env.BASE_URL + '#/login'
        return Promise.reject(body)
      }
      if (body.code === 403) ElMessage.error(body.message || '您没有权限执行此操作')
      else ElMessage.error(body.message || '请求失败')
      return Promise.reject(body)
    }
    return body
  },
  (err) => {
    ElMessage.error(err?.message || '网络异常，请重试')
    return Promise.reject(err)
  },
)

export default service
