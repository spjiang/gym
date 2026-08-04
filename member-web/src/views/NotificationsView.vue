<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'

type Note = {
  id: number
  event_type: string
  title: string
  body: string
  created_at: string
}

const notes = ref<Note[]>([])
const error = ref('')

async function refresh() {
  error.value = ''
  try {
    const { data } = await http.get('/member/notifications')
    notes.value = data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

onMounted(refresh)
</script>

<template>
  <section class="mw-page">
    <h1 class="mw-page__title">消息中心</h1>
    <p class="mw-page__desc">系统通知与业务提醒</p>
    <p v-if="error" class="mw-msg mw-msg--error">{{ error }}</p>

    <div v-for="n in notes" :key="n.id" class="mw-card">
      <div class="mw-list-row__title">{{ n.title }}</div>
      <p class="body">{{ n.body }}</p>
      <div class="mw-list-row__meta">
        {{ n.event_type }} · {{ n.created_at?.slice(0, 19).replace('T', ' ') }}
      </div>
    </div>
    <div v-if="!notes.length && !error" class="mw-empty">暂无消息</div>
  </section>
</template>

<style scoped>
.body {
  margin: var(--mw-space-2) 0;
  font-size: 14px;
  color: var(--mw-text);
  line-height: 1.55;
  white-space: pre-wrap;
}
</style>
