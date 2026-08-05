import { createRouter, createWebHistory } from 'vue-router'
import { pathForMerchant, useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import StoresView from '../views/StoresView.vue'
import LayoutView from '../views/LayoutView.vue'
import HomeView from '../views/HomeView.vue'
import MembershipsView from '../views/MembershipsView.vue'
import MembershipDetailView from '../views/MembershipDetailView.vue'
import PtPackageDetailView from '../views/PtPackageDetailView.vue'
import ClassesView from '../views/ClassesView.vue'
import ShopView from '../views/ShopView.vue'
import AccessView from '../views/AccessView.vue'
import NotificationsView from '../views/NotificationsView.vue'
import CouponsView from '../views/CouponsView.vue'
import CateringMenuView from '../views/catering/MenuView.vue'
import CateringOrdersView from '../views/catering/OrdersView.vue'
import CateringOrderDetailView from '../views/catering/OrderDetailView.vue'
import ProfileView from '../views/ProfileView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/stores', name: 'stores', component: StoresView },
    { path: '/me', name: 'me', component: ProfileView },
    {
      path: '/m/:merchantId',
      component: LayoutView,
      children: [
        { path: 'gym', name: 'gym-home', component: HomeView, meta: { system: 'gym' } },
        { path: 'gym/memberships', name: 'gym-memberships', component: MembershipsView, meta: { system: 'gym' } },
        {
          path: 'gym/memberships/:membershipId',
          name: 'gym-membership-detail',
          component: MembershipDetailView,
          meta: { system: 'gym' },
        },
        {
          path: 'gym/pt-packages/:packageId',
          name: 'gym-pt-detail',
          component: PtPackageDetailView,
          meta: { system: 'gym' },
        },
        { path: 'gym/classes', name: 'gym-classes', component: ClassesView, meta: { system: 'gym' } },
        { path: 'gym/shop', name: 'gym-shop', component: ShopView, meta: { system: 'gym' } },
        { path: 'gym/coupons', name: 'gym-coupons', component: CouponsView, meta: { system: 'gym' } },
        { path: 'gym/access', name: 'gym-access', component: AccessView, meta: { system: 'gym' } },
        {
          path: 'gym/notifications',
          name: 'gym-notifications',
          component: NotificationsView,
          meta: { system: 'gym' },
        },
        { path: 'catering', name: 'catering-menu', component: CateringMenuView, meta: { system: 'catering' } },
        {
          path: 'catering/orders',
          name: 'catering-orders',
          component: CateringOrdersView,
          meta: { system: 'catering' },
        },
        {
          path: 'catering/orders/:orderId',
          name: 'catering-order',
          component: CateringOrderDetailView,
          meta: { system: 'catering' },
        },
      ],
    },
    { path: '/', redirect: '/stores' },
    { path: '/memberships', redirect: '/stores' },
    { path: '/classes', redirect: '/stores' },
    { path: '/shop', redirect: '/stores' },
    { path: '/coupons', redirect: '/stores' },
    { path: '/access', redirect: '/stores' },
    { path: '/notifications', redirect: '/stores' },
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

  if (to.name === 'stores' || to.name === 'me') return true

  const mid = Number(to.params.merchantId)
  if (!mid || Number.isNaN(mid)) return { name: 'stores' }

  const merchant = auth.me?.merchants.find((m) => m.id === mid)
  if (!merchant) return { name: 'stores' }

  auth.setMerchantId(mid)
  const need = to.meta.system as string | undefined
  if (need && !merchant.subsystem_codes.includes(need)) {
    return pathForMerchant(merchant)
  }
  return true
})

export default router
