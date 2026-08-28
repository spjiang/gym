/** 管理端图片卡片「放大」预览。el-upload 的 on-preview 默认是空函数，必须自己打开查看器。 */

import { ref } from 'vue'
import type { UploadFile } from 'element-plus'

export const imagePreviewVisible = ref(false)
export const imagePreviewUrls = ref<string[]>([])
export const imagePreviewIndex = ref(0)

export function previewUploadFile(file: UploadFile, siblings?: { url?: string }[]) {
  const current = (file.url || '').trim()
  if (!current) return
  const urls = (siblings?.map((item) => (item.url || '').trim()).filter(Boolean) as string[]) || []
  imagePreviewUrls.value = urls.length ? urls : [current]
  const idx = imagePreviewUrls.value.indexOf(current)
  imagePreviewIndex.value = idx >= 0 ? idx : 0
  imagePreviewVisible.value = true
}

export function closeImagePreview() {
  imagePreviewVisible.value = false
}
