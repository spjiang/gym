<script setup lang="ts">
defineProps<{
  qty: number
  min?: number
}>()

const emit = defineEmits<{
  add: []
  sub: []
}>()
</script>

<template>
  <div class="qty" @click.stop>
    <button
      type="button"
      class="qty__btn"
      :disabled="qty <= (min ?? 0)"
      aria-label="减少"
      @click="emit('sub')"
    >
      −
    </button>
    <span class="qty__n">{{ qty }}</span>
    <button type="button" class="qty__btn qty__btn--plus" aria-label="增加" @click="emit('add')">+</button>
  </div>
</template>

<style scoped>
.qty {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.qty__n {
  min-width: 1.2em;
  text-align: center;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.qty__btn {
  width: 28px;
  height: 28px;
  min-height: 28px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid var(--mw-border);
  background: var(--mw-surface);
  color: var(--mw-text);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
}

.qty__btn--plus {
  background: var(--mw-brand);
  border-color: var(--mw-brand);
  color: var(--mw-brand-ink);
}

.qty__btn:disabled {
  opacity: 0.35;
}
</style>
