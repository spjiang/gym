<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { canAny, firstAllowedPath, visibleSubsystems, type Subsystem } from '../nav/systems'

const auth = useAuthStore()
const router = useRouter()

const cards = computed(() => visibleSubsystems(auth.me?.permissions || []))

function openSystem(s: Subsystem) {
  const path = firstAllowedPath(auth.me?.permissions || [], s.id)
  router.push(path)
}

function canOpen(s: Subsystem) {
  return canAny(auth.me?.permissions || [], s.anyOf)
}
</script>

<template>
  <div class="portal">
    <header class="hero">
      <p class="eyebrow">Subsystem Portal</p>
      <h2>综合经营管理系统</h2>
      <p class="lead">
        这里是场地级入口：配置子系统、管理组织与权限、主档与整体运营数据。业态能力请进入对应子系统。
      </p>
    </header>

    <div class="grid">
      <button
        v-for="s in cards"
        :key="s.id"
        class="card"
        type="button"
        :disabled="!canOpen(s)"
        @click="openSystem(s)"
      >
        <div class="card-top">
          <span class="badge" :data-system="s.id">{{ s.shortName }}</span>
          <span class="arrow">进入 →</span>
        </div>
        <h3>{{ s.name }}</h3>
        <p>{{ s.description }}</p>
      </button>
    </div>

    <p v-if="!cards.length" class="empty">当前账号暂无可用子系统，请联系管理员分配权限。</p>
  </div>
</template>

<style scoped>
.portal {
  max-width: 920px;
}

.hero {
  margin-bottom: 28px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--admin-copper);
  font-weight: 600;
}

h2 {
  margin: 0;
  font-size: 1.75rem;
  letter-spacing: -0.03em;
}

.lead {
  margin-top: 10px;
  max-width: 48ch;
  line-height: 1.6;
  color: var(--admin-ink-muted);
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.card {
  text-align: left;
  border: 1px solid rgba(28, 25, 23, 0.08);
  border-radius: 18px;
  padding: 22px 20px;
  background: linear-gradient(165deg, #fffcf8 0%, #f3eee5 100%);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  font: inherit;
  color: inherit;
}

.card:hover:not(:disabled) {
  transform: translateY(-3px);
  border-color: rgba(61, 107, 92, 0.35);
  box-shadow: 0 18px 40px -28px rgba(28, 25, 23, 0.45);
}

.card:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.badge {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--admin-accent-soft);
  color: var(--admin-accent-strong);
}

.badge[data-system='gym'] {
  background: rgba(166, 124, 82, 0.16);
  color: #7a5634;
}

.arrow {
  font-size: 0.82rem;
  color: var(--admin-ink-muted);
  font-weight: 600;
}

.card h3 {
  margin: 0 0 8px;
  font-size: 1.15rem;
}

.card p {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.55;
  color: var(--admin-ink-muted);
}

.empty {
  margin-top: 24px;
  color: var(--admin-ink-muted);
}

@media (max-width: 720px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
