<script setup lang="ts">
import { computed, onMounted, ref, watch, type Component } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Bell,
  Calendar,
  Collection,
  CreditCard,
  DataAnalysis,
  Document,
  Expand,
  Fold,
  Food,
  Goods,
  Grid,
  House,
  List,
  Lock,
  Monitor,
  OfficeBuilding,
  Postcard,
  Setting,
  Share,
  ShoppingCart,
  Ticket,
  Tools,
  TrendCharts,
  User,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import {
  findMenuFromNav,
  firstAllowedPathFromNav,
  groupGymMenus,
  groupPlatformMenus,
  menusForSystemFromNav,
  merchantsWithSystem,
  type SystemId,
} from '../nav/systems'
import { useOpsStore } from '../stores/ops'
import { brandLabelForSystem, brandVariantForSystem } from '../brand'
import BrandMark from '../components/BrandMark.vue'
import { copyrightLine } from '../copyright'
import http from '../api/http'

const auth = useAuthStore()
const ops = useOpsStore()
const router = useRouter()
const route = useRoute()
const allMerchants = ref<{ id: number; name: string; subsystem_codes?: string[] }[]>([])

const scopedMerchants = computed(() => merchantsWithSystem(allMerchants.value, ops.subsystem))

async function loadMerchants() {
  try {
    const { data } = await http.get('/merchants')
    allMerchants.value = data
    if (ops.merchantId && !scopedMerchants.value.some((m) => m.id === ops.merchantId)) {
      ops.setMerchantId(null)
    }
  } catch {
    allMerchants.value = []
  }
}

watch(
  () => ops.subsystem,
  () => {
    if (ops.merchantId && !scopedMerchants.value.some((m) => m.id === ops.merchantId)) {
      ops.setMerchantId(null)
    }
  },
)

onMounted(loadMerchants)

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

const platformMenus = computed(() => menusForSystemFromNav(auth, 'platform'))
const platformGroups = computed(() => groupPlatformMenus(platformMenus.value))
const opsMenus = computed(() =>
  platformMenus.value.filter((m) => ['/ops', '/reports'].includes(m.path)),
)
const isPortal = computed(() => currentSystem.value === 'portal')
const isPlatform = computed(() => currentSystem.value === 'platform')
const isBusiness = computed(() => currentSystem.value === 'gym' || currentSystem.value === 'catering')
const businessMenus = computed(() =>
  isBusiness.value ? menusForSystemFromNav(auth, currentSystem.value) : [],
)
const gymGroups = computed(() => groupGymMenus(businessMenus.value))
const isGym = computed(() => currentSystem.value === 'gym')
const showMerchantFilter = computed(() => isBusiness.value)
const activeMenu = computed(() => route.path)

watch(
  () => currentSystem.value,
  (sys) => {
    if (sys === 'gym' || sys === 'catering') {
      if (ops.subsystem !== sys) ops.setSubsystem(sys)
    }
  },
)

const subsystems = computed(() => auth.navigation?.subsystems || [])

const pageTitle = computed(() => {
  if (isPortal.value) return '工作台'
  const hit = findMenuFromNav(auth, route.path)
  return hit?.name || systemMeta.value?.name || '工作台'
})

const eyebrow = computed(() => {
  if (isPortal.value) return '观野SPACE 综合管理平台'
  return systemMeta.value?.name || brandLabelForSystem(String(currentSystem.value))
})

const brandVariant = computed(() => brandVariantForSystem(isPortal.value ? 'platform' : String(currentSystem.value)))

const ASIDE_KEY = 'admin-aside-collapsed'
const asideCollapsed = ref(localStorage.getItem(ASIDE_KEY) === '1')
const asideWidth = computed(() => (asideCollapsed.value ? '72px' : '248px'))

function toggleAside() {
  asideCollapsed.value = !asideCollapsed.value
  localStorage.setItem(ASIDE_KEY, asideCollapsed.value ? '1' : '0')
}

function menuIcon(path: string): Component {
  const exact: Record<string, Component> = {
    '/ops': DataAnalysis,
    '/reports': TrendCharts,
    '/orders': Document,
    '/platform/payment-reconcile': Document,
    '/members': User,
    '/visits': Postcard,
    '/coupons/templates': Ticket,
    '/coupons/issue': Ticket,
    '/notifications': Bell,
    '/access': Monitor,
    '/merchants': OfficeBuilding,
    '/merchant-types': OfficeBuilding,
    '/platform/roles': Lock,
    '/staff': User,
    '/platform/site-profile': Setting,
    '/platform/subsystems': Setting,
    '/platform/payment-settings': Setting,
    '/platform/sms-settings': Setting,
    '/platform/agreements': Document,
    '/platform/commission-settings': TrendCharts,
    '/platform/audit-logs': List,
    '/platform/ai/prompt-templates': Document,
    '/platform/ai/llm-accounts': Setting,
    '/platform/ai/analysis': DataAnalysis,
    '/platform/ai/analysis-logs': List,
    '/platform/website/settings': Monitor,
    '/platform/website/home': Monitor,
    '/platform/website/brands': Monitor,
    '/platform/website/news': Document,
    '/platform/website/jobs': Document,
    '/platform/website/partners': Document,
    '/catering/categories': Collection,
    '/catering/menu': Food,
    '/catering/tables': Grid,
    '/catering/kitchen': Monitor,
    '/catering/pos': ShoppingCart,
    '/catering/orders': Collection,
    '/memberships': CreditCard,
    '/products': CreditCard,
    '/coaches': User,
    '/sales-reps': User,
    '/retail': Goods,
    '/equipment': Setting,
  }
  if (exact[path]) return exact[path]
  if (path.startsWith('/group-') || path.includes('coach-desk')) return Calendar
  if (path.startsWith('/pt-')) return User
  if (path.startsWith('/activit')) return Calendar
  if (path.includes('commission')) return TrendCharts
  if (path.startsWith('/retail')) return Goods
  if (path.startsWith('/equipment')) return Setting
  if (path.startsWith('/platform/website')) return Monitor
  if (path.startsWith('/platform/promotion') || path.startsWith('/rebate') || path.startsWith('/payout')) return Share
  return Collection
}

function groupIcon(key: string): Component {
  const map: Record<string, Component> = {
    ops: DataAnalysis,
    order: Document,
    member: User,
    visit: Postcard,
    coupon: Ticket,
    promoter: Share,
    notify: Bell,
    device: Monitor,
    merchant: OfficeBuilding,
    rbac: Lock,
    devops: Tools,
    base: Setting,
    website: Monitor,
    membership: CreditCard,
    group: Calendar,
    pt: User,
    activity: Calendar,
    commission: TrendCharts,
    coach: User,
    sales: User,
    retail: Goods,
    equipment: Setting,
  }
  return map[key] || Collection
}

function shortName(code: string, fallback: string) {
  return brandLabelForSystem(code) || fallback
}

function goPortal() {
  router.push({ name: 'portal' })
}

function openSystem(s: { code: string; entry_path: string | null; name: string }) {
  if (s.code === 'gym' || s.code === 'catering') {
    ops.setSubsystem(s.code)
  }
  router.push(firstAllowedPathFromNav(auth, s.code))
}

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <el-container class="layout">
    <el-aside :width="asideWidth" class="aside" :class="{ 'aside--collapsed': asideCollapsed }">
      <div class="brand">
        <BrandMark :variant="brandVariant" compact />
        <div class="brand-sub">{{ isPortal ? '综合管理平台' : systemMeta?.name }}</div>
      </div>

      <!-- 工作台：侧栏直接列出业务系统 -->
      <template v-if="isPortal">
        <button
          class="nav-item nav-item--home is-active"
          type="button"
          title="工作台"
          @click="goPortal"
        >
          <el-icon><House /></el-icon>
          <span v-show="!asideCollapsed">工作台</span>
        </button>

        <div v-show="!asideCollapsed" class="system-label">业务系统</div>
        <nav class="system-nav" aria-label="业务系统">
          <button
            v-for="s in subsystems"
            :key="s.code"
            type="button"
            class="nav-item"
            :title="shortName(s.code, s.name)"
            @click="openSystem(s)"
          >
            <span class="nav-dot" :data-system="s.code" aria-hidden="true" />
            <span v-show="!asideCollapsed" class="nav-text">
              <span class="nav-title">{{ shortName(s.code, s.name) }}</span>
              <span class="nav-desc">{{ s.is_business ? '业态' : '平台' }}</span>
            </span>
          </button>
          <p v-if="!subsystems.length" class="nav-empty">暂无可用系统</p>
        </nav>
      </template>

      <!-- 子系统内：返回工作台 + 二级功能菜单 -->
      <template v-else>
        <button class="portal-link" type="button" title="返回工作台" @click="goPortal">
          <el-icon><House /></el-icon>
          <span v-show="!asideCollapsed">工作台</span>
        </button>

        <div v-show="!asideCollapsed" class="system-label">{{ shortName(String(currentSystem), systemMeta?.name || '') }}</div>

        <el-menu
          v-if="isPlatform"
          router
          :default-active="activeMenu"
          :default-openeds="[]"
          :collapse="asideCollapsed"
          unique-opened
          class="side-menu"
          background-color="transparent"
          text-color="#c5cbc6"
          active-text-color="#f2e6d2"
        >
          <el-sub-menu v-if="opsMenus.length" index="ops">
            <template #title>
              <el-icon><component :is="groupIcon('ops')" /></el-icon>
              <span>经营管理</span>
            </template>
            <el-menu-item v-for="m in opsMenus" :key="m.path" :index="m.path">
              <el-icon><component :is="menuIcon(m.path)" /></el-icon>
              <span>{{ m.label }}</span>
            </el-menu-item>
          </el-sub-menu>
          <template v-for="g in platformGroups.groups" :key="g.key">
            <el-menu-item v-if="g.flat && g.items[0]" :index="g.items[0].path">
              <el-icon><component :is="menuIcon(g.items[0].path)" /></el-icon>
              <span>{{ g.label }}</span>
            </el-menu-item>
            <el-sub-menu v-else :index="g.key">
              <template #title>
                <el-icon><component :is="groupIcon(g.key)" /></el-icon>
                <span>{{ g.label }}</span>
              </template>
              <el-menu-item v-for="m in g.items" :key="m.path" :index="m.path">
                <el-icon><component :is="menuIcon(m.path)" /></el-icon>
                <span>{{ m.label }}</span>
              </el-menu-item>
            </el-sub-menu>
          </template>
          <el-menu-item v-for="m in platformGroups.leftover" :key="m.path" :index="m.path">
            <el-icon><component :is="menuIcon(m.path)" /></el-icon>
            <span>{{ m.label }}</span>
          </el-menu-item>
        </el-menu>

        <el-menu
          v-else-if="isGym"
          router
          :default-active="activeMenu"
          :default-openeds="[]"
          :collapse="asideCollapsed"
          unique-opened
          class="side-menu"
          background-color="transparent"
          text-color="#c5cbc6"
          active-text-color="#f2e6d2"
        >
          <template v-for="g in gymGroups.groups" :key="g.key">
            <el-menu-item v-if="g.flat && g.items[0]" :index="g.items[0].path">
              <el-icon><component :is="menuIcon(g.items[0].path)" /></el-icon>
              <span>{{ g.label }}</span>
            </el-menu-item>
            <el-sub-menu v-else :index="g.key">
              <template #title>
                <el-icon><component :is="groupIcon(g.key)" /></el-icon>
                <span>{{ g.label }}</span>
              </template>
              <el-menu-item v-for="m in g.items" :key="m.path" :index="m.path">
                <el-icon><component :is="menuIcon(m.path)" /></el-icon>
                <span>{{ m.label }}</span>
              </el-menu-item>
            </el-sub-menu>
          </template>
          <el-menu-item v-for="m in gymGroups.leftover" :key="m.path" :index="m.path">
            <el-icon><component :is="menuIcon(m.path)" /></el-icon>
            <span>{{ m.label }}</span>
          </el-menu-item>
        </el-menu>

        <el-menu
          v-else
          router
          :default-active="activeMenu"
          :default-openeds="[]"
          :collapse="asideCollapsed"
          unique-opened
          class="side-menu"
          background-color="transparent"
          text-color="#c5cbc6"
          active-text-color="#f2e6d2"
        >
          <el-menu-item v-for="m in businessMenus" :key="m.path" :index="m.path">
            <el-icon><component :is="menuIcon(m.path)" /></el-icon>
            <span>{{ m.label }}</span>
          </el-menu-item>
        </el-menu>
      </template>
      <p v-show="!asideCollapsed" class="aside-copy">{{ copyrightLine() }}</p>
    </el-aside>

    <el-container class="workspace">
      <el-header class="header" height="auto">
        <div class="header-left">
          <button
            class="aside-toggle"
            type="button"
            :title="asideCollapsed ? '展开菜单' : '收起菜单'"
            @click="toggleAside"
          >
            <el-icon :size="18">
              <Expand v-if="asideCollapsed" />
              <Fold v-else />
            </el-icon>
          </button>
          <div class="header-titles">
            <div class="eyebrow">{{ eyebrow }}</div>
            <h1 class="page-title">{{ pageTitle }}</h1>
          </div>
          <div v-if="showMerchantFilter" class="ops-filter">
            <el-select
              :model-value="ops.merchantId ?? undefined"
              clearable
              placeholder="全部商户"
              style="width: 200px"
              @change="(v: number | undefined) => ops.setMerchantId(v ?? null)"
            >
              <el-option v-for="m in scopedMerchants" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </div>
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
        <p class="page-copy">{{ copyrightLine() }}</p>
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
  background: #171b1f;
  color: #f2e6d2;
  border-right: 1px solid rgba(242, 230, 210, 0.06);
  position: relative;
  overflow-x: hidden;
  overflow-y: auto;
  transition: width 0.22s ease;
  display: flex;
  flex-direction: column;
}

.aside--collapsed :deep(.brand-mark .word),
.aside--collapsed :deep(.brand-mark .tag) {
  display: none;
}
.aside--collapsed :deep(.brand-mark .bars) {
  width: 36px;
  margin: 0 auto;
}
.aside--collapsed .brand {
  align-items: center;
  padding: 18px 10px 8px;
}
.aside--collapsed .brand-sub {
  display: none;
}
.aside--collapsed .nav-item {
  justify-content: center;
  padding: 11px 0;
}
.aside--collapsed .nav-item--home,
.aside--collapsed .portal-link {
  margin-left: 8px;
  margin-right: 8px;
  width: calc(100% - 16px);
  justify-content: center;
}
.aside--collapsed .side-menu {
  padding-left: 4px;
  padding-right: 4px;
  width: 100%;
}
.aside--collapsed .side-menu :deep(.el-menu) {
  background: transparent;
}

.brand {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 24px 22px 10px;
  position: relative;
  z-index: 1;
}

.brand-sub {
  margin-top: 6px;
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
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.portal-link:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #f2e6d2;
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
  color: #f2e6d2;
}

.nav-item.is-active,
.nav-item--home.is-active {
  background: rgba(243, 107, 33, 0.22);
  color: #f2e6d2;
  box-shadow: inset 3px 0 0 #f26a21;
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
  background: #1ec8c3;
}

.nav-dot[data-system='gym'] {
  background: #f26a21;
}

.nav-dot[data-system='catering'] {
  background: #1ec8c3;
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

.side-menu :deep(.el-icon) {
  font-size: 18px;
  color: inherit;
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
  color: #f2e6d2 !important;
}

.side-menu :deep(.el-menu-item.is-active) {
  background: rgba(243, 107, 33, 0.22) !important;
  color: #f2e6d2 !important;
  box-shadow: inset 3px 0 0 #f26a21;
  font-weight: 600;
}

.workspace {
  min-width: 0;
  overflow: hidden;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  height: auto !important;
  min-height: 72px;
  padding: 12px 28px;
  box-sizing: border-box;
  overflow: hidden;
  background: rgba(251, 248, 243, 0.72);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(28, 25, 23, 0.06);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
  flex: 1;
}

.aside-toggle {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(28, 25, 23, 0.1);
  background: rgba(255, 255, 255, 0.72);
  color: var(--admin-ink-muted);
  border-radius: 10px;
  display: grid;
  place-items: center;
  cursor: pointer;
}

.aside-toggle:hover {
  color: var(--admin-ink);
  border-color: rgba(243, 107, 33, 0.35);
  background: #fff;
}

.header-titles {
  min-width: 0;
}

.eyebrow {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  line-height: 1.2;
  color: var(--admin-copper);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.page-title {
  margin: 2px 0 0;
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.3;
  color: var(--admin-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ops-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.side-menu :deep(.el-sub-menu__title) {
  height: 44px;
  line-height: 44px;
  margin: 3px 0;
  border-radius: 12px;
  color: #c5cbc6 !important;
}

.side-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.05) !important;
  color: #f2e6d2 !important;
}

.side-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: #f2e6d2 !important;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-shrink: 0;
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
  background: #f36b21;
  color: #f2e6d2;
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

.aside-copy {
  margin: auto 16px 20px;
  padding-top: 16px;
  font-size: 0.68rem;
  line-height: 1.5;
  color: rgba(197, 203, 198, 0.45);
}

.page-copy {
  margin: 16px 4px 0;
  text-align: center;
  font-size: 0.75rem;
  color: var(--admin-ink-muted);
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
  .aside:not(.aside--collapsed) {
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
