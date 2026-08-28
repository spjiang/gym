<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type UploadRequestOptions, type UploadUserFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import http from '../../../core/api/http'

type Settings = {
  site: {
    display_name?: string | null
    seo_title?: string | null
    seo_description?: string | null
    logo_url?: string | null
    member_web_url?: string | null
    miniprogram_hint?: string | null
    footer_note?: string | null
    icp_beian?: string | null
  }
  contact: { address: string | null; service_phone: string | null; business_hours: string | null }
}

const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const contact = ref<Settings['contact']>({ address: null, service_phone: null, business_hours: null })
const form = reactive({
  display_name: '',
  seo_title: '',
  seo_description: '',
  logo_url: '',
  member_web_url: '',
  miniprogram_hint: '',
  footer_note: '',
  icp_beian: '',
})

const logoList = computed<UploadUserFile[]>(() =>
  form.logo_url ? [{ name: 'Logo', url: form.logo_url, uid: 1 }] : [],
)

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<Settings>('/website/settings')
    contact.value = data.contact
    form.display_name = data.site.display_name || ''
    form.seo_title = data.site.seo_title || ''
    form.seo_description = data.site.seo_description || ''
    form.logo_url = data.site.logo_url || ''
    form.member_web_url = data.site.member_web_url || ''
    form.miniprogram_hint = data.site.miniprogram_hint || ''
    form.footer_note = data.site.footer_note || ''
    form.icp_beian = data.site.icp_beian || ''
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function uploadLogo(opt: UploadRequestOptions) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', opt.file as File)
    const { data } = await http.post<{ url: string }>('/uploads', fd, { timeout: 30000 })
    form.logo_url = data.url
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : 'Logo 上传失败')
  } finally {
    uploading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await http.put('/website/settings', {
      site: {
        display_name: form.display_name.trim() || null,
        seo_title: form.seo_title.trim() || null,
        seo_description: form.seo_description.trim() || null,
        logo_url: form.logo_url || null,
        member_web_url: form.member_web_url.trim() || null,
        miniprogram_hint: form.miniprogram_hint.trim() || null,
        footer_note: form.footer_note.trim() || null,
        icp_beian: form.icp_beian.trim() || null,
      },
    })
    ElMessage.success('站点设置已保存，刷新官网即可看到')
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
        <h3>站点设置</h3>
        <p class="hint">官网名称、SEO、会员端入口与页脚补充。页脚固定展示「北京晨曦坤泽科技有限公司」版权，不必写在补充句里。地址/电话/营业时间来自「观野SPACE 介绍」。</p>
      </div>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </div>

    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
      场地联系：{{ contact.service_phone || '未填电话' }} · {{ contact.business_hours || '未填营业时间' }} ·
      {{ contact.address || '未填地址' }}
    </el-alert>

    <el-form label-width="140px" style="max-width: 760px">
      <el-form-item label="对外站点名">
        <el-input v-model="form.display_name" maxlength="128" placeholder="默认 观野SPACE" />
      </el-form-item>
      <el-form-item label="SEO 标题">
        <el-input v-model="form.seo_title" maxlength="128" placeholder="空则使用站点名" />
      </el-form-item>
      <el-form-item label="SEO 描述">
        <el-input v-model="form.seo_description" type="textarea" :rows="2" maxlength="255" />
      </el-form-item>
      <el-form-item label="Logo">
        <el-upload
          list-type="picture-card"
          accept=".jpg,.jpeg,.png,.webp"
          :limit="1"
          :file-list="logoList"
          :http-request="uploadLogo"
          :on-remove="() => (form.logo_url = '')"
          :disabled="uploading"
          :class="{ 'hide-uploader': !!form.logo_url }"
        >
          <el-icon><Plus /></el-icon>
        </el-upload>
      </el-form-item>
      <el-form-item label="会员端链接">
        <el-input v-model="form.member_web_url" maxlength="255" placeholder="空则使用环境变量 MEMBER_WEB_PUBLIC_URL" />
      </el-form-item>
      <el-form-item label="小程序提示">
        <el-input v-model="form.miniprogram_hint" maxlength="128" placeholder="空则官网不展示小程序入口" />
      </el-form-item>
      <el-form-item label="页脚补充">
        <el-input v-model="form.footer_note" maxlength="255" />
      </el-form-item>
      <el-form-item label="备案号">
        <el-input v-model="form.icp_beian" maxlength="64" />
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
