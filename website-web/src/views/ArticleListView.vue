<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import http from '../api/http'
import type { ArticleChannel, NewsBrief, Page } from '../api/types'

const props = defineProps<{ channel: ArticleChannel }>()
const TITLES: Record<ArticleChannel, string> = { news: '新闻动态', jobs: '招聘信息', partners: '招商入驻' }
const LEADS: Record<ArticleChannel, string> = {
  news: '园区开放、课表、驻场与市集。访客只阅读，办业务请走会员中心。',
  jobs: '职位说明与到店联系方式。官网不设投递表单，请按每条文末提示联系前台。',
  partners: '铺位、快闪与合作说明。需到店看场，不在此页留资或支付意向金。',
}

const items = ref<NewsBrief[]>([])
const error = ref('')
const loading = ref(false)

function formatDay(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await http.get<Page<NewsBrief>>('/public/website/articles', {
      params: { channel: props.channel, page: 1, page_size: 50 },
    })
    items.value = data.items
  } catch {
    error.value = '暂时无法加载'
    items.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.channel, load)
</script>

<template>
  <section class="page">
    <header class="intro">
      <h1>{{ TITLES[channel] }}</h1>
      <p>{{ LEADS[channel] }}</p>
    </header>
    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="muted">{{ error }}</p>
    <p v-else-if="!items.length" class="muted">暂无内容</p>
    <div v-else class="grid">
      <RouterLink v-for="n in items" :key="n.id" class="card" :to="`/${channel}/${n.id}`">
        <img v-if="n.cover_image_url" :src="n.cover_image_url" alt="" />
        <div>
          <small>{{ formatDay(n.published_at) }}</small>
          <strong>{{ n.title }}</strong>
          <span>{{ n.summary }}</span>
        </div>
      </RouterLink>
    </div>
  </section>
</template>

<style scoped>
.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 40px 28px 80px;
}
.intro {
  max-width: 40em;
  margin-bottom: 28px;
}
h1 {
  margin: 0 0 10px;
}
.intro p,
.muted {
  color: var(--muted);
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.card {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 0;
  background: var(--bg-2);
  border: 1px solid var(--line);
  overflow: hidden;
  min-height: 140px;
}
.card img {
  height: 100%;
  min-height: 140px;
  width: 180px;
  object-fit: cover;
}
.card:not(:has(img)) {
  grid-template-columns: 1fr;
}
.card div {
  padding: 16px 16px 18px;
}
.card small {
  color: var(--cyan);
  font-size: 12px;
}
.card strong {
  display: block;
  margin: 6px 0 8px;
}
.card span {
  color: var(--muted);
  font-size: 14px;
}
@media (max-width: 800px) {
  .grid,
  .card {
    grid-template-columns: 1fr;
  }
  .card img {
    width: 100%;
    height: 160px;
  }
}
</style>
