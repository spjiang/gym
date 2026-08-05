<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  findMenuFromNav,
  firstAllowedPathFromNav,
  menusForSystemFromNav,
  type SystemId,
} from '../nav/systems'

/** 侧栏展示用短名，避免长标题挤占 */
const SYSTEM_SHORT: Record<string, string> = {
  platform: '综合经营',
  gym: '健身管理',
  catering: '餐饮管理',
}

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const currentSystem = computed<SystemId | 'portal'>(() => {
  if (route.path === '/portal' || route.name === 'portal') return 'portal'
  const fromMeta = route.meta.system as SystemId | undefined
  if (fromMeta) return fromMeta
  const hit = findMenuFromNav(auth, route.path)
  return (hit?.subsystem_code as SystemId) || 'platform'
})

const systemMeta = computed(() => {
  const code = currentSystem.value
  if (code === 'portal') return null
  return auth.navigation?.subsystems.find((s) => s.code === code) || null
})

const menus = computed(() => {
  if (currentSystem.value === 'portal') return []
  return menusForSystemFromNav(auth, currentSystem.value)
})

const isPortal = computed(() => currentSystem.value === 'portal')

const subsystems = computed(() => auth.navigation?.subsystems || [])

const pageTitle = computed(() => {
  if (isPortal.value) return '工作台'
  const hit = findMenuFromNav(auth, route.path)
  return hit?.name || systemMeta.value?.name || '工作台'
})

const eyebrow = computed(() => {
  if (isPortal.value) return '回龙观公园综合场地'
  return systemMeta.value?.name || '运营工作台'
})

function shortName(code: string, fallback: string) {
  return SYSTEM_SHORT[code] || fallback
}

function goPortal() {
  router.push({ name: 'portal' })
}

function openSystem(s: { code: string; entry_path: string | null; name: string }) {
  if (s.entry_path) router.push(s.entry_path)
  else router.push(firstAllowedPathFromNav(auth, s.code))
}

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="248px" class="aside">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true" />
        <div>
          <div class="brand-name">回龙观场地</div>
          <div class="brand-sub">{{ isPortal ? '运营工作台' : systemMeta?.name }}</div>
        </div>
      </div>

      <!-- 工作台：侧栏直接列出业务系统 -->
      <template v-if="isPortal">
        <button
          class="nav-item nav-item--home is-active"
          type="button"
          @click="goPortal"
        >
          工作台
        </button>

        <div class="system-label">业务系统</div>
        <nav class="system-nav" aria-label="业务系统">
          <button
            v-for="s in subsystems"
            :key="s.code"
            type="button"
            class="nav-item"
            @click="openSystem(s)"
          >
            <span class="nav-dot" :data-system="s.code" aria-hidden="true" />
            <span class="nav-text">
              <span class="nav-title">{{ shortName(s.code, s.name) }}</span>
              <span class="nav-desc">{{ s.is_business ? '业态' : '公共' }}</span>
            </span>
          </button>
          <p v-if="!subsystems.length" class="nav-empty">暂无可用系统</p>
        </nav>
      </template>

      <!-- 子系统内：返回工作台 + 功能菜单 -->
      <template v-else>
        <button class="portal-link" type="button" @click="goPortal">← 工作台</button>

        <div class="system-label">{{ shortName(currentSystem, systemMeta?.name || '') }}</div>

        <el-menu
          v-if="menus.length"
          router
          :default-active="$route.path"
          class="side-menu"
          background-color="transparent"
          text-color="#c5cbc6"
          active-text-color="#f5f0e8"
        >
          <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
            <span>{{ m.label }}</span>
          </el-menu-item>
        </el-menu>
      </template>
    </el-aside>

    <el-container class="workspace">
      <el-header class="header" height="72px">
        <div class="header-left">
          <div class="eyebrow">{{ eyebrow }}</div>
          <h1 class="page-title">{{ pageTitle }}</h1>
        </div>
        <div class="header-right">
          <div class="user-chip">
            <div class="avatar">{{ auth.me?.display_name?.slice(0, 1) || '管' }}</div>
            <div class="user-meta">
              <div class="user-name">{{ auth.me?.display_name }}</div>
              <div class="user-roles">{{ auth.me?.role_codes.join(' · ') }}</div>
            </div>
          </div>
          <el-button class="logout-btn" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main" :class="{ 'main--portal': isPortal }">
        <div class="main-panel" :class="{ 'main-panel--portal': isPortal }">
          <router-view />
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  background: transparent;
}

.aside {
  background:
    linear-gradient(180deg, rgba(61, 107, 92, 0.18) 0%, transparent 28%),
    linear-gradient(165deg, #171c19 0%, #101412 55%, #0c0f0d 100%);
  color: #fff;
  border-right: 1px solid rgba(255, 255, 255, 0.04);
  position: relative;
  overflow: hidden;
}

.aside::after {
  content: '';
  position: absolute;
  inset: auto -40% -20% auto;
  width: 280px;
  height: 280px;
  background: radial-gradient(circle, rgba(166, 124, 82, 0.18), transparent 68%);
  pointer-events: none;
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 28px 22px 12px;
  position: relative;
  z-index: 1;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: linear-gradient(145deg, #a67c52 0%, #3d6b5c 70%), #3d6b5c;
  box-shadow: 0 10px 24px -12px rgba(166, 124, 82, 0.8);
  flex-shrink: 0;
}

.brand-name {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #f7f3ec;
}

.brand-sub {
  margin-top: 2px;
  font-size: 0.72rem;
  color: rgba(197, 203, 198, 0.72);
  letter-spacing: 0.04em;
}

.portal-link {
  position: relative;
  z-index: 1;
  margin: 4px 16px 10px;
  width: calc(100% - 32px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  color: #d7ddd8;
  border-radius: 12px;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  font: inherit;
  font-size: 0.84rem;
  font-weight: 600;
}

.portal-link:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #f5f0e8;
}

.system-label {
  position: relative;
  z-index: 1;
  margin: 8px 20px 8px;
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: rgba(166, 124, 82, 0.95);
  font-weight: 700;
}

.system-nav {
  position: relative;
  z-index: 1;
  padding: 0 12px 28px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  border: none;
  background: transparent;
  color: #c5cbc6;
  border-radius: 12px;
  padding: 11px 12px;
  text-align: left;
  cursor: pointer;
  font: inherit;
  transition: background 0.2s ease, color 0.2s ease;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #f5f0e8;
}

.nav-item.is-active,
.nav-item--home.is-active {
  background: linear-gradient(90deg, rgba(61, 107, 92, 0.45), rgba(61, 107, 92, 0.12));
  color: #f5f0e8;
  box-shadow: inset 3px 0 0 #a67c52;
  font-weight: 600;
}

.nav-item--home {
  margin: 4px 16px 4px;
  width: calc(100% - 32px);
  font-weight: 600;
  font-size: 0.9rem;
}

.nav-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #3d6b5c;
}

.nav-dot[data-system='gym'] {
  background: #a67c52;
}

.nav-dot[data-system='catering'] {
  background: #7a8f6e;
}

.nav-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.nav-title {
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.2;
}

.nav-desc {
  font-size: 0.68rem;
  color: rgba(197, 203, 198, 0.55);
  letter-spacing: 0.04em;
}

.nav-empty {
  margin: 8px 8px 0;
  font-size: 0.78rem;
  color: rgba(197, 203, 198, 0.5);
}

.side-menu {
  border-right: none !important;
  padding: 4px 12px 28px;
  position: relative;
  z-index: 1;
}

.side-menu :deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 3px 0;
  border-radius: 12px;
  color: #c5cbc6 !important;
  transition: background 0.2s ease, color 0.2s ease;
}

.side-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.05) !important;
  color: #f5f0e8 !important;
}

.side-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(61, 107, 92, 0.45), rgba(61, 107, 92, 0.12)) !important;
  color: #f5f0e8 !important;
  box-shadow: inset 3px 0 0 #a67c52;
  font-weight: 600;
}

.workspace {
  min-width: 0;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 28px;
  background: rgba(251, 248, 243, 0.72);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(28, 25, 23, 0.06);
}

.eyebrow {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  color: var(--admin-copper);
  font-weight: 600;
}

.page-title {
  margin: 2px 0 0;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--admin-ink);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px 8px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(28, 25, 23, 0.06);
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, #3d6b5c, #2f5549);
  color: #f7f3ec;
  font-weight: 700;
  font-size: 0.85rem;
}

.user-name {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--admin-ink);
  line-height: 1.2;
}

.user-roles {
  font-size: 0.72rem;
  color: var(--admin-ink-muted);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-btn {
  border-radius: 999px;
  border-color: rgba(28, 25, 23, 0.12);
  background: transparent;
  color: var(--admin-ink-muted);
}

.logout-btn:hover {
  color: var(--admin-danger);
  border-color: rgba(180, 35, 24, 0.25);
  background: rgba(180, 35, 24, 0.04);
}

.main {
  padding: 22px 28px 36px;
}

.main--portal {
  padding-top: 18px;
}

.main-panel {
  min-height: calc(100vh - 130px);
  padding: 22px;
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 252, 248, 0.92), rgba(251, 248, 243, 0.88));
  border: 1px solid rgba(28, 25, 23, 0.06);
  box-shadow: var(--admin-shadow);
  animation: panel-in 0.45s ease both;
}

.main-panel--portal {
  padding: 8px 4px 12px;
  background: transparent;
  border: none;
  box-shadow: none;
}

@keyframes panel-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 960px) {
  .aside {
    width: 200px !important;
  }
  .header,
  .main {
    padding-left: 16px;
    padding-right: 16px;
  }
  .user-roles {
    display: none;
  }
}
</style>
