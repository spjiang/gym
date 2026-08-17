import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const SUB_KEY = 'gym_ops_subsystem'
const MERCHANT_KEY = 'gym_ops_merchant_id'

export type OpsSubsystem = 'gym' | 'catering'

export const useOpsStore = defineStore('ops', () => {
  const savedSub = (localStorage.getItem(SUB_KEY) || 'gym') as OpsSubsystem
  const savedMerchant = localStorage.getItem(MERCHANT_KEY)

  const subsystem = ref<OpsSubsystem>(savedSub === 'catering' ? 'catering' : 'gym')
  const merchantId = ref<number | null>(savedMerchant ? Number(savedMerchant) : null)

  const subsystemLabel = computed(() => (subsystem.value === 'catering' ? '观野BAR' : '观野FIT'))

  function setSubsystem(code: OpsSubsystem) {
    subsystem.value = code
    localStorage.setItem(SUB_KEY, code)
  }

  function setMerchantId(id: number | null) {
    merchantId.value = id
    if (id == null) localStorage.removeItem(MERCHANT_KEY)
    else localStorage.setItem(MERCHANT_KEY, String(id))
  }

  return { subsystem, merchantId, subsystemLabel, setSubsystem, setMerchantId }
})
