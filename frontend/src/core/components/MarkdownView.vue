<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = withDefaults(
  defineProps<{
    content: string
    emptyText?: string
  }>(),
  { emptyText: '暂无内容' },
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
  <div v-if="html" class="markdown-body" v-html="html" />
  <div v-else class="markdown-empty">{{ emptyText }}</div>
</template>

<style scoped>
.markdown-empty {
  color: var(--el-text-color-secondary);
  padding: 24px 0;
  text-align: center;
}
.markdown-body {
  font-size: 14px;
  line-height: 1.75;
  color: var(--el-text-color-primary);
  word-break: break-word;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 1.2em 0 0.6em;
  font-weight: 600;
  line-height: 1.35;
}
.markdown-body :deep(h1) {
  font-size: 1.5em;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding-bottom: 0.3em;
}
.markdown-body :deep(h2) {
  font-size: 1.25em;
}
.markdown-body :deep(h3) {
  font-size: 1.1em;
}
.markdown-body :deep(p) {
  margin: 0.75em 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.75em 0;
  padding-left: 1.5em;
}
.markdown-body :deep(li) {
  margin: 0.35em 0;
}
.markdown-body :deep(blockquote) {
  margin: 0.75em 0;
  padding: 0.5em 1em;
  border-left: 4px solid var(--el-color-primary);
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
}
.markdown-body :deep(code) {
  padding: 0.15em 0.35em;
  border-radius: 4px;
  background: var(--el-fill-color);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.9em;
}
.markdown-body :deep(pre) {
  margin: 0.75em 0;
  padding: 12px;
  overflow: auto;
  border-radius: 8px;
  background: var(--el-fill-color-dark);
}
.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
}
.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.75em 0;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--el-border-color-lighter);
  padding: 8px 10px;
}
.markdown-body :deep(th) {
  background: var(--el-fill-color-light);
}
.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--el-border-color-lighter);
  margin: 1.2em 0;
}
.markdown-body :deep(strong) {
  font-weight: 600;
}
</style>
