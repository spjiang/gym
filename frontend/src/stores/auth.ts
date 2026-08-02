import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '../api/http'

export type Me = {
  id: number
  username: string
  display_name: string
  site_id: number
  merchant_id: number | null
  role_codes: string[]
  permissions: string[]
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const me = ref<Me | null>(null)

  async function login(username: string, password: string) {
    const { data } = await http.post('/auth/login', { username, password })
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    await fetchMe()
  }

  async function fetchMe() {
    const { data } = await http.get<Me>('/auth/me')
    me.value = data
  }

  function logout() {
    token.value = null
    me.value = null
    localStorage.removeItem('token')
  }

  const isSiteAdmin = () => !!me.value?.role_codes.includes('site_admin')

  return { token, me, login, fetchMe, logout, isSiteAdmin }
})
