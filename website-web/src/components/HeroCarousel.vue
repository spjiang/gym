<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { mediaSrc } from '../lib/media'

const props = defineProps<{
  urls: string[]
}>()

const slides = computed(() => {
  const seen = new Set<string>()
  const list: string[] = []
  for (const raw of props.urls) {
    const src = mediaSrc(raw)
    if (!src || seen.has(src)) continue
    seen.add(src)
    list.push(src)
  }
  return list
})

const index = ref(0)
const paused = ref(false)
let timer: number | null = null

function go(next: number) {
  const n = slides.value.length
  if (!n) return
  index.value = (next + n) % n
}

function start() {
  stop()
  if (slides.value.length < 2) return
  timer = window.setInterval(() => {
    if (!paused.value) go(index.value + 1)
  }, 5600)
}

function stop() {
  if (timer != null) {
    window.clearInterval(timer)
    timer = null
  }
}

watch(slides, () => {
  index.value = 0
  start()
})

onMounted(start)
onUnmounted(stop)
</script>

<template>
  <div
    class="carousel"
    @mouseenter="paused = true"
    @mouseleave="paused = false"
  >
    <div v-if="!slides.length" class="fallback" />
    <template v-else>
      <figure v-for="(src, i) in slides" :key="src" class="slide" :class="{ 'is-on': i === index }">
        <img class="photo" :src="src" alt="" />
      </figure>
      <button v-if="slides.length > 1" class="nav prev" type="button" aria-label="上一张" @click="go(index - 1)">
        ‹
      </button>
      <button v-if="slides.length > 1" class="nav next" type="button" aria-label="下一张" @click="go(index + 1)">
        ›
      </button>
      <ol v-if="slides.length > 1" class="dots">
        <li v-for="(_, i) in slides" :key="i">
          <button type="button" :class="{ 'is-on': i === index }" :aria-label="`第 ${i + 1} 张`" @click="go(i)" />
        </li>
      </ol>
    </template>
  </div>
</template>

<style scoped>
.carousel {
  position: relative;
  width: 100%;
  height: 100vh;
  min-height: 100vh;
  background: #050607;
  overflow: hidden;
}
.slide,
.fallback {
  position: absolute;
  inset: 0;
  margin: 0;
}
.slide {
  opacity: 0;
  transition: opacity 0.8s ease;
  pointer-events: none;
}
.slide.is-on {
  opacity: 1;
  pointer-events: auto;
}
.photo {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}
.fallback {
  background:
    radial-gradient(ellipse at 30% 20%, rgba(243, 107, 33, 0.18), transparent 42%),
    radial-gradient(ellipse at 80% 70%, rgba(20, 184, 212, 0.12), transparent 40%),
    #12151a;
}
.nav {
  position: absolute;
  top: 50%;
  z-index: 3;
  transform: translateY(-50%);
  width: 48px;
  height: 48px;
  border: 0;
  border-radius: 50%;
  background: rgba(8, 9, 11, 0.45);
  color: #f2e6d2;
  font-size: 28px;
  line-height: 1;
}
.prev {
  left: 16px;
}
.next {
  right: 16px;
}
.dots {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 20px;
  z-index: 5;
  display: flex;
  justify-content: center;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.dots button {
  width: 8px;
  height: 8px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(242, 230, 210, 0.35);
}
.dots button.is-on {
  background: var(--orange);
  width: 22px;
  border-radius: 999px;
}
@media (max-width: 720px) {
  .carousel {
    height: 100svh;
    min-height: 100svh;
  }
  .nav {
    width: 40px;
    height: 40px;
  }
}
</style>
