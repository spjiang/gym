<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type UploadRequestOptions } from 'element-plus'
import http from '../../../core/api/http'
import { useAuthStore } from '../../../core/stores/auth'

type Member = {
  id: number
  phone: string
  name: string
  face_status: string
  merchant_ids: number[]
  avatar_url?: string | null
  acquisition_source?: string
  first_merchant_id?: number | null
  first_merchant_name?: string | null
  created_at?: string
  has_password?: boolean
  referrer_member_id?: number | null
  referrer_note?: string | null
  referral_code?: string | null
  referrer_display?: string | null
  referred_count?: number
}
type Merchant = { id: number; name: string }
type Page<T> = { items: T[]; total: number; page: number; page_size: number }
type ImportError = { row: number; phone?: string | null; name?: string | null; message: string }
type ImportResult = {
  merchant_id: number
  merchant_name: string
  total_rows: number
  created: number
  linked: number
  skipped: number
  failed: number
  errors: ImportError[]
}

const auth = useAuthStore()
const router = useRouter()
const isSiteAdmin = computed(() => auth.isSiteAdmin())
const canWrite = computed(
  () =>
    (auth.me?.permissions || []).includes('member:write') ||
    (auth.me?.permissions || []).includes('*'),
)
const canPromote = computed(() => {
  const perms = auth.me?.permissions || []
  return perms.includes('promoter:read') || perms.includes('promoter:manage') || perms.includes('*')
})
const canResetPassword = computed(() => {
  const perms = auth.me?.permissions || []
  const roles = auth.me?.role_codes || []
  return roles.includes('site_admin') || perms.includes('staff:manage') || perms.includes('*')
})

const members = ref<Member[]>([])
const merchants = ref<Merchant[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({
  q: '',
  merchant_id: undefined as number | undefined,
  face_status: '' as string,
  has_password: '' as '' | 'true' | 'false',
  has_referrer: '' as '' | 'true' | 'false',
  referral_code: '',
})

const createDialog = ref(false)
const importDialog = ref(false)
const importing = ref(false)
const downloadingTemplate = ref(false)
const importMerchantId = ref<number | undefined>(undefined)
const importFileName = ref('')
const importResult = ref<ImportResult | null>(null)
const linkDialog = ref(false)
const editDialog = ref(false)
const detailVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const linkFormRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()
const pwdFormRef = ref<FormInstance>()

const form = reactive({
  phone: '',
  name: '',
  merchant_id: undefined as number | undefined,
  password: '',
  confirm: '',
  referrer_type: '' as '' | 'member' | 'note',
  referrer_member_id: undefined as number | undefined,
  referrer_note: '',
  referral_code: '',
})
const linkForm = reactive({ merchant_id: undefined as number | undefined })
const editForm = reactive({
  name: '',
  password: '',
  referrer_type: '' as '' | 'member' | 'note',
  referrer_member_id: undefined as number | undefined,
  referrer_note: '',
})
const pwdForm = reactive({ password: '', confirm: '' })
const linkTarget = ref<Member | null>(null)
const editTarget = ref<Member | null>(null)
const pwdTarget = ref<Member | null>(null)
const pwdVisible = ref(false)
const detail = ref<Member | null>(null)
const uploadingAvatar = ref(false)

const rules: FormRules = {
  phone: [{ required: true, message: '请填写手机号', trigger: 'blur' }],
  name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
  merchant_id: [{ required: true, message: '请选择商户', trigger: 'change' }],
  password: [{ min: 6, message: '密码至少 6 位', trigger: 'blur' }],
  confirm: [
    {
      validator: (_rule, value, callback) => {
        if (form.password && value !== form.password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

const linkRules: FormRules = {
  merchant_id: [{ required: true, message: '请选择目标商户', trigger: 'change' }],
}

const editRules: FormRules = {
  name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
}

const pwdRules: FormRules = {
  password: [
    { required: true, message: '请填写新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== pwdForm.password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

function merchantName(id: number) {
  return merchants.value.find((m) => m.id === id)?.name || `#${id}`
}

function faceLabel(status: string) {
  return { enrolled: '已录入', not_enrolled: '未录入', pending: '待审核' }[status] || status
}

function sourceLabel(row: Member) {
  if (row.acquisition_source === 'merchant') {
    return row.first_merchant_name || merchantName(row.first_merchant_id || 0) || '商户获客'
  }
  return '综合运营平台'
}

async function load() {
  loading.value = true
  try {
    const [m, ms] = await Promise.all([
      http.get<Page<Member>>('/members', {
        params: {
          page: page.value,
          page_size: pageSize.value,
          q: query.q.trim() || undefined,
          merchant_id: query.merchant_id,
          face_status: query.face_status || undefined,
          has_password: query.has_password === '' ? undefined : query.has_password === 'true',
          has_referrer: query.has_referrer === '' ? undefined : query.has_referrer === 'true',
          referral_code: query.referral_code.trim() || undefined,
        },
      }),
      http.get('/merchants'),
    ])
    members.value = m.data.items
    total.value = m.data.total
    merchants.value = ms.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function resetSearch() {
  query.q = ''
  query.merchant_id = undefined
  query.face_status = ''
  query.has_password = ''
  query.has_referrer = ''
  query.referral_code = ''
  page.value = 1
  void load()
}

/** 推荐人下拉：只选推广会员 */
const referrerCandidates = ref<Member[]>([])
const referrerLoading = ref(false)

async function searchReferrerMembers(keyword: string) {
  referrerLoading.value = true
  try {
    const { data } = await http.get<Page<Member>>('/members', {
      params: { page: 1, page_size: 20, q: keyword.trim() || undefined },
    })
    referrerCandidates.value = data.items
  } catch {
    referrerCandidates.value = []
  } finally {
    referrerLoading.value = false
  }
}

function goPromotion(row: Member) {
  router.push({
    path: '/platform/promotion-settings',
    query: { member_id: String(row.id) },
  })
}

function referrerText(row: Member) {
  if (row.referrer_display) return row.referrer_display
  if (row.referral_code) return `推广码 ${row.referral_code}`
  return '—'
}

function openImport() {
  importMerchantId.value = isSiteAdmin.value ? merchants.value[0]?.id : (auth.me?.merchant_id ?? merchants.value[0]?.id)
  importFileName.value = ''
  importResult.value = null
  importDialog.value = true
}

async function downloadTemplate() {
  downloadingTemplate.value = true
  try {
    const { data } = await http.get<Blob>('/members/import-template', { responseType: 'blob' })
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = '商户会员导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '模板下载失败')
  } finally {
    downloadingTemplate.value = false
  }
}

async function uploadImport(opt: UploadRequestOptions) {
  if (isSiteAdmin.value && !importMerchantId.value) {
    ElMessage.warning('请先选择要导入到的商户')
    return
  }
  const fd = new FormData()
  fd.append('file', opt.file)
  importing.value = true
  importResult.value = null
  importFileName.value = opt.file.name
  try {
    const { data } = await http.post<ImportResult>('/members/import', fd, {
      params: isSiteAdmin.value ? { merchant_id: importMerchantId.value } : undefined,
      timeout: 60000,
    })
    importResult.value = data
    opt.onSuccess(data)
    if (data.failed && !data.created && !data.linked && !data.skipped) {
      ElMessage.warning('没有成功导入的行，请检查表格')
    } else {
      ElMessage.success(`已导入到「${data.merchant_name}」：新增 ${data.created}，挂靠 ${data.linked}`)
      await load()
    }
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  } finally {
    importing.value = false
  }
}

function openCreate() {
  form.phone = ''
  form.name = ''
  form.merchant_id = merchants.value[0]?.id
  form.password = ''
  form.confirm = ''
  form.referrer_type = ''
  form.referrer_member_id = undefined
  form.referrer_note = ''
  form.referral_code = ''
  referrerCandidates.value = []
  formRef.value?.clearValidate()
  createDialog.value = true
}

/** 推荐来源：会员推广 / 登记姓名 */
function referrerPayload(src: {
  referrer_type: '' | 'member' | 'note'
  referrer_member_id?: number
  referrer_note: string
}) {
  return {
    referrer_member_id: src.referrer_type === 'member' ? (src.referrer_member_id ?? null) : null,
    referrer_note: src.referrer_type === 'note' ? src.referrer_note.trim() || null : null,
  }
}

async function create() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/members', {
      phone: form.phone.trim(),
      name: form.name.trim(),
      merchant_id: form.merchant_id,
      ...referrerPayload(form),
      referral_code: form.referral_code.trim().toUpperCase() || null,
      ...(canResetPassword.value && form.password ? { password: form.password } : {}),
    })
    ElMessage.success('会员已创建')
    createDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openDetail(row: Member) {
  detail.value = row
  detailVisible.value = true
}

async function uploadAvatar(opt: UploadRequestOptions, target?: Member | null) {
  const row = target || editTarget.value || detail.value
  if (!row) return
  const fd = new FormData()
  fd.append('file', opt.file)
  uploadingAvatar.value = true
  try {
    const { data } = await http.post<Member>(`/members/${row.id}/avatar`, fd, { timeout: 30000 })
    opt.onSuccess(data)
    ElMessage.success('头像已更新')
    if (editTarget.value?.id === data.id) editTarget.value = data
    if (detail.value?.id === data.id) detail.value = data
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '头像上传失败')
  } finally {
    uploadingAvatar.value = false
  }
}

async function clearAvatar(row: Member) {
  uploadingAvatar.value = true
  try {
    const { data } = await http.delete<Member>(`/members/${row.id}/avatar`)
    ElMessage.success('已清除头像')
    if (editTarget.value?.id === data.id) editTarget.value = data
    if (detail.value?.id === data.id) detail.value = data
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '清除失败')
  } finally {
    uploadingAvatar.value = false
  }
}

function openEdit(row: Member) {
  editTarget.value = row
  editForm.name = row.name
  editForm.password = ''
  editForm.referrer_member_id = row.referrer_member_id ?? undefined
  editForm.referrer_note = row.referrer_note ?? ''
  editForm.referrer_type = row.referrer_member_id ? 'member' : row.referrer_note ? 'note' : ''
  referrerCandidates.value = row.referrer_member_id
    ? [{ id: row.referrer_member_id, phone: '', name: row.referrer_display || `#${row.referrer_member_id}` } as Member]
    : []
  editFormRef.value?.clearValidate()
  editDialog.value = true
}

async function saveEdit() {
  if (!editTarget.value) return
  const ok = await editFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (canResetPassword.value && editForm.password && editForm.password.length < 6) {
    ElMessage.error('密码至少 6 位')
    return
  }
  submitting.value = true
  try {
    const { data } = await http.patch<Member>(`/members/${editTarget.value.id}`, {
      name: editForm.name.trim(),
      ...referrerPayload(editForm),
    })
    if (canResetPassword.value && editForm.password) {
      await http.post(`/members/${editTarget.value.id}/password`, { password: editForm.password })
      data.has_password = true
    }
    ElMessage.success('已保存')
    editDialog.value = false
    if (detail.value?.id === data.id) detail.value = data
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

function openLink(row: Member) {
  linkTarget.value = row
  linkForm.merchant_id = merchants.value.find((m) => !row.merchant_ids.includes(m.id))?.id
  linkFormRef.value?.clearValidate()
  linkDialog.value = true
}

async function link() {
  if (!linkTarget.value) return
  const ok = await linkFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post(`/members/${linkTarget.value.id}/merchants`, { merchant_id: linkForm.merchant_id })
    ElMessage.success(`已关联到「${merchantName(linkForm.merchant_id!)}」`)
    linkDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '关联失败')
  } finally {
    submitting.value = false
  }
}

function openResetPwd(row: Member) {
  pwdTarget.value = row
  pwdForm.password = ''
  pwdForm.confirm = ''
  pwdFormRef.value?.clearValidate()
  pwdVisible.value = true
}

async function saveResetPwd() {
  if (!pwdTarget.value) return
  const ok = await pwdFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post(`/members/${pwdTarget.value.id}/password`, { password: pwdForm.password })
    ElMessage.success(`已重置「${pwdTarget.value.name || pwdTarget.value.phone}」的登录密码`)
    pwdVisible.value = false
    if (detail.value?.id === pwdTarget.value.id) {
      detail.value = { ...detail.value, has_password: true }
    }
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '改密失败')
  } finally {
    submitting.value = false
  }
}

async function remove(row: Member) {
  try {
    await ElMessageBox.confirm(
      `确认删除会员「${row.name || row.phone || `#${row.id}`}」？删除后不可恢复。`,
      '删除会员',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await http.delete(`/members/${row.id}`)
    ElMessage.success('已删除')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>会员档案</h3>
      <div v-if="canWrite" class="toolbar-actions">
        <el-button :loading="downloadingTemplate" @click="downloadTemplate">下载导入模板</el-button>
        <el-button @click="openImport">导入会员</el-button>
        <el-button type="primary" @click="openCreate">创建会员</el-button>
      </div>
    </div>

    <div class="filters">
      <el-input
        v-model="query.q"
        clearable
        placeholder="手机号 / 姓名"
        style="width: 200px"
        @keyup.enter="search"
      />
      <el-select v-model="query.merchant_id" clearable placeholder="关联商户" style="width: 180px">
        <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-select v-model="query.face_status" clearable placeholder="人脸状态" style="width: 130px">
        <el-option label="已录入" value="enrolled" />
        <el-option label="未录入" value="not_enrolled" />
      </el-select>
      <el-select v-model="query.has_password" clearable placeholder="登录密码" style="width: 130px">
        <el-option label="已设置" value="true" />
        <el-option label="未设置" value="false" />
      </el-select>
      <el-select v-model="query.has_referrer" clearable placeholder="推荐关系" style="width: 130px">
        <el-option label="有推荐人" value="true" />
        <el-option label="无推荐人" value="false" />
      </el-select>
      <el-input
        v-model="query.referral_code"
        clearable
        placeholder="推广码"
        style="width: 130px"
        @keyup.enter="search"
      />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="members" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="头像" width="76">
        <template #default="{ row }">
          <img v-if="row.avatar_url" class="avatar" :src="row.avatar_url" alt="" />
          <div v-else class="avatar avatar-fallback">{{ (row.name || '?').slice(0, 1) }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="phone" label="手机号" />
      <el-table-column prop="name" label="姓名" />
      <el-table-column label="登录密码" width="110">
        <template #default="{ row }">
          <el-tag :type="row.has_password ? 'success' : 'info'" size="small">
            {{ row.has_password ? '已设置' : '未设置' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="人脸状态" width="120">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="row.face_status === 'enrolled' ? 'success' : row.face_status === 'pending' ? 'warning' : 'info'"
          >
            {{ faceLabel(row.face_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="首次来源" min-width="140">
        <template #default="{ row }">{{ sourceLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="推荐人" min-width="160">
        <template #default="{ row }">
          <div>{{ referrerText(row) }}</div>
          <div v-if="row.referred_count" class="sub">已推荐 {{ row.referred_count }} 人</div>
        </template>
      </el-table-column>
      <el-table-column label="关联商户">
        <template #default="{ row }">
          <el-tag
            v-for="id in row.merchant_ids"
            :key="id"
            size="small"
            effect="plain"
            style="margin-right: 6px"
          >
            {{ merchantName(id) }}
          </el-tag>
          <span v-if="!row.merchant_ids.length">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="340" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="canWrite" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="canPromote" link type="primary" @click="goPromotion(row)">推广</el-button>
          <el-button v-if="canResetPassword" link type="primary" @click="openResetPwd(row)">改密</el-button>
          <el-button v-if="canWrite" link type="primary" @click="openLink(row)">关联商户</el-button>
          <el-button v-if="canWrite" link type="danger" @click="remove(row)">删除</el-button>
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
        @current-change="load"
        @size-change="
          () => {
            page = 1
            load()
          }
        "
      />
    </div>

    <el-drawer v-model="detailVisible" title="会员详情" size="420px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="头像">
            <img v-if="detail.avatar_url" class="detail-avatar" :src="detail.avatar_url" alt="" />
            <div v-else class="detail-avatar avatar-fallback">{{ (detail.name || '?').slice(0, 1) }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detail.phone }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="人脸">{{ faceLabel(detail.face_status) }}</el-descriptions-item>
          <el-descriptions-item label="登录密码">
            {{ detail.has_password ? '已设置' : '未设置（仅可用验证码登录）' }}
          </el-descriptions-item>
          <el-descriptions-item label="首次来源">{{ sourceLabel(detail) }}</el-descriptions-item>
          <el-descriptions-item label="推荐人">{{ referrerText(detail) }}</el-descriptions-item>
          <el-descriptions-item label="推广码">{{ detail.referral_code || '—' }}</el-descriptions-item>
          <el-descriptions-item label="累计推荐">{{ detail.referred_count ?? 0 }} 人</el-descriptions-item>
          <el-descriptions-item label="关联商户">
            <template v-if="detail.merchant_ids.length">
              <el-tag
                v-for="id in detail.merchant_ids"
                :key="id"
                size="small"
                style="margin-right: 6px"
              >
                {{ merchantName(id) }}
              </el-tag>
            </template>
            <span v-else>—</span>
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="canWrite || canResetPassword || canPromote" class="drawer-actions">
          <el-button v-if="canWrite" type="primary" @click="openEdit(detail)">编辑</el-button>
          <el-button v-if="canPromote" plain @click="goPromotion(detail)">推广配置</el-button>
          <el-button v-if="canResetPassword" type="warning" plain @click="openResetPwd(detail)">
            修改密码
          </el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="importDialog" title="导入商户会员" width="620px" destroy-on-close>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 14px"
        title="请先下载模板，按「手机号 / 姓名」填写后上传。导入会员将挂靠到所选商户。"
      />
      <el-form label-width="90px">
        <el-form-item v-if="isSiteAdmin" label="导入到">
          <el-select v-model="importMerchantId" style="width: 100%" placeholder="选择商户">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="导入到">
          <span>{{ merchants[0]?.name || '当前商户' }}</span>
        </el-form-item>
        <el-form-item label="Excel">
          <el-upload
            :show-file-list="false"
            accept=".xlsx"
            :disabled="importing"
            :http-request="uploadImport"
          >
            <el-button :loading="importing">选择 .xlsx 文件</el-button>
          </el-upload>
          <p v-if="importFileName" class="hint">已选择：{{ importFileName }}</p>
        </el-form-item>
      </el-form>
      <div v-if="importResult" class="import-result">
        <p>
          「{{ importResult.merchant_name }}」共处理 {{ importResult.total_rows }} 行：新增
          {{ importResult.created }}，挂靠已有会员 {{ importResult.linked }}，本店已存在
          {{ importResult.skipped }}，失败 {{ importResult.failed }}
        </p>
        <el-table v-if="importResult.errors.length" :data="importResult.errors" size="small" max-height="240">
          <el-table-column prop="row" label="行" width="70" />
          <el-table-column prop="phone" label="手机号" width="130" />
          <el-table-column prop="name" label="姓名" width="120" />
          <el-table-column prop="message" label="原因" />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="downloadTemplate" :loading="downloadingTemplate">下载模板</el-button>
        <el-button type="primary" @click="importDialog = false">完成</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createDialog" title="创建会员" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="会员手机号，必填" maxlength="32" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="会员姓名，必填" maxlength="128" />
        </el-form-item>
        <el-form-item label="商户" prop="merchant_id">
          <el-select v-model="form.merchant_id" style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="推荐来源">
          <el-select v-model="form.referrer_type" clearable placeholder="无推荐人" style="width: 100%">
            <el-option label="会员推广" value="member" />
            <el-option label="登记姓名" value="note" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.referrer_type === 'member'" label="推广会员">
          <el-select
            v-model="form.referrer_member_id"
            filterable
            remote
            :remote-method="searchReferrerMembers"
            :loading="referrerLoading"
            placeholder="输入手机号或姓名搜索"
            style="width: 100%"
          >
            <el-option
              v-for="x in referrerCandidates"
              :key="x.id"
              :label="`${x.name} ${x.phone}`"
              :value="x.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.referrer_type === 'note'" label="推荐人姓名">
          <el-input v-model="form.referrer_note" maxlength="128" placeholder="仅登记，不参与返点结算" />
        </el-form-item>
        <el-form-item label="推广码">
          <el-input v-model="form.referral_code" maxlength="32" placeholder="选填，扫码注册会自动写入" />
        </el-form-item>
        <template v-if="canResetPassword">
          <el-form-item label="登录密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              maxlength="64"
              placeholder="选填，至少 6 位；不填则仅验证码登录"
            />
          </el-form-item>
          <el-form-item v-if="form.password" label="确认密码" prop="confirm">
            <el-input v-model="form.confirm" type="password" show-password maxlength="64" placeholder="再次输入密码" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialog" title="编辑会员" width="420px" destroy-on-close>
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="80px">
        <el-form-item label="头像">
          <div class="avatar-edit">
            <img v-if="editTarget?.avatar_url" class="detail-avatar" :src="editTarget.avatar_url" alt="" />
            <div v-else class="detail-avatar avatar-fallback">{{ (editForm.name || '?').slice(0, 1) }}</div>
            <div>
              <el-upload :show-file-list="false" accept="image/jpeg,image/png,image/webp" :http-request="uploadAvatar">
                <el-button :loading="uploadingAvatar">上传头像</el-button>
              </el-upload>
              <el-button
                v-if="editTarget?.avatar_url"
                link
                type="danger"
                :disabled="uploadingAvatar"
                @click="editTarget && clearAvatar(editTarget)"
              >
                清除
              </el-button>
              <p class="hint">JPG / PNG / WEBP，不超过 8MB。会员也可在 H5 / 小程序自行更换。</p>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="editForm.name" maxlength="128" />
        </el-form-item>
        <el-form-item label="推荐来源">
          <el-select v-model="editForm.referrer_type" clearable placeholder="无推荐人" style="width: 100%">
            <el-option label="会员推广" value="member" />
            <el-option label="登记姓名" value="note" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editForm.referrer_type === 'member'" label="推广会员">
          <el-select
            v-model="editForm.referrer_member_id"
            filterable
            remote
            :remote-method="searchReferrerMembers"
            :loading="referrerLoading"
            placeholder="输入手机号或姓名搜索"
            style="width: 100%"
          >
            <el-option
              v-for="x in referrerCandidates"
              :key="x.id"
              :label="x.phone ? `${x.name} ${x.phone}` : x.name"
              :value="x.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editForm.referrer_type === 'note'" label="推荐人姓名">
          <el-input v-model="editForm.referrer_note" maxlength="128" placeholder="仅登记，不参与返点结算" />
        </el-form-item>
        <el-form-item v-if="editTarget?.referral_code" label="推广码">
          <el-input :model-value="editTarget?.referral_code" disabled />
        </el-form-item>
        <el-form-item v-if="canResetPassword" label="新密码">
          <el-input
            v-model="editForm.password"
            type="password"
            show-password
            maxlength="64"
            placeholder="留空不修改"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="linkDialog"
      :title="`关联商户 · ${linkTarget ? linkTarget.name || linkTarget.phone : ''}`"
      width="460px"
      destroy-on-close
    >
      <el-alert
        v-if="linkTarget"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 14px"
        title="关联后该会员可访问对应商户的权益与门禁授权"
      />
      <el-form ref="linkFormRef" :model="linkForm" :rules="linkRules" label-width="80px">
        <el-form-item label="目标商户" prop="merchant_id">
          <el-select v-model="linkForm.merchant_id" style="width: 100%" placeholder="请选择要关联到的商户">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="linkDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="link">确认关联</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="pwdVisible"
      :title="`修改密码 · ${pwdTarget?.name || pwdTarget?.phone || ''}`"
      width="440px"
      destroy-on-close
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 14px"
        :title="pwdTarget?.has_password ? '重置后会员需使用新密码登录 H5 / 小程序。' : '设置后会员可用手机号+密码登录，验证码登录仍然可用。'"
      />
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="90px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="pwdForm.password" type="password" show-password maxlength="64" placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input v-model="pwdForm.confirm" type="password" show-password maxlength="64" placeholder="再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveResetPwd">确认改密</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.toolbar h3 {
  margin: 0;
  font-size: 1.1rem;
}
.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.import-result {
  margin-top: 8px;
}
.import-result p {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.drawer-actions {
  margin-top: 16px;
}
.sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.avatar,
.detail-avatar {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 50%;
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
.avatar-edit {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
</style>
