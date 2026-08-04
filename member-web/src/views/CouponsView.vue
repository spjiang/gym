<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

type Claimable = {
  id: number
  name: string
  discount_type: string
  fixed_amount: string | null
  percent_off: number | null
  threshold_amount: string
  applicable_to: string
}
type Mine = { id: number; template_id: number; status: string; ends_at: string }

const auth = useAuthStore()
const claimable = ref<Claimable[]>([])
const mine = ref<Mine[]>([])
const msg = ref('')
const err = ref('')
const busyId = ref<number | null>(null)

async function load() {
  const mid = auth.merchantId
  const [c, m] = await Promise.all([
    http.get('/member/coupons/claimable', { params: { merchant_id: mid } }),
    http.get('/member/coupons', { params: { merchant_id: mid } }),
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
      merchant_id: auth.merchantId,
      template_id: id,
    })
    msg.value = '领取成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '领取失败'
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
    <p class="mw-page__desc">领取可用优惠券，并在购卡或消费时使用</p>
    <p v-if="msg" class="mw-msg mw-msg--ok">{{ msg }}</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

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
    <div v-if="!claimable.length" class="mw-empty">暂无可领券</div>

    <h2 class="mw-section-title">我的券</h2>
    <div v-for="c in mine" :key="c.id" class="mw-card mw-list-row">
      <div class="mw-list-row__main">
        <div class="mw-list-row__title">券 #{{ c.id }}</div>
        <div class="mw-list-row__meta">模板 {{ c.template_id }} · 至 {{ c.ends_at?.slice(0, 10) }}</div>
      </div>
      <span class="mw-status mw-status--neutral">{{ c.status }}</span>
    </div>
    <div v-if="!mine.length" class="mw-empty">暂无卡券</div>
  </section>
</template>
