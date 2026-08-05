import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import http from '../api/http'

export type MemberMerchant = {
  id: number
  name: string
  subsystem_codes: string[]
  primary_system: string | null
}

export type MemberMe = {
  id: number
  site_id: number
  phone: string
  name: string
  face_status: string
  merchant_ids: number[]
  merchants: MemberMerchant[]
  acquisition_source?: string
  first_merchant_id?: number | null
  first_merchant_name?: string | null
}

export function pathForMerchant(m: MemberMerchant) {
  const sys = m.primary_system || m.subsystem_codes[0]
  if (sys === 'catering') return `/m/${m.id}/catering`
  return `/m/${m.id}/gym`
}

export const useAuthStore = defineStore('member-auth', () => {
  const token = ref(localStorage.getItem('member_token') || '')
  const me = ref<MemberMe | null>(null)
  const merchantId = ref<number | undefined>(
    localStorage.getItem('member_merchant_id')
      ? Number(localStorage.getItem('member_merchant_id'))
      : undefined,
  )

  const currentMerchant = computed(() => me.value?.merchants.find((m) => m.id === merchantId.value) || null)

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
    me.value = {
      ...data,
      merchants: data.merchants || [],
    }
    if (merchantId.value && !me.value.merchants.some((m) => m.id === merchantId.value)) {
      setMerchantId(undefined)
    }
    return me.value
  }

  function logout() {
    token.value = ''
    me.value = null
    setMerchantId(undefined)
    localStorage.removeItem('member_token')
  }

  return {
    token,
    me,
    merchantId,
    currentMerchant,
    setToken,
    setMerchantId,
    fetchMe,
    logout,
    pathForMerchant,
  }
})
