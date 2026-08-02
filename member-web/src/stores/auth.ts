import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '../api/http'

export type MemberMe = {
  id: number
  site_id: number
  phone: string
  name: string
  face_status: string
  merchant_ids: number[]
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('member_token') || '')
  const me = ref<MemberMe | null>(null)
  const merchantId = ref<number | undefined>(
    localStorage.getItem('member_merchant_id')
      ? Number(localStorage.getItem('member_merchant_id'))
      : undefined,
  )

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('member_token', t)
  }

  function setMerchantId(id: number | undefined) {
    merchantId.value = id
    if (id == null) localStorage.removeItem('member_merchant_id')
    else localStorage.setItem('member_merchant_id', String(id))
  }

  async function fetchMe() {
    const { data } = await http.get<MemberMe>('/member/me')
    me.value = data
    if (!merchantId.value && data.merchant_ids[0]) {
      setMerchantId(data.merchant_ids[0])
    }
    return data
  }

  function logout() {
    token.value = ''
    me.value = null
    localStorage.removeItem('member_token')
  }

  return { token, me, merchantId, setToken, setMerchantId, fetchMe, logout }
})
