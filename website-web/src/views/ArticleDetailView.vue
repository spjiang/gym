<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import MarkdownView from '../components/MarkdownView.vue'
import http, { ApiError } from '../api/http'
import type { ArticleChannel, ArticleDetail } from '../api/types'

const props = defineProps<{ channel: ArticleChannel }>()
const BACK: Record<ArticleChannel, { to: string; label: string }> = {
  news: { to: '/news', label: '返回新闻' },
  jobs: { to: '/jobs', label: '返回招聘' },
  partners: { to: '/partners', label: '返回招商' },
}
const route = useRoute()
const article = ref<ArticleDetail | null>(null)
const missing = ref(false)
const fail = ref(false)

function formatDay(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
}

async function load() {
  missing.value = false
  fail.value = false
  article.value = null
  const id = Number(route.params.id)
  if (!Number.isFinite(id)) {
    missing.value = true
    return
  }
  try {
    const { data } = await http.get<ArticleDetail>(`/public/website/articles/${id}`)
    if (data.channel !== props.channel) {
      missing.value = true
      return
    }
    article.value = data
  } catch (e: unknown) {
    if (e instanceof ApiError && e.status === 404) {
      missing.value = true
      return
    }
    fail.value = true
  }
}

onMounted(load)
watch(() => [route.params.id, props.channel], load)
</script>

<template>
  <article class="page">
    <p v-if="missing" class="muted">内容不存在或已下架</p>
    <p v-else-if="fail" class="muted">暂时无法加载</p>
    <template v-else-if="article">
      <RouterLink class="back" :to="BACK[channel].to">{{ BACK[channel].label }}</RouterLink>
      <h1>{{ article.title }}</h1>
      <p v-if="article.published_at" class="day">{{ formatDay(article.published_at) }}</p>
      <p v-if="article.summary" class="sum">{{ article.summary }}</p>
      <img v-if="article.cover_image_url" class="cover" :src="article.cover_image_url" alt="" />
      <MarkdownView :content="article.body" empty-text="" />
      <p v-if="article.contact_hint" class="contact">{{ article.contact_hint }}</p>
    </template>
  </article>
</template>

<style scoped>
.page {
  max-width: 760px;
  margin: 0 auto;
  padding: 40px 28px 80px;
}
.back {
  display: inline-block;
  margin-bottom: 16px;
  color: var(--orange);
  font-size: 14px;
}
h1 {
  margin: 0 0 10px;
  font-size: clamp(26px, 4vw, 38px);
}
.day {
  margin: 0;
  color: var(--cyan);
  font-size: 13px;
}
.sum {
  color: var(--muted);
  font-size: 17px;
  line-height: 1.7;
}
.cover {
  width: 100%;
  max-height: 420px;
  object-fit: cover;
  border-radius: 10px;
  margin: 20px 0 8px;
}
.contact {
  margin-top: 32px;
  padding: 16px 18px;
  border: 1px solid var(--line);
  background: var(--bg-2);
  color: var(--muted);
}
.muted {
  color: var(--muted);
}
</style>
