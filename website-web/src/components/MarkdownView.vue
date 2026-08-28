<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = withDefaults(
  defineProps<{
    content: string
    emptyText?: string
  }>(),
  { emptyText: '内容筹备中' },
)

marked.setOptions({ breaks: true, gfm: true })

const html = computed(() => {
  const text = (props.content || '').trim()
  if (!text) return ''
  const raw = marked.parse(text, { async: false }) as string
  return DOMPurify.sanitize(raw)
})
</script>

<template>
  <div v-if="html" class="md" v-html="html" />
  <p v-else class="empty">{{ emptyText }}</p>
</template>

<style scoped>
.empty {
  color: var(--muted);
}
.md {
  line-height: 1.8;
  word-break: break-word;
}
.md :deep(a) {
  color: var(--orange);
}
.md :deep(p) {
  margin: 0.8em 0;
}
.md :deep(h2),
.md :deep(h3) {
  margin: 1.4em 0 0.5em;
}
.md :deep(ul),
.md :deep(ol) {
  margin: 0.6em 0 1em;
  padding-left: 1.3em;
}
.md :deep(li) {
  margin: 0.35em 0;
}
.md :deep(strong) {
  color: #f7eee0;
}
.md :deep(img) {
  border-radius: 8px;
  margin: 1em 0;
}
</style>
