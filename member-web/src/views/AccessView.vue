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
  <section class="mw-page">
    <h1 class="mw-page__title">通行记录</h1>
    <p class="mw-page__desc">展示近期门禁验证结果</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <div v-for="e in events" :key="e.id" class="mw-card mw-list-row">
      <div class="mw-list-row__main">
        <div class="mw-list-row__title">门禁点 {{ e.access_point_id }}</div>
        <div class="mw-list-row__meta">
          {{ e.created_at?.slice(0, 19).replace('T', ' ') }}
          <template v-if="e.reason"> · {{ e.reason }}</template>
        </div>
      </div>
      <span class="mw-status" :class="e.allowed ? 'mw-status--ok' : 'mw-status--danger'">
        {{ e.allowed ? '放行' : '拒绝' }}
      </span>
    </div>
    <div v-if="!events.length && !err" class="mw-empty">暂无通行记录</div>
  </section>
</template>
