<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'

type Event = {
  id: number
  access_point_id: number
  allowed: boolean
  reason: string | null
  created_at: string
}

const events = ref<Event[]>([])
const err = ref('')

onMounted(async () => {
  try {
    const { data } = await http.get('/member/access-events')
    events.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
  }
})
</script>

<template>
  <section>
    <h2>通行记录</h2>
    <p v-if="err" class="err">{{ err }}</p>
    <div v-for="e in events" :key="e.id" class="card">
      <div>#{{ e.id }} · 门禁点 {{ e.access_point_id }} · {{ e.allowed ? '放行' : '拒绝' }}</div>
      <div class="muted">{{ e.created_at?.slice(0, 19).replace('T', ' ') }} {{ e.reason || '' }}</div>
    </div>
    <p v-if="!events.length" class="muted">暂无记录</p>
  </section>
</template>
