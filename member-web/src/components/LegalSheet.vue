<script setup lang="ts">
import { computed } from 'vue'
import { LEGAL_DOCS, type LegalDoc } from '../legal'
import { copyrightNotice } from '../copyright'

const props = defineProps<{
  doc: LegalDoc | null
}>()

const emit = defineEmits<{
  close: []
}>()

const current = computed(() => (props.doc ? LEGAL_DOCS[props.doc] : null))
</script>

<template>
  <div v-if="current" class="legal" role="dialog" :aria-label="current.title">
    <div class="legal__panel">
      <header class="legal__head">
        <strong>{{ current.title }}</strong>
        <button class="legal__close" type="button" @click="emit('close')">关闭</button>
      </header>
      <div class="legal__body" v-html="current.html" />
      <p class="legal__copy">{{ copyrightNotice() }}</p>
    </div>
  </div>
</template>

<style scoped>
.legal {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: var(--mw-bg);
  overflow: auto;
}

.legal__panel {
  width: min(680px, calc(100% - 40px));
  margin: 0 auto;
  padding: 28px 0 48px;
  color: var(--mw-text);
}

.legal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.legal__head strong {
  font-size: 20px;
}

.legal__close {
  min-height: 0;
  padding: 0;
  border: 0;
  background: none;
  color: var(--mw-text-secondary);
  font: inherit;
  font-size: 14px;
  font-weight: 400;
  cursor: pointer;
}

.legal__body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--mw-text);
}

.legal__body :deep(h2) {
  margin: 22px 0 8px;
  font-size: 15px;
  color: var(--mw-text);
}

.legal__body :deep(p) {
  margin: 0 0 10px;
  color: var(--mw-text-secondary);
}

.legal__copy {
  margin: 28px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--mw-text-tertiary);
}
</style>
