<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'
import { couponStatusLabel } from '../utils/labels'

type Claimable = {
  id: number
  name: string
  discount_type: string
  fixed_amount: string | null
  percent_off: number | null
  threshold_amount: string
  applicable_to: string
}
type Mine = {
  id: number
  template_id: number
  status: string
  ends_at: string
  template_name?: string | null
  discount_type?: string | null
  fixed_amount?: string | null
  percent_off?: number | null
  threshold_amount?: string | null
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const system = computed(() => (route.path.includes('/catering') ? 'catering' : 'gym'))
const merchantId = computed(() => Number(route.params.merchantId) || auth.merchantId)
const claimable = ref<Claimable[]>([])
const mine = ref<Mine[]>([])
const msg = ref('')
const err = ref('')
const busyId = ref<number | null>(null)

async function load() {
  const mid = merchantId.value
  const [c, m] = await Promise.all([
    http.get('/member/coupons/claimable', { params: { merchant_id: mid, system: system.value } }),
    http.get('/member/coupons', { params: { merchant_id: mid, system: system.value } }),
  ])
  claimable.value = c.data
  mine.value = m.data
}

async function claim(id: number) {
  msg.value = ''
  err.value = ''
  busyId.value = id
  try {
    await http.post('/member/coupons/claim', {
      merchant_id: merchantId.value,
      template_id: id,
    })
    msg.value = '领取成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '领取失败'
    await load()
  } finally {
    busyId.value = null
  }
}

function face(c: Claimable) {
  return c.discount_type === 'fixed' ? `减¥${c.fixed_amount}` : `${c.percent_off}% 折`
}

onMounted(load)
</script>

<template>
  <section class="mw-page">
    <h1 class="mw-page__title">优惠卡券</h1>
    <p class="mw-page__desc">{{ system === 'catering' ? '领取餐饮券，点餐结算时使用' : '领取可用优惠券，并在购卡或消费时使用' }}</p>
    <button
      v-if="system === 'catering' && merchantId"
      class="mw-btn mw-btn--ghost mw-btn--sm"
      type="button"
      style="margin-bottom: 12px"
      @click="router.push(`/m/${merchantId}/catering`)"
    >
      去点餐使用
    </button>
    <p v-if="msg" class="mw-msg mw-msg--ok">{{ msg }}</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <template v-if="claimable.length">
      <h2 class="mw-section-title">可领取</h2>
      <div v-for="c in claimable" :key="c.id" class="mw-card mw-list-row">
        <div class="mw-list-row__main">
          <div class="mw-list-row__title">{{ c.name }}</div>
          <div class="mw-price">{{ face(c) }}</div>
          <div class="mw-list-row__meta">满 ¥{{ c.threshold_amount }} 可用</div>
        </div>
        <button
          class="mw-btn mw-btn--sm mw-list-row__action"
          type="button"
          :disabled="busyId === c.id"
          @click="claim(c.id)"
        >
          {{ busyId === c.id ? '领取中' : '领取' }}
        </button>
      </div>
    </template>

    <h2 class="mw-section-title">我的券</h2>
    <div v-for="c in mine" :key="c.id" class="mw-card mw-list-row">
      <div class="mw-list-row__main">
        <div class="mw-list-row__title">{{ c.template_name || `券 #${c.id}` }}</div>
        <div class="mw-list-row__meta">至 {{ c.ends_at?.slice(0, 10) }}</div>
      </div>
      <span class="mw-status mw-status--neutral">{{ couponStatusLabel(c.status) }}</span>
    </div>
    <div v-if="!mine.length" class="mw-empty">暂无卡券</div>
  </section>
</template>
