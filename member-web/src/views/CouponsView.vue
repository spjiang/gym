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
  try {
    await http.post('/member/coupons/claim', {
      merchant_id: auth.merchantId,
      template_id: id,
    })
    msg.value = '领取成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '领取失败'
  }
}

function face(c: Claimable) {
  return c.discount_type === 'fixed' ? `减¥${c.fixed_amount}` : `${c.percent_off}% 折`
}

onMounted(load)
</script>

<template>
  <section>
    <h2>领券</h2>
    <p v-if="msg" class="muted">{{ msg }}</p>
    <p v-if="err" class="err">{{ err }}</p>
    <h3>可领取</h3>
    <div v-for="c in claimable" :key="c.id" class="card row">
      <div>
        <div>{{ c.name }}</div>
        <div class="muted">{{ face(c) }} · 门槛 ¥{{ c.threshold_amount }}</div>
      </div>
      <button @click="claim(c.id)">领取</button>
    </div>
    <p v-if="!claimable.length" class="muted">暂无可领券</p>
    <h3>我的券</h3>
    <div v-for="c in mine" :key="c.id" class="card">
      <strong>#{{ c.id }}</strong>
      <span class="muted"> 模板 {{ c.template_id }} · {{ c.status }} · 至 {{ c.ends_at?.slice(0, 10) }}</span>
    </div>
  </section>
</template>

<style scoped>
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}
.err {
  color: #b91c1c;
}
</style>
