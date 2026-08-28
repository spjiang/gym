<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadRequestOptions, type UploadUserFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import http from '../../../core/api/http'

type Settings = {
  home: {
    hero_image_url?: string | null
    headline?: string | null
    subheadline?: string | null
    show_space?: boolean
    show_fit?: boolean
    show_bar?: boolean
  }
}

const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const form = reactive({
  hero_image_url: '',
  headline: '',
  subheadline: '',
  show_space: true,
  show_fit: true,
  show_bar: true,
})

const heroList = computed<UploadUserFile[]>(() =>
  form.hero_image_url ? [{ name: '主视觉', url: form.hero_image_url, uid: 1 }] : [],
)

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<Settings>('/website/settings')
    form.hero_image_url = data.home.hero_image_url || ''
    form.headline = data.home.headline || ''
    form.subheadline = data.home.subheadline || ''
    form.show_space = data.home.show_space !== false
    form.show_fit = data.home.show_fit !== false
    form.show_bar = data.home.show_bar !== false
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function uploadHero(opt: UploadRequestOptions) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', opt.file as File)
    const { data } = await http.post<{ url: string }>('/uploads', fd, { timeout: 30000 })
    form.hero_image_url = data.url
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '主视觉上传失败')
  } finally {
    uploading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await http.put('/website/settings', {
      home: {
        hero_image_url: form.hero_image_url || null,
        headline: form.headline.trim() || null,
        subheadline: form.subheadline.trim() || null,
        show_space: form.show_space,
        show_fit: form.show_fit,
        show_bar: form.show_bar,
      },
    })
    ElMessage.success('首页配置已保存')
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
        <h3>首页配置</h3>
        <p class="hint">官网首页主视觉、标题与三个品牌入口是否展示。</p>
      </div>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </div>

    <el-form label-width="140px" style="max-width: 760px">
      <el-form-item label="主视觉">
        <el-upload
          list-type="picture-card"
          accept=".jpg,.jpeg,.png,.webp"
          :limit="1"
          :file-list="heroList"
          :http-request="uploadHero"
          :on-remove="() => (form.hero_image_url = '')"
          :disabled="uploading"
          :class="{ 'hide-uploader': !!form.hero_image_url }"
        >
          <el-icon><Plus /></el-icon>
        </el-upload>
      </el-form-item>
      <el-form-item label="主标题">
        <el-input v-model="form.headline" maxlength="128" />
      </el-form-item>
      <el-form-item label="副标题">
        <el-input v-model="form.subheadline" maxlength="255" placeholder="默认 SPORTS · EVENTS · COMMUNITY" />
      </el-form-item>
      <el-form-item label="品牌入口">
        <el-checkbox v-model="form.show_space">SPACE</el-checkbox>
        <el-checkbox v-model="form.show_fit">FIT</el-checkbox>
        <el-checkbox v-model="form.show_bar">BAR</el-checkbox>
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
  margin-bottom: 16px;
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
