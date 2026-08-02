import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import LayoutView from '../views/LayoutView.vue'
import HomeView from '../views/HomeView.vue'
import MembershipsView from '../views/MembershipsView.vue'
import ClassesView from '../views/ClassesView.vue'
import ShopView from '../views/ShopView.vue'
import AccessView from '../views/AccessView.vue'
import NotificationsView from '../views/NotificationsView.vue'
import CouponsView from '../views/CouponsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    {
      path: '/',
      component: LayoutView,
      children: [
        { path: '', name: 'home', component: HomeView },
        { path: 'memberships', name: 'memberships', component: MembershipsView },
        { path: 'classes', name: 'classes', component: ClassesView },
        { path: 'shop', name: 'shop', component: ShopView },
        { path: 'coupons', name: 'coupons', component: CouponsView },
        { path: 'access', name: 'access', component: AccessView },
        { path: 'notifications', name: 'notifications', component: NotificationsView },
      ],
    },
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
  return true
})

export default router
