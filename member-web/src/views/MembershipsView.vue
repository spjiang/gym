<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

type Membership = {
  id: number
  status: string
  ends_at: string | null
  remaining_sessions: number | null
  product_id: number
}
type PtPackage = {
  id: number
  status: string
  remaining_sessions: number
  ends_at: string | null
}

const auth = useAuthStore()
const memberships = ref<Membership[]>([])
const packages = ref<PtPackage[]>([])
const err = ref('')

async function load() {
  err.value = ''
  try {
    const mid = auth.merchantId
    const [m, p] = await Promise.all([
      http.get('/member/memberships', { params: { merchant_id: mid } }),
      http.get('/member/pt-packages', { params: { merchant_id: mid } }),
    ])
    memberships.value = m.data
    packages.value = p.data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
  }
}

onMounted(load)
</script>

<template>
  <section>
    <h2>会籍与课包</h2>
    <p v-if="err" class="err">{{ err }}</p>
    <h3>会籍</h3>
    <div v-for="m in memberships" :key="m.id" class="card">
      <div>#{{ m.id }} · {{ m.status }}</div>
      <div class="muted">到期 {{ m.ends_at?.slice(0, 10) || '-' }} · 剩余次 {{ m.remaining_sessions ?? '-' }}</div>
    </div>
    <p v-if="!memberships.length" class="muted">暂无会籍</p>
    <h3>私教课包</h3>
    <div v-for="p in packages" :key="p.id" class="card">
      <div>#{{ p.id }} · {{ p.status }}</div>
      <div class="muted">剩余课时 {{ p.remaining_sessions }} · 到期 {{ p.ends_at?.slice(0, 10) || '-' }}</div>
    </div>
    <p v-if="!packages.length" class="muted">暂无课包</p>
  </section>
</template>
