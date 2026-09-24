<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'space' | 'fit' | 'bar'
    compact?: boolean
  }>(),
  { variant: 'space', compact: false },
)

const EN: Record<string, string> = { space: 'SPACE', fit: 'FIT', bar: 'BAR' }
</script>

<template>
  <div class="brand-mark" :class="[`is-${variant}`, { 'is-compact': compact }]">
    <div class="word">
      <span class="cn">观野</span>
      <span class="en">{{ EN[variant] }}</span>
    </div>
    <div class="bars" aria-hidden="true">
      <span class="bar-orange" />
      <span class="bar-cyan" />
    </div>
  </div>
</template>

<style scoped>
.brand-mark {
  --cn-size: 1.35rem;
  color: #f2e6d2;
}
.word {
  display: flex;
  align-items: flex-end;
  gap: 0.3em;
  line-height: 1;
  white-space: nowrap;
}
.cn {
  font-family: 'Noto Sans SC', sans-serif;
  font-size: var(--cn-size);
  font-weight: 700;
}
.en {
  font-family: Montserrat, Arial, sans-serif;
  font-size: calc(var(--cn-size) * 0.86);
  font-weight: 800;
}
.bars {
  display: flex;
  align-items: flex-end;
  width: 10em;
  margin-top: 0.28em;
}
.bar-orange {
  width: 64%;
  height: 5px;
  background: #f36b21;
}
.bar-cyan {
  width: 36%;
  height: 3px;
  background: #14b8d4;
}
.is-compact {
  --cn-size: 1rem;
}
</style>
