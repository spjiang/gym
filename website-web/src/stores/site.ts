import { defineStore } from 'pinia'
import { ref } from 'vue'
import http from '../api/http'
import type { PublicWebsite } from '../api/types'

export const useSiteStore = defineStore('site', () => {
  const data = ref<PublicWebsite | null>(null)
  const error = ref('')
  const loading = ref(false)

  async function load() {
    if (data.value || loading.value) return
    loading.value = true
    error.value = ''
    try {
      const { data: body } = await http.get<PublicWebsite>('/public/website')
      data.value = body
      if (body.site.seo_title) document.title = body.site.seo_title
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '暂时无法加载'
    } finally {
      loading.value = false
    }
  }

  return { data, error, loading, load }
})
