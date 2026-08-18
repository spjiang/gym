<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps<{
  /** 出餐看板进行中的单量，用于角标 */
  queueCount?: number
}>()

const route = useRoute()
const router = useRouter()

const current = computed(() => (route.path.startsWith('/catering/kitchen') ? 'kitchen' : 'pos'))

function go(path: string) {
  if (route.path === path) return
  router.push(path)
}
</script>

<template>
  <div class="desk-switch" role="tablist" aria-label="吧台作业切换">
    <button
      type="button"
      class="card"
      :class="{ 'is-on': current === 'pos' }"
      role="tab"
      :aria-selected="current === 'pos'"
      @click="go('/catering/pos')"
    >
      <div class="card__kicker">下单收款</div>
      <div class="card__title">吧台点单</div>
      <div class="card__desc">{{ current === 'pos' ? '当前页面 · 选菜并收款' : '点击切换到点单' }}</div>
    </button>
    <button
      type="button"
      class="card"
      :class="{ 'is-on': current === 'kitchen' }"
      role="tab"
      :aria-selected="current === 'kitchen'"
      @click="go('/catering/kitchen')"
    >
      <div class="card__kicker">更新状态</div>
      <div class="card__title">
        出餐看板
        <span v-if="(props.queueCount || 0) > 0" class="badge">{{ props.queueCount }}</span>
      </div>
      <div class="card__desc">{{ current === 'kitchen' ? '当前页面 · 出餐并完成取餐' : '点击切换到出餐' }}</div>
    </button>
  </div>
</template>

<style scoped>
.desk-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  width: 100%;
  margin: 0 0 24px;
}
.card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 168px;
  padding: 28px 24px;
  border: 2px solid rgba(28, 25, 23, 0.1);
  border-radius: 20px;
  background: #fff;
  color: inherit;
  text-align: center;
  cursor: pointer;
  font: inherit;
  box-shadow: 0 4px 16px rgba(28, 25, 23, 0.06);
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
}
.card:hover {
  transform: translateY(-2px);
  border-color: rgba(243, 107, 33, 0.45);
  box-shadow: 0 12px 28px rgba(28, 25, 23, 0.1);
}
.card.is-on {
  background: linear-gradient(180deg, #fff4ea, #fff);
  border-color: #f36b21;
  box-shadow: 0 12px 28px rgba(243, 107, 33, 0.16);
  cursor: default;
}
.card__kicker {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--admin-copper, #a67c52);
}
.card.is-on .card__kicker {
  color: #f36b21;
}
.card__title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1.15;
  color: var(--admin-ink, #1c1917);
}
.card__desc {
  font-size: 15px;
  color: var(--admin-ink-muted, #78716c);
}
.badge {
  min-width: 26px;
  height: 26px;
  padding: 0 8px;
  border-radius: 999px;
  background: #f36b21;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  line-height: 26px;
  text-align: center;
}
@media (max-width: 720px) {
  .desk-switch {
    grid-template-columns: 1fr;
  }
  .card {
    min-height: 132px;
  }
  .card__title {
    font-size: 1.6rem;
  }
}
</style>
