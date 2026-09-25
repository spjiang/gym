import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  config.headers['X-Client-Channel'] = 'member_h5'
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error.response?.status
    const url = String(error.config?.url || '')
    const message = error.response?.data?.message || error.message || '请求失败'
    if (status === 401 && !url.includes('/member/auth/')) {
      const auth = useAuthStore()
      auth.logout()
      void import('../router').then(({ default: router }) => {
        if (router.currentRoute.value.name !== 'login') {
          void router.replace({ name: 'login' })
        }
      })
    }
    return Promise.reject(new Error(message))
  },
)

export default http
