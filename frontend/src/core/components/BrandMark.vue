<script setup lang="ts">
import { computed } from 'vue'
import { BRAND, type BrandVariant } from '../brand'

const props = withDefaults(
  defineProps<{
    variant?: BrandVariant
    compact?: boolean
    showTagline?: boolean
  }>(),
  { variant: 'space', compact: false, showTagline: false },
)

const en = computed(() => BRAND[props.variant].toUpperCase())
const tagline = computed(() => BRAND.tagline[props.variant])
</script>

<template>
  <div class="brand-mark" :class="[`is-${variant}`, { 'is-compact': compact }]">
    <div class="word">
      <span class="cn">{{ BRAND.cn }}</span>
      <span class="en">{{ en }}</span>
    </div>
    <p v-if="showTagline" class="tag">{{ tagline }}</p>
    <div class="bars" aria-hidden="true">
      <span class="bar bar-orange" />
      <span class="bar bar-cyan" />
    </div>
  </div>
</template>

<style scoped>
/* 观野 VI：思源黑体 + Montserrat，橙长条 / 青短条 */
.brand-mark {
  --cn-size: 1.75rem;
  color: #f2e6d2;
  min-width: 0;
  padding: calc(var(--cn-size) * 0.35) 0;
}
.word {
  display: flex;
  align-items: flex-end;
  gap: calc(var(--cn-size) * 0.24);
  line-height: 1;
  white-space: nowrap;
}
.cn {
  font-family: 'Noto Sans SC', 'Source Han Sans SC', 'PingFang SC', sans-serif;
  font-size: var(--cn-size);
  font-weight: 700;
  letter-spacing: 0.035em;
}
.en {
  font-family: Montserrat, Arial, sans-serif;
  font-size: calc(var(--cn-size) * 0.86);
  font-weight: 800;
  letter-spacing: 0.018em;
  line-height: 1;
  padding-bottom: 0.04em;
}
.tag {
  margin: calc(var(--cn-size) * 0.28) 0 0;
  font-family: Montserrat, Arial, sans-serif;
  font-size: 0.58rem;
  font-weight: 600;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #f2e6d2;
  opacity: 0.78;
}
.bars {
  display: flex;
  align-items: flex-end;
  width: min(100%, 13.5em);
  margin-top: calc(var(--cn-size) * 0.22);
}
.bar-orange {
  width: 64%;
  height: 6px;
  background: #f36b21;
}
.bar-cyan {
  width: 36%;
  height: 3.8px;
  background: #14b8d4;
}
.is-compact {
  --cn-size: 1.12rem;
  padding: calc(var(--cn-size) * 0.2) 0;
}
.is-compact .bar-orange {
  height: 4px;
}
.is-compact .bar-cyan {
  height: 2.5px;
}
.is-compact .bars {
  width: 10.5em;
}
</style>
