import { createRouter, createWebHistory } from 'vue-router'
import LayoutView from '../views/LayoutView.vue'
import HomeView from '../views/HomeView.vue'
import BrandView from '../views/BrandView.vue'
import ArticleListView from '../views/ArticleListView.vue'
import ArticleDetailView from '../views/ArticleDetailView.vue'
import NotFoundView from '../views/NotFoundView.vue'

export default createRouter({
  history: createWebHistory(),
  scrollBehavior() {
    return { top: 0 }
  },
  routes: [
    {
      path: '/',
      component: LayoutView,
      children: [
        { path: '', name: 'home', component: HomeView },
        { path: 'space', name: 'brand-space', component: BrandView, props: { brandKey: 'space' } },
        { path: 'fit', name: 'brand-fit', component: BrandView, props: { brandKey: 'fit' } },
        { path: 'bar', name: 'brand-bar', component: BrandView, props: { brandKey: 'bar' } },
        { path: 'news', name: 'news', component: ArticleListView, props: { channel: 'news' } },
        { path: 'news/:id', name: 'news-detail', component: ArticleDetailView, props: { channel: 'news' } },
        { path: 'jobs', name: 'jobs', component: ArticleListView, props: { channel: 'jobs' } },
        { path: 'jobs/:id', name: 'jobs-detail', component: ArticleDetailView, props: { channel: 'jobs' } },
        { path: 'partners', name: 'partners', component: ArticleListView, props: { channel: 'partners' } },
        { path: 'partners/:id', name: 'partners-detail', component: ArticleDetailView, props: { channel: 'partners' } },
        { path: ':pathMatch(.*)*', name: 'not-found', component: NotFoundView },
      ],
    },
  ],
})
