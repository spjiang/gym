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

export type NavSubsystem = {
  code: string
  name: string
  description: string | null
  is_business: boolean
  sort_order: number
  entry_path: string | null
}

export type NavMenu = {
  code: string
  subsystem_code: string
  path: string
  name: string
  sort_order: number
}

export type Navigation = {
  subsystems: NavSubsystem[]
  menus: NavMenu[]
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const me = ref<Me | null>(null)
  const navigation = ref<Navigation | null>(null)

  async function login(username: string, password: string) {
    const { data } = await http.post('/auth/login', { username, password })
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    await fetchMe()
  }

  async function fetchMe() {
    const { data } = await http.get<Me>('/auth/me')
    me.value = data
    await fetchNavigation()
  }

  async function fetchNavigation() {
    try {
      const { data } = await http.get<Navigation>('/me/navigation')
      navigation.value = data
    } catch {
      navigation.value = { subsystems: [], menus: [] }
    }
  }

  function logout() {
    token.value = null
    me.value = null
    navigation.value = null
    localStorage.removeItem('token')
  }

  const isSiteAdmin = () => !!me.value?.role_codes.includes('site_admin')

  return { token, me, navigation, login, fetchMe, fetchNavigation, logout, isSiteAdmin }
})
