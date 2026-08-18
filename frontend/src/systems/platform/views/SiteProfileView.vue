<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadFile, type UploadRequestOptions, type UploadUserFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import http from '../../../core/api/http'

type Profile = {
  id: number
  name: string
  tagline: string | null
  description: string | null
  address: string | null
  service_phone: string | null
  business_hours: string | null
  cover_image_url: string | null
  banner_image_urls: string[]
  gallery_image_urls: string[]
}

const BANNER_LIMIT = 6
const GALLERY_LIMIT = 9

const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const form = reactive({
  name: '观野SPACE',
  tagline: '',
  description: '',
  address: '',
  service_phone: '',
  business_hours: '',
  cover_image_url: '',
  banner_image_urls: [] as string[],
  gallery_image_urls: [] as string[],
})

const coverList = computed<UploadUserFile[]>(() =>
  form.cover_image_url ? [{ name: '封面', url: form.cover_image_url, uid: 1 }] : [],
)
const bannerList = computed<UploadUserFile[]>(() =>
  form.banner_image_urls.map((url, i) => ({ name: `广告${i + 1}`, url, uid: i + 1 })),
)
const galleryList = computed<UploadUserFile[]>(() =>
  form.gallery_image_urls.map((url, i) => ({ name: `环境${i + 1}`, url, uid: i + 1 })),
)

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<Profile>('/site/profile')
    form.name = data.name || '观野SPACE'
    form.tagline = data.tagline || ''
    form.description = data.description || ''
    form.address = data.address || ''
    form.service_phone = data.service_phone || ''
    form.business_hours = data.business_hours || ''
    form.cover_image_url = data.cover_image_url || ''
    form.banner_image_urls = [...(data.banner_image_urls || [])]
    form.gallery_image_urls = [...(data.gallery_image_urls || [])]
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
    form.cover_image_url = await uploadImage(opt)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '封面上传失败')
  } finally {
    uploading.value = false
  }
}

async function uploadBanner(opt: UploadRequestOptions) {
  if (form.banner_image_urls.length >= BANNER_LIMIT) {
    ElMessage.warning(`广告图最多 ${BANNER_LIMIT} 张`)
    return
  }
  uploading.value = true
  try {
    form.banner_image_urls.push(await uploadImage(opt))
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '广告图上传失败')
  } finally {
    uploading.value = false
  }
}

async function uploadGallery(opt: UploadRequestOptions) {
  if (form.gallery_image_urls.length >= GALLERY_LIMIT) {
    ElMessage.warning(`环境图最多 ${GALLERY_LIMIT} 张`)
    return
  }
  uploading.value = true
  try {
    form.gallery_image_urls.push(await uploadImage(opt))
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '环境图上传失败')
  } finally {
    uploading.value = false
  }
}

function removeCover() {
  form.cover_image_url = ''
}

function removeBanner(file: UploadFile) {
  form.banner_image_urls = form.banner_image_urls.filter((u) => u !== file.url)
}

function removeGallery(file: UploadFile) {
  form.gallery_image_urls = form.gallery_image_urls.filter((u) => u !== file.url)
}

async function save() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写场地名称')
    return
  }
  saving.value = true
  try {
    await http.put('/site/profile', {
      name: form.name.trim(),
      tagline: form.tagline.trim() || null,
      description: form.description.trim() || null,
      address: form.address.trim() || null,
      service_phone: form.service_phone.trim() || null,
      business_hours: form.business_hours.trim() || null,
      cover_image_url: form.cover_image_url || null,
      banner_image_urls: form.banner_image_urls,
      gallery_image_urls: form.gallery_image_urls,
    })
    ElMessage.success('观野SPACE 介绍已保存，会员门户将同步展示')
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
        <h3>观野SPACE 介绍</h3>
        <p class="hint">配置会员端商场门户：广告位、整体介绍、客服电话与地址。</p>
      </div>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
      title="此处为场地级门户资料，全场共用。商户自己的封面请到「商户组织」里维护。"
    />

    <el-form label-width="120px" style="max-width: 860px">
      <h4>基础信息</h4>
      <el-form-item label="场地名称">
        <el-input v-model="form.name" maxlength="128" />
      </el-form-item>
      <el-form-item label="对外口号">
        <el-input v-model="form.tagline" maxlength="128" placeholder="如：运动 · 夜生活 · 社区" />
      </el-form-item>
      <el-form-item label="整体介绍">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="4"
          maxlength="800"
          show-word-limit
          placeholder="写给会员看的商场介绍"
        />
      </el-form-item>
      <el-form-item label="地址">
        <el-input v-model="form.address" maxlength="255" placeholder="北京市昌平区回龙观公园" />
      </el-form-item>
      <el-form-item label="客服电话">
        <el-input v-model="form.service_phone" maxlength="32" placeholder="会员可直接拨打" />
      </el-form-item>
      <el-form-item label="营业时间">
        <el-input v-model="form.business_hours" maxlength="128" placeholder="如：06:00–24:00" />
      </el-form-item>

      <h4>门户视觉</h4>
      <el-form-item label="封面图">
        <el-upload
          list-type="picture-card"
          accept=".jpg,.jpeg,.png,.webp"
          :limit="1"
          :file-list="coverList"
          :http-request="uploadCover"
          :on-remove="removeCover"
          :disabled="uploading"
          :class="{ 'hide-uploader': !!form.cover_image_url }"
        >
          <el-icon><Plus /></el-icon>
        </el-upload>
        <p class="hint">一张，无广告图时作为门户主视觉。</p>
      </el-form-item>
      <el-form-item label="广告位">
        <el-upload
          list-type="picture-card"
          accept=".jpg,.jpeg,.png,.webp"
          :limit="BANNER_LIMIT"
          :file-list="bannerList"
          :http-request="uploadBanner"
          :on-remove="removeBanner"
          :disabled="uploading"
          :class="{ 'hide-uploader': form.banner_image_urls.length >= BANNER_LIMIT }"
        >
          <el-icon><Plus /></el-icon>
        </el-upload>
        <p class="hint">最多 {{ BANNER_LIMIT }} 张，会员门户顶部轮播。</p>
      </el-form-item>
      <el-form-item label="环境相册">
        <el-upload
          list-type="picture-card"
          accept=".jpg,.jpeg,.png,.webp"
          :limit="GALLERY_LIMIT"
          :file-list="galleryList"
          :http-request="uploadGallery"
          :on-remove="removeGallery"
          :disabled="uploading"
          :class="{ 'hide-uploader': form.gallery_image_urls.length >= GALLERY_LIMIT }"
        >
          <el-icon><Plus /></el-icon>
        </el-upload>
        <p class="hint">最多 {{ GALLERY_LIMIT }} 张，展示园区、大堂、夜景等。</p>
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
h4 {
  margin: 8px 0 16px;
  font-size: 15px;
}
.hide-uploader :deep(.el-upload--picture-card) {
  display: none;
}
</style>
