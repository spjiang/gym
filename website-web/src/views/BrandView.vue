<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import MarkdownView from '../components/MarkdownView.vue'
import { mediaSrc } from '../lib/media'
import { useSiteStore } from '../stores/site'
import type { BrandKey } from '../api/types'

const props = defineProps<{ brandKey: BrandKey }>()
const site = useSiteStore()
const brand = computed(() => site.data?.brands[props.brandKey])
const others = computed(() => {
  if (!site.data) return []
  return (['space', 'fit', 'bar'] as BrandKey[])
    .filter((k) => k !== props.brandKey)
    .map((k) => site.data!.brands[k])
})
</script>

<template>
  <article class="page">
    <header class="head">
      <figure class="hero-shot">
        <img v-if="brand?.cover_image_url" :src="mediaSrc(brand.cover_image_url)" alt="" />
      </figure>
      <div class="head-copy">
        <p class="kicker">{{ brand?.key.toUpperCase() }}</p>
        <h1>{{ brand?.title }}</h1>
      </div>
    </header>
    <div class="body">
      <MarkdownView :content="brand?.body || ''" />
      <a v-if="brand?.cta_label && brand.cta_url" class="btn" :href="brand.cta_url" target="_blank" rel="noreferrer">
        {{ brand.cta_label }}
      </a>
      <div v-if="brand?.gallery_image_urls.length" class="gallery">
        <img v-for="url in brand.gallery_image_urls" :key="url" :src="mediaSrc(url)" alt="" />
      </div>
      <div v-if="others.length" class="others">
        <h2>园里还有</h2>
        <div class="row">
          <RouterLink v-for="b in others" :key="b.key" class="mini" :to="`/${b.key}`">
            <img v-if="b.cover_image_url" :src="mediaSrc(b.cover_image_url)" alt="" />
            <span>{{ b.title }}</span>
          </RouterLink>
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.head {
  background: #08090b;
}
.hero-shot {
  margin: 0;
  display: flex;
  justify-content: center;
  background: #050607;
}
.hero-shot img {
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: min(88vh, 920px);
  object-fit: contain;
}
.head-copy {
  padding: 36px clamp(20px, 4vw, 40px) 8px;
  max-width: 920px;
}
.kicker {
  margin: 0 0 8px;
  letter-spacing: 0.2em;
  color: var(--cyan);
  font-size: 12px;
}
h1 {
  margin: 0;
  font-size: clamp(28px, 4vw, 46px);
}
.body {
  max-width: 840px;
  margin: 0 auto;
  padding: 36px 28px 72px;
}
.btn {
  display: inline-block;
  margin-top: 24px;
  background: var(--orange);
  color: #171b1f;
  padding: 10px 18px;
  border-radius: 999px;
  font-weight: 600;
}
.gallery {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 36px;
}
.gallery img {
  width: 100%;
  height: auto;
  object-fit: contain;
  background: #050607;
}
.others {
  margin-top: 48px;
}
.others h2 {
  margin: 0 0 16px;
  font-size: 18px;
}
.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.mini {
  border: 1px solid var(--line);
  overflow: hidden;
  background: var(--bg-2);
}
.mini img {
  width: 100%;
  height: auto;
  object-fit: contain;
  background: #050607;
}
.mini span {
  display: block;
  padding: 10px 12px;
}
@media (max-width: 700px) {
  .gallery,
  .row {
    grid-template-columns: 1fr;
  }
  .gallery img {
    height: auto;
  }
}
</style>
