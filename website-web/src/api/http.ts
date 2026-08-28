import axios, { AxiosError } from 'axios'

export class ApiError extends Error {
  status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
})

http.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<{ message?: string }>) => {
    const message = error.response?.data?.message || error.message || '请求失败'
    return Promise.reject(new ApiError(message, error.response?.status ?? null))
  },
)

export default http
