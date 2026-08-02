<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  findMenu,
  menusForSystem,
  subsystems,
  type SystemId,
} from '../nav/systems'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const currentSystem = computed<SystemId | 'portal'>(() => {
  if (route.path === '/portal' || route.name === 'portal') return 'portal'
  const fromMeta = route.meta.system as SystemId | undefined
  if (fromMeta) return fromMeta
  return findMenu(route.path)?.system || 'platform'
})

const systemMeta = computed(() => subsystems.find((s) => s.id === currentSystem.value))

const menus = computed(() => {
  if (currentSystem.value === 'portal') return []
  return menusForSystem(currentSystem.value, auth.me?.permissions || [])
})

const pageTitle = computed(() => {
  if (currentSystem.value === 'portal') return '子系统入口'
  return findMenu(route.path)?.label || systemMeta.value?.shortName || '工作台'
})

const eyebrow = computed(() => {
  if (currentSystem.value === 'portal') return '综合经营管理系统'
  return systemMeta.value?.name || '运营工作台'
})

function goPortal() {
  router.push({ name: 'portal' })
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
          <div class="brand-sub">
            {{ currentSystem === 'portal' ? '综合经营管理系统' : systemMeta?.shortName }}
          </div>
        </div>
      </div>

      <button class="portal-link" type="button" @click="goPortal">
        ← 子系统入口
      </button>

      <div v-if="currentSystem !== 'portal'" class="system-label">{{ systemMeta?.name }}</div>

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

      <div v-else class="aside-hint">
        请选择子系统进入对应业务模块。综合经营负责组织、权限与整体数据；健身能力在健身管理平台。
      </div>
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
      <el-main class="main">
        <div class="main-panel">
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
  margin: 4px 20px 8px;
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: rgba(166, 124, 82, 0.95);
  font-weight: 700;
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

.aside-hint {
  position: relative;
  z-index: 1;
  margin: 8px 18px 24px;
  padding: 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(197, 203, 198, 0.78);
  font-size: 0.8rem;
  line-height: 1.55;
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

.main-panel {
  min-height: calc(100vh - 130px);
  padding: 22px;
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 252, 248, 0.92), rgba(251, 248, 243, 0.88));
  border: 1px solid rgba(28, 25, 23, 0.06);
  box-shadow: var(--admin-shadow);
  animation: panel-in 0.45s ease both;
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
