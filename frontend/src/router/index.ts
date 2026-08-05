import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '../core/stores/auth'
import { canAny, firstAllowedPathFromNav } from '../core/nav/systems'
import LoginView from '../core/views/LoginView.vue'
import LayoutView from '../core/views/LayoutView.vue'
import PortalView from '../core/views/PortalView.vue'
import MerchantsView from '../systems/platform/views/MerchantsView.vue'
import StaffView from '../systems/platform/views/StaffView.vue'
import MembersView from '../systems/platform/views/MembersView.vue'
import AccessView from '../systems/platform/views/AccessView.vue'
import OrdersView from '../systems/platform/views/OrdersView.vue'
import ReportsView from '../systems/platform/views/ReportsView.vue'
import VisitsView from '../systems/platform/views/VisitsView.vue'
import NotificationsView from '../systems/platform/views/NotificationsView.vue'
import SubsystemsView from '../systems/platform/views/SubsystemsView.vue'
import RolesView from '../systems/platform/views/RolesView.vue'
import ProductsView from '../systems/gym/views/ProductsView.vue'
import MembershipsView from '../systems/gym/views/MembershipsView.vue'
import CoachesView from '../systems/gym/views/CoachesView.vue'
import PtPackagesView from '../systems/gym/views/PtPackagesView.vue'
import GroupCoursesView from '../systems/gym/views/GroupCoursesView.vue'
import CoachDeskView from '../systems/gym/views/CoachDeskView.vue'
import RetailView from '../systems/gym/views/RetailView.vue'
import CouponsView from '../systems/gym/views/CouponsView.vue'
import EquipmentView from '../systems/gym/views/EquipmentView.vue'
import CateringMenuView from '../systems/catering/views/CateringMenuView.vue'
import CateringOrdersView from '../systems/catering/views/CateringOrdersView.vue'

const children: RouteRecordRaw[] = [
  { path: '', redirect: '/portal' },
  { path: 'portal', name: 'portal', component: PortalView, meta: { system: 'portal' } },
  {
    path: 'platform/subsystems',
    name: 'platform-subsystems',
    component: SubsystemsView,
    meta: { system: 'platform', anyOf: ['rbac:manage', '*'] },
  },
  {
    path: 'platform/roles',
    name: 'platform-roles',
    component: RolesView,
    meta: { system: 'platform', anyOf: ['rbac:manage', 'staff:manage', '*'] },
  },
  { path: 'merchants', name: 'merchants', component: MerchantsView, meta: { system: 'platform', anyOf: ['org:read', '*'] } },
  { path: 'staff', name: 'staff', component: StaffView, meta: { system: 'platform', anyOf: ['staff:manage', '*'] } },
  { path: 'members', name: 'members', component: MembersView, meta: { system: 'platform', anyOf: ['member:read', '*'] } },
  { path: 'access', name: 'access', component: AccessView, meta: { system: 'platform', anyOf: ['access:read', '*'] } },
  {
    path: 'visits',
    name: 'visits',
    component: VisitsView,
    meta: { system: 'platform', anyOf: ['access:manage', 'access:read', '*'] },
  },
  { path: 'orders', name: 'orders', component: OrdersView, meta: { system: 'platform', anyOf: ['order:read', '*'] } },
  { path: 'reports', name: 'reports', component: ReportsView, meta: { system: 'platform', anyOf: ['report:read', '*'] } },
  {
    path: 'notifications',
    name: 'notifications',
    component: NotificationsView,
    meta: { system: 'platform', anyOf: ['order:read', 'member:read', 'access:read', '*'] },
  },
  {
    path: 'products',
    name: 'products',
    component: ProductsView,
    meta: { system: 'gym', anyOf: ['membership:manage', 'membership:sell', '*'] },
  },
  {
    path: 'memberships',
    name: 'memberships',
    component: MembershipsView,
    meta: { system: 'gym', anyOf: ['membership:manage', 'membership:sell', '*'] },
  },
  { path: 'coaches', name: 'coaches', component: CoachesView, meta: { system: 'gym', anyOf: ['coach:manage', '*'] } },
  {
    path: 'pt-packages',
    name: 'pt-packages',
    component: PtPackagesView,
    meta: { system: 'gym', anyOf: ['pt:sell', 'course:manage', '*'] },
  },
  {
    path: 'group-courses',
    name: 'group-courses',
    component: GroupCoursesView,
    meta: { system: 'gym', anyOf: ['course:manage', 'course:book', '*'] },
  },
  {
    path: 'coach-desk',
    name: 'coach-desk',
    component: CoachDeskView,
    meta: { system: 'gym', anyOf: ['course:checkin', 'course:manage', '*'] },
  },
  {
    path: 'retail',
    name: 'retail',
    component: RetailView,
    meta: { system: 'gym', anyOf: ['retail:read', 'retail:sell', 'retail:manage', '*'] },
  },
  { path: 'coupons', name: 'coupons', component: CouponsView, meta: { system: 'gym', anyOf: ['coupon:read', 'coupon:manage', '*'] } },
  {
    path: 'equipment',
    name: 'equipment',
    component: EquipmentView,
    meta: { system: 'gym', anyOf: ['equipment:read', 'equipment:manage', 'equipment:repair', '*'] },
  },
  {
    path: 'catering/menu',
    name: 'catering-menu',
    component: CateringMenuView,
    meta: { system: 'catering', anyOf: ['catering:menu', 'order:write', '*'] },
  },
  {
    path: 'catering/orders',
    name: 'catering-orders',
    component: CateringOrdersView,
    meta: { system: 'catering', anyOf: ['catering:order', 'order:read', 'order:write', '*'] },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', component: LayoutView, children },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) return true
  if (!auth.token) return { name: 'login', query: { redirect: to.fullPath } }
  if (!auth.me) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return { name: 'login' }
    }
  }
  const need = (to.meta.anyOf as string[] | undefined) || []
  if (need.length && !canAny(auth.me?.permissions || [], need)) {
    return { path: firstAllowedPathFromNav(auth) }
  }
  return true
})

export default router
