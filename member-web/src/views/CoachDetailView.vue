<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'

type Coach = {
  id: number
  merchant_id: number
  display_name: string
  title: string | null
  gender: string | null
  phone: string | null
  years_experience: number | null
  hourly_rate: string | null
  specialties: string | null
  certifications: string | null
  bio: string | null
  availability_note: string | null
  avatar_url: string | null
  intro_image_urls: string[]
}

const GENDER: Record<string, string> = { male: '男', female: '女', other: '其他' }

const route = useRoute()
const router = useRouter()
const mid = computed(() => Number(route.params.merchantId))
const coachId = computed(() => Number(route.params.coachId))
const fromSession = computed(() => {
  const raw = route.query.from
  const n = Number(Array.isArray(raw) ? raw[0] : raw)
  return n && !Number.isNaN(n) ? n : null
})
const item = ref<Coach | null>(null)
const err = ref('')
const loading = ref(true)

function genderText(code: string | null) {
  if (!code) return '—'
  return GENDER[code] || code
}

function back() {
  if (fromSession.value) {
    router.push(`/m/${mid.value}/gym/classes/${fromSession.value}`)
    return
  }
  router.push(`/m/${mid.value}/gym/classes`)
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await http.get<Coach>(`/member/coaches/${coachId.value}`)
    if (data.merchant_id !== mid.value) {
      err.value = '该教练不属于当前门店'
      item.value = null
      return
    }
    item.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
    item.value = null
  } finally {
    loading.value = false
  }
}

watch(coachId, load, { immediate: true })
</script>

<template>
  <section class="mw-page">
    <button class="back" type="button" @click="back">← {{ fromSession ? '团课详情' : '团课预约' }}</button>

    <p v-if="loading" class="mw-page__desc">加载中…</p>
    <p v-else-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <template v-else-if="item">
      <div class="hero mw-card">
        <div class="hero__avatar">
          <img v-if="item.avatar_url" :src="item.avatar_url" alt="" />
          <span v-else>{{ item.display_name.slice(0, 1) }}</span>
        </div>
        <div>
          <h1 class="mw-page__title">{{ item.display_name }}</h1>
          <p class="mw-page__desc">{{ item.title || '教练' }} · {{ genderText(item.gender) }}</p>
        </div>
      </div>

      <div class="mw-card">
        <div class="row"><span>电话</span><strong>{{ item.phone || '—' }}</strong></div>
        <div class="row">
          <span>从业年限</span>
          <strong>{{ item.years_experience != null ? `${item.years_experience} 年` : '—' }}</strong>
        </div>
        <div class="row"><span>课时参考价</span><strong>{{ item.hourly_rate ? `¥${item.hourly_rate}` : '—' }}</strong></div>
        <div class="row"><span>擅长</span><strong>{{ item.specialties || '—' }}</strong></div>
        <div class="row"><span>可约时段</span><strong>{{ item.availability_note || '—' }}</strong></div>
        <div class="row"><span>资质证书</span><strong>{{ item.certifications || '—' }}</strong></div>
        <div class="row"><span>个人简介</span><strong>{{ item.bio || '—' }}</strong></div>
      </div>

      <div v-if="item.intro_image_urls.length" class="gallery">
        <img v-for="url in item.intro_image_urls" :key="url" :src="url" alt="" />
      </div>
    </template>
  </section>
</template>

<style scoped>
.back {
  border: 0;
  background: transparent;
  color: var(--mw-brand);
  padding: 0;
  margin-bottom: var(--mw-space-4);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
}

.hero {
  display: flex;
  align-items: center;
  gap: var(--mw-space-4);
}

.hero .mw-page__title,
.hero .mw-page__desc {
  margin: 0;
}

.hero .mw-page__desc {
  margin-top: 4px;
}

.hero__avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: var(--mw-brand);
  color: var(--mw-brand-ink);
  font-weight: 700;
  font-size: 22px;
  flex-shrink: 0;
}

.hero__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--mw-border);
  font-size: 14px;
}

.row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.row span {
  color: var(--mw-text-secondary);
  flex-shrink: 0;
}

.row strong {
  font-weight: 600;
  text-align: right;
}

.gallery {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.gallery img {
  width: 100%;
  height: 120px;
  object-fit: cover;
  border-radius: var(--mw-radius-md);
  border: 1px solid var(--mw-border);
}
</style>
