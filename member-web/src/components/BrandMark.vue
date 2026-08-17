<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'space' | 'fit' | 'bar'
    compact?: boolean
    showTagline?: boolean
  }>(),
  { variant: 'space', compact: false, showTagline: false },
)

const EN: Record<string, string> = { space: 'SPACE', fit: 'FIT', bar: 'BAR' }
const TAG: Record<string, string> = {
  space: 'SPORTS · EVENTS · COMMUNITY',
  fit: 'TRAIN · RECOVER · BELONG',
  bar: 'NIGHTS · MUSIC · COMMUNITY',
}
</script>

<template>
  <div class="brand-mark" :class="[`is-${variant}`, { 'is-compact': compact }]">
    <div class="word">
      <span class="cn">观野</span>
      <span class="en">{{ EN[variant] }}</span>
    </div>
    <p v-if="showTagline" class="tag">{{ TAG[variant] }}</p>
    <div class="bars" aria-hidden="true">
      <span class="bar-orange" />
      <span class="bar-cyan" />
    </div>
  </div>
</template>

<style scoped>
.brand-mark {
  --cn-size: 1.7rem;
  color: #f2e6d2;
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
  font-family: 'Noto Sans SC', 'Source Han Sans SC', sans-serif;
  font-size: var(--cn-size);
  font-weight: 700;
  letter-spacing: 0.035em;
}
.en {
  font-family: Montserrat, Arial, sans-serif;
  font-size: calc(var(--cn-size) * 0.86);
  font-weight: 800;
  letter-spacing: 0.018em;
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
  width: 12.5em;
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
  --cn-size: 1.05rem;
  padding: calc(var(--cn-size) * 0.15) 0;
}
.is-compact .bar-orange {
  height: 4px;
}
.is-compact .bar-cyan {
  height: 2.5px;
}
.is-compact .bars {
  width: 9.5em;
}
</style>
