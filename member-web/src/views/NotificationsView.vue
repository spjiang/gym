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
  <section>
    <h2>消息</h2>
    <p v-if="error" class="muted">{{ error }}</p>
    <div v-for="n in notes" :key="n.id" class="card">
      <strong>{{ n.title }}</strong>
      <p>{{ n.body }}</p>
      <p class="muted">{{ n.event_type }} · {{ n.created_at }}</p>
    </div>
    <p v-if="!notes.length && !error" class="muted">暂无消息</p>
  </section>
</template>
