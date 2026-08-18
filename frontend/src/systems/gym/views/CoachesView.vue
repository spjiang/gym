<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules, type UploadRequestOptions, type UploadUserFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import http from '../../../core/api/http'
import { percentLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Staff = { id: number; display_name: string; username: string }
type Coach = {
  id: number
  display_name: string
  title: string | null
  gender: string | null
  phone: string | null
  years_experience: number | null
  hourly_rate: string | null
  pt_commission_rate: string | null
  specialties: string | null
  certifications: string | null
  bio: string | null
  availability_note: string | null
  avatar_url: string | null
  intro_image_urls: string[]
  is_active: boolean
  staff_user_id: number
}

const INTRO_IMAGE_LIMIT = 9
const GENDER_LABEL: Record<string, string> = { male: '男', female: '女', other: '其他' }

const merchants = ref<Merchant[]>([])
const staff = ref<Staff[]>([])
const coaches = ref<Coach[]>([])
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const query = reactive({ q: '', status: '' as '' | 'active' | 'inactive', gender: '' as string })

const dialogVisible = ref(false)
const detailVisible = ref(false)
const detail = ref<Coach | null>(null)
const submitting = ref(false)
const uploading = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const avatarList = ref<UploadUserFile[]>([])
const introList = ref<UploadUserFile[]>([])
const form = reactive({
  staff_user_id: undefined as number | undefined,
  display_name: '',
  title: '',
  gender: '' as string,
  phone: '',
  years_experience: undefined as number | undefined,
  hourly_rate: '',
  pt_commission_rate: '',
  specialties: '',
  certifications: '',
  bio: '',
  availability_note: '',
  avatar_url: '' as string,
  intro_image_urls: [] as string[],
})

const rules: FormRules = {
  staff_user_id: [{ required: true, message: '请选择员工账号', trigger: 'change' }],
  display_name: [{ required: true, message: '请填写教练显示名', trigger: 'blur' }],
}

function staffName(id: number | undefined) {
  const s = staff.value.find((x) => x.id === id)
  return s ? `${s.display_name} (${s.username})` : ''
}

function genderLabel(code: string | null | undefined) {
  if (!code) return '—'
  return GENDER_LABEL[code] || code
}

function syncMediaLists() {
  avatarList.value = form.avatar_url ? [{ name: '头像', url: form.avatar_url, uid: 1 }] : []
  introList.value = form.intro_image_urls.map((url, i) => ({ name: `图${i + 1}`, url, uid: i + 1 }))
}

function resetForm() {
  form.staff_user_id = undefined
  form.display_name = ''
  form.title = ''
  form.gender = ''
  form.phone = ''
  form.years_experience = undefined
  form.hourly_rate = ''
  form.pt_commission_rate = ''
  form.specialties = ''
  form.certifications = ''
  form.bio = ''
  form.availability_note = ''
  form.avatar_url = ''
  form.intro_image_urls = []
  syncMediaLists()
}

async function refresh() {
  loading.value = true
  try {
    const [m, s] = await Promise.all([
      http.get('/merchants'),
      http.get('/staff', { params: { page: 1, page_size: 100 } }),
    ])
    merchants.value = merchantsWithSystem(m.data, 'gym')
    staff.value = s.data.items
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const { data } = await http.get('/coaches', {
      params: {
        merchant_id: merchantId.value,
        q: query.q.trim() || undefined,
        is_active: query.status === 'active' ? true : query.status === 'inactive' ? false : undefined,
        gender: query.gender || undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    coaches.value = data.items
    total.value = data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void refresh()
}

function resetSearch() {
  query.q = ''
  query.status = ''
  query.gender = ''
  page.value = 1
  void refresh()
}

function openDialog() {
  editingId.value = null
  resetForm()
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

function openEdit(row: Coach) {
  editingId.value = row.id
  form.staff_user_id = row.staff_user_id
  form.display_name = row.display_name
  form.title = row.title || ''
  form.gender = row.gender || ''
  form.phone = row.phone || ''
  form.years_experience = row.years_experience ?? undefined
  form.hourly_rate = row.hourly_rate || ''
  form.pt_commission_rate = row.pt_commission_rate || ''
  form.specialties = row.specialties || ''
  form.certifications = row.certifications || ''
  form.bio = row.bio || ''
  form.availability_note = row.availability_note || ''
  form.avatar_url = row.avatar_url || ''
  form.intro_image_urls = [...(row.intro_image_urls || [])]
  syncMediaLists()
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

function openDetail(row: Coach) {
  detail.value = row
  detailVisible.value = true
}

async function uploadImage(opt: UploadRequestOptions): Promise<string> {
  const fd = new FormData()
  fd.append('file', opt.file as File)
  const { data } = await http.post<{ url: string }>('/uploads', fd, { timeout: 30000 })
  return data.url
}

async function uploadAvatar(opt: UploadRequestOptions) {
  uploading.value = true
  try {
    form.avatar_url = await uploadImage(opt)
    syncMediaLists()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '头像上传失败')
  } finally {
    uploading.value = false
  }
}

function removeAvatar() {
  form.avatar_url = ''
  syncMediaLists()
}

async function uploadIntro(opt: UploadRequestOptions) {
  if (form.intro_image_urls.length >= INTRO_IMAGE_LIMIT) {
    ElMessage.warning(`介绍图最多 ${INTRO_IMAGE_LIMIT} 张`)
    return
  }
  uploading.value = true
  try {
    const url = await uploadImage(opt)
    form.intro_image_urls.push(url)
    syncMediaLists()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '图片上传失败')
  } finally {
    uploading.value = false
  }
}

function removeIntro(file: UploadUserFile) {
  form.intro_image_urls = form.intro_image_urls.filter((url) => url !== file.url)
  syncMediaLists()
}

function onIntroExceed() {
  ElMessage.warning(`介绍图最多 ${INTRO_IMAGE_LIMIT} 张`)
}

async function saveCoach() {
  const ok = await formRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    const payload = {
      merchant_id: mid,
      staff_user_id: form.staff_user_id,
      display_name: form.display_name.trim(),
      title: form.title.trim() || null,
      gender: form.gender || null,
      phone: form.phone.trim() || null,
      years_experience: form.years_experience ?? null,
      hourly_rate: form.hourly_rate.trim() || null,
      pt_commission_rate: form.pt_commission_rate.trim() || null,
      specialties: form.specialties.trim() || null,
      certifications: form.certifications.trim() || null,
      bio: form.bio.trim() || null,
      availability_note: form.availability_note.trim() || null,
      avatar_url: form.avatar_url || null,
      intro_image_urls: form.intro_image_urls,
    }
    if (editingId.value) {
      await http.patch(`/coaches/${editingId.value}`, payload)
      ElMessage.success('教练已更新')
    } else {
      await http.post('/coaches', payload)
      ElMessage.success('教练已创建')
    }
    dialogVisible.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function deactivate(id: number) {
  await http.post(`/coaches/${id}/deactivate`)
  ElMessage.success('已停用')
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>教练档案</h3>
        <p class="lead">维护对外展示的教练资料、头像与图文介绍。团课排课在「团课管理」，课包售卖在「私教课管理」。</p>
      </div>
      <el-button type="primary" @click="openDialog">新建教练</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="search">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="姓名 / 头衔 / 擅长 / 电话" style="width: 220px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 110px">
          <el-option label="启用" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>
      </el-form-item>
      <el-form-item label="性别">
        <el-select v-model="query.gender" clearable placeholder="全部" style="width: 110px">
          <el-option label="男" value="male" />
          <el-option label="女" value="female" />
          <el-option label="其他" value="other" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="coaches" v-loading="loading" stripe>
      <el-table-column label="教练" min-width="200">
        <template #default="{ row }">
          <div class="coach-cell">
            <img v-if="row.avatar_url" class="avatar" :src="row.avatar_url" alt="" />
            <div v-else class="avatar avatar-fallback">{{ row.display_name.slice(0, 1) }}</div>
            <div>
              <div class="name">{{ row.display_name }}</div>
              <div class="sub">{{ row.title || '—' }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="员工账号" min-width="160">
        <template #default="{ row }">{{ staffName(row.staff_user_id) }}</template>
      </el-table-column>
      <el-table-column label="性别" width="80">
        <template #default="{ row }">{{ genderLabel(row.gender) }}</template>
      </el-table-column>
      <el-table-column prop="specialties" label="擅长" min-width="140">
        <template #default="{ row }">{{ row.specialties || '—' }}</template>
      </el-table-column>
      <el-table-column label="年限" width="80">
        <template #default="{ row }">{{ row.years_experience != null ? `${row.years_experience} 年` : '—' }}</template>
      </el-table-column>
      <el-table-column label="私教提成" width="110">
        <template #default="{ row }">
          {{ row.pt_commission_rate ? percentLabel(row.pt_commission_rate) : '商户规则' }}
        </template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.is_active" link type="danger" @click="deactivate(row.id)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="refresh"
        @size-change="
          () => {
            page = 1
            refresh()
          }
        "
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑教练' : '新建教练'" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="员工账号" prop="staff_user_id">
          <el-select v-model="form.staff_user_id" filterable :disabled="!!editingId" style="width: 100%">
            <el-option v-for="s in staff" :key="s.id" :label="`${s.display_name} (${s.username})`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="form.display_name" placeholder="对外展示的教练姓名" maxlength="64" />
        </el-form-item>
        <el-form-item label="头衔">
          <el-input v-model="form.title" placeholder="如：金牌私教 / 团课主教练" maxlength="64" />
        </el-form-item>
        <el-form-item label="性别">
          <el-select v-model="form.gender" clearable placeholder="选填" style="width: 100%">
            <el-option label="男" value="male" />
            <el-option label="女" value="female" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.phone" placeholder="对外展示，选填" maxlength="32" />
        </el-form-item>
        <el-form-item label="从业年限">
          <el-input-number v-model="form.years_experience" :min="0" :max="60" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="课时参考价">
          <el-input v-model="form.hourly_rate" placeholder="如 300，选填" />
        </el-form-item>
        <el-form-item label="私教提成比例">
          <el-input v-model="form.pt_commission_rate" placeholder="0.4 表示 40%，留空走商户规则" />
        </el-form-item>
        <el-form-item label="擅长">
          <el-input v-model="form.specialties" placeholder="如：减脂 / 力量训练 / 普拉提" maxlength="255" />
        </el-form-item>
        <el-form-item label="资质证书">
          <el-input
            v-model="form.certifications"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
            placeholder="如：NSCA-CPT、体适能培训证书"
          />
        </el-form-item>
        <el-form-item label="可约时段">
          <el-input v-model="form.availability_note" placeholder="如：工作日 10:00-21:00" maxlength="255" />
        </el-form-item>
        <el-form-item label="个人简介">
          <el-input
            v-model="form.bio"
            type="textarea"
            :rows="4"
            maxlength="1000"
            show-word-limit
            placeholder="对外介绍教练背景、带课风格等"
          />
        </el-form-item>
        <el-form-item label="头像">
          <el-upload
            list-type="picture-card"
            accept=".jpg,.jpeg,.png,.webp"
            :limit="1"
            :file-list="avatarList"
            :http-request="uploadAvatar"
            :on-remove="removeAvatar"
            :disabled="uploading"
            :class="{ 'hide-uploader': !!form.avatar_url }"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
          <p class="hint">一张，不超过 8MB，支持 JPG / PNG / WEBP。</p>
        </el-form-item>
        <el-form-item label="图片介绍">
          <el-upload
            list-type="picture-card"
            accept=".jpg,.jpeg,.png,.webp"
            :limit="INTRO_IMAGE_LIMIT"
            :file-list="introList"
            :http-request="uploadIntro"
            :on-remove="removeIntro"
            :on-exceed="onIntroExceed"
            :disabled="uploading"
            :class="{ 'hide-uploader': form.intro_image_urls.length >= INTRO_IMAGE_LIMIT }"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
          <p class="hint">最多 {{ INTRO_IMAGE_LIMIT }} 张，用于会员端展示教练风采。</p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveCoach">{{ editingId ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="教练详情" width="640px" destroy-on-close>
      <div v-if="detail" class="detail">
        <div class="detail-head">
          <img v-if="detail.avatar_url" class="detail-avatar" :src="detail.avatar_url" alt="" />
          <div v-else class="detail-avatar avatar-fallback">{{ detail.display_name.slice(0, 1) }}</div>
          <div>
            <h4>{{ detail.display_name }}</h4>
            <p>{{ detail.title || '—' }} · {{ genderLabel(detail.gender) }}</p>
          </div>
        </div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="员工账号">{{ staffName(detail.staff_user_id) }}</el-descriptions-item>
          <el-descriptions-item label="电话">{{ detail.phone || '—' }}</el-descriptions-item>
          <el-descriptions-item label="从业年限">
            {{ detail.years_experience != null ? `${detail.years_experience} 年` : '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="课时参考价">{{ detail.hourly_rate ? `¥${detail.hourly_rate}` : '—' }}</el-descriptions-item>
          <el-descriptions-item label="私教提成比例">
            {{ detail.pt_commission_rate ? percentLabel(detail.pt_commission_rate) : '按商户规则' }}
          </el-descriptions-item>
          <el-descriptions-item label="擅长" :span="2">{{ detail.specialties || '—' }}</el-descriptions-item>
          <el-descriptions-item label="可约时段" :span="2">{{ detail.availability_note || '—' }}</el-descriptions-item>
          <el-descriptions-item label="资质证书" :span="2">{{ detail.certifications || '—' }}</el-descriptions-item>
          <el-descriptions-item label="个人简介" :span="2">{{ detail.bio || '—' }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detail.intro_image_urls?.length" class="gallery">
          <el-image
            v-for="url in detail.intro_image_urls"
            :key="url"
            :src="url"
            :preview-src-list="detail.intro_image_urls"
            fit="cover"
            class="gallery-img"
          />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}
.toolbar h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}
.lead {
  margin: 0;
  max-width: 640px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--el-text-color-secondary);
}
.filters {
  margin-bottom: 4px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.coach-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.avatar,
.detail-avatar {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  flex-shrink: 0;
}
.detail-avatar {
  width: 64px;
  height: 64px;
  font-size: 22px;
}
.avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  font-weight: 600;
}
.name {
  font-weight: 600;
}
.sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.hide-uploader :deep(.el-upload--picture-card) {
  display: none;
}
.detail-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}
.detail-head h4 {
  margin: 0 0 4px;
}
.detail-head p {
  margin: 0;
  color: var(--el-text-color-secondary);
}
.gallery {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}
.gallery-img {
  width: 96px;
  height: 96px;
  border-radius: 8px;
}
</style>
