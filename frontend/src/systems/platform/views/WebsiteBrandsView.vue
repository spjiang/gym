<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadFile, type UploadRequestOptions, type UploadUserFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import http from '../../../core/api/http'
import { previewUploadFile } from '../../../core/imagePreview'

type BrandKey = 'space' | 'fit' | 'bar'
type Brand = {
  title?: string | null
  cover_image_url?: string | null
  body?: string | null
  gallery_image_urls?: string[]
  cta_label?: string | null
  cta_url?: string | null
}

const GALLERY_LIMIT = 9
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const active = ref<BrandKey>('space')
const brands = reactive<Record<BrandKey, Brand>>({
  space: emptyBrand(),
  fit: emptyBrand(),
  bar: emptyBrand(),
})

function emptyBrand(): Brand {
  return { title: '', cover_image_url: '', body: '', gallery_image_urls: [], cta_label: '', cta_url: '' }
}

function asBrand(raw: Brand | undefined): Brand {
  return {
    title: raw?.title || '',
    cover_image_url: raw?.cover_image_url || '',
    body: raw?.body || '',
    gallery_image_urls: [...(raw?.gallery_image_urls || [])],
    cta_label: raw?.cta_label || '',
    cta_url: raw?.cta_url || '',
  }
}

const current = computed(() => brands[active.value])
const coverList = computed<UploadUserFile[]>(() =>
  current.value.cover_image_url ? [{ name: '封面', url: current.value.cover_image_url, uid: 1 }] : [],
)
const galleryList = computed<UploadUserFile[]>(() =>
  (current.value.gallery_image_urls || []).map((url, i) => ({ name: `图${i + 1}`, url, uid: i + 1 })),
)

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<{ brands: Record<BrandKey, Brand> }>('/website/settings')
    brands.space = asBrand(data.brands?.space)
    brands.fit = asBrand(data.brands?.fit)
    brands.bar = asBrand(data.brands?.bar)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function uploadImage(opt: UploadRequestOptions): Promise<string> {
  const fd = new FormData()
  fd.append('file', opt.file as File)
  const { data } = await http.post<{ url: string }>('/uploads', fd, { timeout: 30000 })
  return data.url
}

async function uploadCover(opt: UploadRequestOptions) {
  uploading.value = true
  try {
    current.value.cover_image_url = await uploadImage(opt)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '封面上传失败')
  } finally {
    uploading.value = false
  }
}

async function uploadGallery(opt: UploadRequestOptions) {
  const list = current.value.gallery_image_urls || []
  if (list.length >= GALLERY_LIMIT) {
    ElMessage.warning(`图集最多 ${GALLERY_LIMIT} 张`)
    return
  }
  uploading.value = true
  try {
    list.push(await uploadImage(opt))
    current.value.gallery_image_urls = list
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '图集上传失败')
  } finally {
    uploading.value = false
  }
}

function removeGallery(file: UploadFile) {
  current.value.gallery_image_urls = (current.value.gallery_image_urls || []).filter((u) => u !== file.url)
}

function payload(b: Brand): Brand {
  return {
    title: (b.title || '').trim() || null,
    cover_image_url: b.cover_image_url || null,
    body: (b.body || '').trim() || null,
    gallery_image_urls: b.gallery_image_urls || [],
    cta_label: (b.cta_label || '').trim() || null,
    cta_url: (b.cta_url || '').trim() || null,
  }
}

async function save() {
  saving.value = true
  try {
    await http.put('/website/settings', {
      brands: {
        space: payload(brands.space),
        fit: payload(brands.fit),
        bar: payload(brands.bar),
      },
    })
    ElMessage.success('品牌页面已保存')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar">
      <div>
        <h3>品牌页面</h3>
        <p class="hint">SPACE / FIT / BAR 各自标题、封面、正文与跳转按钮。</p>
      </div>
      <el-button type="primary" :loading="saving" @click="save">保存三个品牌</el-button>
    </div>

    <el-tabs v-model="active">
      <el-tab-pane label="SPACE" name="space" />
      <el-tab-pane label="FIT" name="fit" />
      <el-tab-pane label="BAR" name="bar" />
    </el-tabs>

    <el-form label-width="120px" style="max-width: 860px">
      <el-form-item label="标题">
        <el-input v-model="current.title" maxlength="64" />
      </el-form-item>
      <el-form-item label="封面">
        <el-upload
          list-type="picture-card"
          accept=".jpg,.jpeg,.png,.webp"
          :limit="1"
          :file-list="coverList"
          :http-request="uploadCover"
          :on-preview="previewUploadFile"
          :on-remove="() => (current.cover_image_url = '')"
          :disabled="uploading"
          :class="{ 'hide-uploader': !!current.cover_image_url }"
        >
          <el-icon><Plus /></el-icon>
        </el-upload>
      </el-form-item>
      <el-form-item label="正文">
        <el-input v-model="current.body" type="textarea" :rows="8" placeholder="Markdown" />
      </el-form-item>
      <el-form-item label="图集">
        <el-upload
          list-type="picture-card"
          accept=".jpg,.jpeg,.png,.webp"
          :limit="GALLERY_LIMIT"
          :file-list="galleryList"
          :http-request="uploadGallery"
          :on-preview="(file: UploadFile) => previewUploadFile(file, galleryList)"
          :on-remove="removeGallery"
          :disabled="uploading"
          :class="{ 'hide-uploader': (current.gallery_image_urls || []).length >= GALLERY_LIMIT }"
        >
          <el-icon><Plus /></el-icon>
        </el-upload>
      </el-form-item>
      <el-form-item label="按钮文案">
        <el-input v-model="current.cta_label" maxlength="32" placeholder="有文案且有链接才显示按钮" />
      </el-form-item>
      <el-form-item label="按钮链接">
        <el-input v-model="current.cta_url" maxlength="255" />
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.toolbar h3 {
  margin: 0;
}
.hint {
  margin: 4px 0 0;
  color: var(--admin-ink-muted);
  font-size: 13px;
}
.hide-uploader :deep(.el-upload--picture-card) {
  display: none;
}
</style>
