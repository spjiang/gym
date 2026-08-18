import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const status = error.response?.status
    const url = String(error.config?.url || '')
    if (
      status === 403 &&
      !url.includes('/auth/me') &&
      !url.includes('/me/navigation')
    ) {
      const auth = useAuthStore()
      if (auth.token) {
        try {
          await auth.fetchMe()
        } catch {
          /* 刷新权限失败时仍把原错误抛给页面 */
        }
      }
    }
    const message = error.response?.data?.message || error.message || '请求失败'
    return Promise.reject(new Error(message))
  },
)

export default http
