<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules, type UploadRequestOptions } from 'element-plus'
import http from '../../../core/api/http'
import { BUSINESS_SYSTEM_OPTIONS, defaultSubsystemsForTypeCode } from '../../../core/nav/systems'
import { merchantStatusLabel } from '../../../core/labels'
import { useAuthStore } from '../../../core/stores/auth'

type MerchantType = { id: number; code: string; name: string }
type Contact = {
  name: string
  phone: string
  title: string
  kind: 'primary' | 'emergency' | 'other'
  remark: string
}
type Merchant = {
  id: number
  name: string
  status: string
  merchant_type_id: number
  subsystem_codes: string[]
  legal_name?: string | null
  credit_code?: string | null
  license_no?: string | null
  license_image_url?: string | null
  legal_person?: string | null
  registered_address?: string | null
  business_address?: string | null
  contact_phone?: string | null
  contact_email?: string | null
  business_hours?: string | null
  description?: string | null
  contacts?: Array<Contact & { id?: number }>
  has_license?: boolean
  emergency_contact_count?: number
  lease_starts_on?: string | null
  lease_ends_on?: string | null
  lease_days_total?: number | null
  lease_days_remaining?: number | null
  lease_progress?: number | null
  lease_state?: 'unset' | 'not_started' | 'active' | 'expiring' | 'expired'
}

const auth = useAuthStore()
const isSiteAdmin = computed(() => auth.isSiteAdmin())
const canEditProfile = computed(
  () => isSiteAdmin.value || (auth.me?.permissions || []).includes('staff:manage') || (auth.me?.permissions || []).includes('*'),
)

const types = ref<MerchantType[]>([])
const merchants = ref<Merchant[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({
  q: '',
  merchant_type_id: undefined as number | undefined,
  status: '' as string,
  lease_state: '' as string,
})
const filteredMerchants = computed(() => {
  const kw = query.q.trim()
  return merchants.value.filter((row) => {
    if (kw && !row.name.includes(kw) && !String(row.id).includes(kw) && !(row.legal_name || '').includes(kw)) return false
    if (query.merchant_type_id != null && row.merchant_type_id !== query.merchant_type_id) return false
    if (query.status && row.status !== query.status) return false
    if (query.lease_state && (row.lease_state || 'unset') !== query.lease_state) return false
    return true
  })
})
const pagedMerchants = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredMerchants.value.slice(start, start + pageSize.value)
})
const merchantDialog = ref(false)
const detailVisible = ref(false)
const submitting = ref(false)
const uploading = ref(false)
const merchantFormRef = ref<FormInstance>()
const editingId = ref<number | null>(null)
const detail = ref<Merchant | null>(null)
const activeTab = ref('base')

function emptyContact(kind: Contact['kind'] = 'emergency'): Contact {
  return { name: '', phone: '', title: '', kind, remark: '' }
}

const merchantForm = reactive({
  merchant_type_id: undefined as number | undefined,
  name: '',
  status: 'active',
  subsystem_codes: ['gym'] as string[],
  legal_name: '',
  credit_code: '',
  license_no: '',
  license_image_url: '',
  legal_person: '',
  registered_address: '',
  business_address: '',
  contact_phone: '',
  contact_email: '',
  business_hours: '',
  description: '',
  lease_starts_on: '',
  lease_ends_on: '',
  contacts: [emptyContact('primary'), emptyContact('emergency')] as Contact[],
})

const leaseRange = computed({
  get() {
    if (!merchantForm.lease_starts_on && !merchantForm.lease_ends_on) return null
    return [merchantForm.lease_starts_on, merchantForm.lease_ends_on] as [string, string]
  },
  set(value: [string, string] | null) {
    merchantForm.lease_starts_on = value?.[0] || ''
    merchantForm.lease_ends_on = value?.[1] || ''
  },
})

const merchantRules: FormRules = {
  merchant_type_id: [{ required: true, message: '请选择商户类型', trigger: 'change' }],
  name: [{ required: true, message: '请填写商户名称', trigger: 'blur' }],
  subsystem_codes: [{ type: 'array', required: true, min: 1, message: '请至少关联一个业态子系统', trigger: 'change' }],
  credit_code: [
    {
      validator: (_rule, value, callback) => {
        const v = String(value || '').trim()
        if (!v) return callback()
        if (!/^[0-9A-Za-z]{18}$/.test(v)) callback(new Error('统一社会信用代码应为 18 位'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

const kindOptions = [
  { value: 'primary', label: '主联系人' },
  { value: 'emergency', label: '紧急联系人' },
  { value: 'other', label: '其他' },
]

function kindLabel(kind: string) {
  return kindOptions.find((o) => o.value === kind)?.label || kind
}

function typeName(id: number) {
  return types.value.find((t) => t.id === id)?.name || `#${id}`
}

function primaryContact(row: Merchant) {
  const list = row.contacts || []
  return list.find((c) => c.kind === 'primary') || list[0] || null
}

function leaseRemainText(row: Merchant) {
  const remaining = row.lease_days_remaining
  switch (row.lease_state) {
    case 'not_started':
      return '未起租'
    case 'active':
      return `剩余 ${remaining ?? '—'} 天`
    case 'expiring':
      return `即将到期 · 剩余 ${remaining ?? 0} 天`
    case 'expired':
      return `已过期 ${Math.abs(remaining ?? 0)} 天`
    default:
      return '未设置租期'
  }
}

async function load() {
  loading.value = true
  try {
    const [t, m] = await Promise.all([http.get('/merchant-types'), http.get('/merchants')])
    types.value = t.data
    merchants.value = m.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

watch(query, () => {
  page.value = 1
}, { deep: true })

function onTypeChange(typeId: number) {
  const t = types.value.find((x) => x.id === typeId)
  if (t && !editingId.value) merchantForm.subsystem_codes = defaultSubsystemsForTypeCode(t.code)
}

function fillForm(row?: Merchant) {
  merchantForm.name = row?.name || ''
  merchantForm.status = row?.status || 'active'
  merchantForm.merchant_type_id = row?.merchant_type_id ?? types.value[0]?.id
  merchantForm.subsystem_codes = row
    ? [...(row.subsystem_codes || [])]
    : defaultSubsystemsForTypeCode(types.value.find((x) => x.id === merchantForm.merchant_type_id)?.code || 'gym')
  merchantForm.legal_name = row?.legal_name || ''
  merchantForm.credit_code = row?.credit_code || ''
  merchantForm.license_no = row?.license_no || ''
  merchantForm.license_image_url = row?.license_image_url || ''
  merchantForm.legal_person = row?.legal_person || ''
  merchantForm.registered_address = row?.registered_address || ''
  merchantForm.business_address = row?.business_address || ''
  merchantForm.contact_phone = row?.contact_phone || ''
  merchantForm.contact_email = row?.contact_email || ''
  merchantForm.business_hours = row?.business_hours || ''
  merchantForm.description = row?.description || ''
  merchantForm.lease_starts_on = row?.lease_starts_on || ''
  merchantForm.lease_ends_on = row?.lease_ends_on || ''
  merchantForm.contacts = (row?.contacts || []).map((c) => ({
    name: c.name,
    phone: c.phone,
    title: c.title || '',
    kind: c.kind,
    remark: c.remark || '',
  }))
  if (!merchantForm.contacts.length) {
    merchantForm.contacts = [emptyContact('primary'), emptyContact('emergency')]
  }
}

function openMerchantDialog(row?: Merchant) {
  editingId.value = row?.id ?? null
  activeTab.value = 'base'
  fillForm(row)
  merchantFormRef.value?.clearValidate()
  merchantDialog.value = true
}

function openDetail(row: Merchant) {
  detail.value = row
  detailVisible.value = true
}

function addContact(kind: Contact['kind'] = 'emergency') {
  merchantForm.contacts.push(emptyContact(kind))
}

function removeContact(index: number) {
  merchantForm.contacts.splice(index, 1)
  if (!merchantForm.contacts.length) merchantForm.contacts.push(emptyContact('primary'))
}

async function uploadLicense(opt: UploadRequestOptions) {
  const fd = new FormData()
  fd.append('file', opt.file)
  uploading.value = true
  try {
    const { data } = await http.post<{ url: string }>('/uploads', fd, { timeout: 30000 })
    merchantForm.license_image_url = data.url
    opt.onSuccess(data)
    ElMessage.success('执照已上传')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

function clearLicense() {
  merchantForm.license_image_url = ''
}

function isImageUrl(url: string) {
  return /\.(png|jpe?g|webp)(\?|$)/i.test(url)
}

async function saveMerchant() {
  const ok = await merchantFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (isSiteAdmin.value && !merchantForm.subsystem_codes.length) {
    ElMessage.warning('请至少关联一个业态子系统')
    return
  }
  const contacts = merchantForm.contacts
    .map((c, index) => ({
      name: c.name.trim(),
      phone: c.phone.trim(),
      title: c.title.trim() || null,
      kind: c.kind,
      remark: c.remark.trim() || null,
      sort_order: index,
    }))
    .filter((c) => c.name && c.phone)
  if (merchantForm.contacts.some((c) => (c.name.trim() && !c.phone.trim()) || (!c.name.trim() && c.phone.trim()))) {
    ElMessage.warning('联系人需同时填写姓名与电话')
    activeTab.value = 'contacts'
    return
  }
  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      name: merchantForm.name.trim(),
      legal_name: merchantForm.legal_name.trim() || null,
      credit_code: merchantForm.credit_code.trim() || null,
      license_no: merchantForm.license_no.trim() || null,
      license_image_url: merchantForm.license_image_url.trim() || null,
      legal_person: merchantForm.legal_person.trim() || null,
      registered_address: merchantForm.registered_address.trim() || null,
      business_address: merchantForm.business_address.trim() || null,
      contact_phone: merchantForm.contact_phone.trim() || null,
      contact_email: merchantForm.contact_email.trim() || null,
      business_hours: merchantForm.business_hours.trim() || null,
      description: merchantForm.description.trim() || null,
      contacts,
    }
    if (isSiteAdmin.value) {
      payload.merchant_type_id = merchantForm.merchant_type_id
      payload.status = merchantForm.status
      payload.subsystem_codes = merchantForm.subsystem_codes
      payload.lease_starts_on = merchantForm.lease_starts_on || null
      payload.lease_ends_on = merchantForm.lease_ends_on || null
    }
    if (editingId.value) await http.patch(`/merchants/${editingId.value}`, payload)
    else await http.post('/merchants', payload)
    ElMessage.success(editingId.value ? '商户档案已更新' : '已创建商户')
    merchantDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function setStatus(row: Merchant, status: string) {
  try {
    await http.patch(`/merchants/${row.id}`, { status })
    ElMessage.success(status === 'active' ? '商户已启用' : '商户已停用')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

const qrDialog = ref(false)
const qrMerchant = ref<Merchant | null>(null)
const qrUrl = ref('')
const qrDataUrl = ref('')
const qrLoading = ref(false)

async function openQr(row: Merchant) {
  qrMerchant.value = row
  qrUrl.value = ''
  qrDataUrl.value = ''
  qrDialog.value = true
  qrLoading.value = true
  try {
    const { data } = await http.get<{ merchant_id: number; url: string }>(
      `/merchants/${row.id}/acquisition-link`,
    )
    qrUrl.value = data.url
    const QRCode = (await import('qrcode')).default
    qrDataUrl.value = await QRCode.toDataURL(data.url, { width: 240, margin: 2 })
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载获客码失败')
    qrDialog.value = false
  } finally {
    qrLoading.value = false
  }
}

async function copyQrUrl() {
  if (!qrUrl.value) return
  try {
    await navigator.clipboard.writeText(qrUrl.value)
    ElMessage.success('链接已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择链接')
  }
}

function downloadQr() {
  if (!qrDataUrl.value || !qrMerchant.value) return
  const a = document.createElement('a')
  a.href = qrDataUrl.value
  a.download = `获客码-${qrMerchant.value.name}.png`
  a.click()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>商户组织</h3>
      <el-button v-if="isSiteAdmin" type="primary" @click="openMerchantDialog()">新增商户</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="名称 / ID / 企业名" style="width: 200px" @keyup.enter="page = 1" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="query.merchant_type_id" clearable placeholder="全部" style="width: 140px" @change="page = 1">
          <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px" @change="page = 1">
          <el-option label="营业中" value="active" />
          <el-option label="筹备中" value="preparing" />
          <el-option label="已停用" value="disabled" />
        </el-select>
      </el-form-item>
      <el-form-item label="租期">
        <el-select v-model="query.lease_state" clearable placeholder="全部" style="width: 130px" @change="page = 1">
          <el-option label="未设置" value="unset" />
          <el-option label="未起租" value="not_started" />
          <el-option label="租期内" value="active" />
          <el-option label="即将到期" value="expiring" />
          <el-option label="已过期" value="expired" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button
          @click="
            () => {
              query.q = ''
              query.merchant_type_id = undefined
              query.status = ''
              query.lease_state = ''
              page = 1
            }
          "
        >
          重置
        </el-button>
      </el-form-item>
    </el-form>

    <el-table :data="pagedMerchants" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">{{ typeName(row.merchant_type_id) }}</template>
      </el-table-column>
      <el-table-column label="执照" width="90">
        <template #default="{ row }">
          <el-tag :type="row.has_license ? 'success' : 'info'" size="small">
            {{ row.has_license ? '已录入' : '待补' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="主联系人" min-width="150">
        <template #default="{ row }">
          <template v-if="primaryContact(row)">
            {{ primaryContact(row)?.name }}
            <span class="muted">{{ primaryContact(row)?.phone }}</span>
          </template>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="紧急联系人" width="110">
        <template #default="{ row }">{{ row.emergency_contact_count || 0 }} 人</template>
      </el-table-column>
      <el-table-column label="租赁有效期" min-width="220">
        <template #default="{ row }">
          <div class="lease-cell" :class="'is-' + (row.lease_state || 'unset')">
            <div class="lease-remain">{{ leaseRemainText(row) }}</div>
            <div v-if="row.lease_progress != null" class="lease-track" aria-hidden="true">
              <div class="lease-fill" :style="{ width: `${row.lease_progress}%` }" />
            </div>
            <div class="lease-dates">
              <span>{{ row.lease_starts_on || '—' }}</span>
              <span>{{ row.lease_ends_on || '—' }}</span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : row.status === 'preparing' ? 'warning' : 'info'" size="small">
            {{ merchantStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="canEditProfile" link type="primary" @click="openMerchantDialog(row)">编辑</el-button>
          <el-button link type="primary" @click="openQr(row)">获客码</el-button>
          <el-button
            v-if="isSiteAdmin && row.status !== 'active'"
            link
            type="success"
            @click="setStatus(row, 'active')"
          >
            启用
          </el-button>
          <el-button
            v-if="isSiteAdmin && row.status === 'active'"
            link
            type="danger"
            @click="setStatus(row, 'disabled')"
          >
            停用
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="filteredMerchants.length"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
      />
    </div>

    <el-drawer v-model="detailVisible" :title="detail ? `商户档案 · ${detail.name}` : '商户档案'" size="480px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="品牌名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeName(detail.merchant_type_id) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ merchantStatusLabel(detail.status) }}</el-descriptions-item>
          <el-descriptions-item label="租赁有效期">
            <div class="lease-cell" :class="'is-' + (detail.lease_state || 'unset')">
              <div class="lease-remain">{{ leaseRemainText(detail) }}</div>
              <div v-if="detail.lease_progress != null" class="lease-track" aria-hidden="true">
                <div class="lease-fill" :style="{ width: `${detail.lease_progress}%` }" />
              </div>
              <div class="lease-dates">
                <span>{{ detail.lease_starts_on || '—' }}</span>
                <span>{{ detail.lease_ends_on || '—' }}</span>
              </div>
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="企业名称">{{ detail.legal_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="统一社会信用代码">{{ detail.credit_code || '—' }}</el-descriptions-item>
          <el-descriptions-item label="营业执照号">{{ detail.license_no || '—' }}</el-descriptions-item>
          <el-descriptions-item label="法定代表人">{{ detail.legal_person || '—' }}</el-descriptions-item>
          <el-descriptions-item label="注册地址">{{ detail.registered_address || '—' }}</el-descriptions-item>
          <el-descriptions-item label="经营地址">{{ detail.business_address || '—' }}</el-descriptions-item>
          <el-descriptions-item label="对外电话">{{ detail.contact_phone || '—' }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ detail.contact_email || '—' }}</el-descriptions-item>
          <el-descriptions-item label="营业时间">{{ detail.business_hours || '—' }}</el-descriptions-item>
          <el-descriptions-item label="简介">{{ detail.description || '—' }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detail.license_image_url" class="license-preview">
          <img v-if="isImageUrl(detail.license_image_url)" :src="detail.license_image_url" alt="营业执照" />
          <a v-else :href="detail.license_image_url" target="_blank" rel="noreferrer">查看营业执照文件</a>
        </div>
        <h4 class="block-title">联系人</h4>
        <el-table :data="detail.contacts || []" size="small">
          <el-table-column prop="name" label="姓名" width="90" />
          <el-table-column prop="phone" label="电话" width="120" />
          <el-table-column prop="title" label="职务" width="90" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">{{ kindLabel(row.kind) }}</template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" />
        </el-table>
        <div v-if="canEditProfile" class="drawer-actions">
          <el-button type="primary" @click="openMerchantDialog(detail)">编辑档案</el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog
      v-model="qrDialog"
      :title="qrMerchant ? `获客码 · ${qrMerchant.name}` : '获客码'"
      width="420px"
      destroy-on-close
    >
      <div v-loading="qrLoading" class="qr-box">
        <img v-if="qrDataUrl" :src="qrDataUrl" alt="获客二维码" class="qr-img" />
        <p class="qr-hint">会员扫码后用手机号验证码登录，自动注册并关联本商户。</p>
        <el-input :model-value="qrUrl" readonly type="textarea" :rows="2" />
      </div>
      <template #footer>
        <el-button @click="copyQrUrl" :disabled="!qrUrl">复制链接</el-button>
        <el-button type="primary" @click="downloadQr" :disabled="!qrDataUrl">下载二维码</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="merchantDialog"
      :title="editingId ? '编辑商户档案' : '新增商户'"
      width="760px"
      destroy-on-close
      top="6vh"
    >
      <el-form ref="merchantFormRef" :model="merchantForm" :rules="merchantRules" label-width="130px">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="经营信息" name="base">
            <el-form-item v-if="isSiteAdmin" label="商户类型" prop="merchant_type_id">
              <el-select v-model="merchantForm.merchant_type_id" style="width: 100%" @change="onTypeChange">
                <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="品牌名称" prop="name">
              <el-input v-model="merchantForm.name" placeholder="如：观野BAR" />
            </el-form-item>
            <el-form-item v-if="isSiteAdmin" label="关联子系统" prop="subsystem_codes">
              <el-select v-model="merchantForm.subsystem_codes" multiple style="width: 100%">
                <el-option
                  v-for="o in BUSINESS_SYSTEM_OPTIONS"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="isSiteAdmin" label="状态">
              <el-select v-model="merchantForm.status" style="width: 100%">
                <el-option label="筹备" value="preparing" />
                <el-option label="营业" value="active" />
                <el-option label="停用" value="disabled" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="isSiteAdmin" label="租赁有效期">
              <el-date-picker
                v-model="leaseRange"
                type="daterange"
                value-format="YYYY-MM-DD"
                start-placeholder="起租日"
                end-placeholder="到期日"
                unlink-panels
                clearable
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="经营地址">
              <el-input v-model="merchantForm.business_address" placeholder="门店实际经营地址" />
            </el-form-item>
            <el-form-item label="对外电话">
              <el-input v-model="merchantForm.contact_phone" placeholder="会员可见的服务电话" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="merchantForm.contact_email" placeholder="选填" />
            </el-form-item>
            <el-form-item label="营业时间">
              <el-input v-model="merchantForm.business_hours" placeholder="如：06:00-22:00" />
            </el-form-item>
            <el-form-item label="简介">
              <el-input v-model="merchantForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
            </el-form-item>
          </el-tab-pane>

          <el-tab-pane label="证照资质" name="license">
            <el-form-item label="企业名称">
              <el-input v-model="merchantForm.legal_name" placeholder="营业执照上的企业名称" />
            </el-form-item>
            <el-form-item label="统一社会信用代码" prop="credit_code">
              <el-input v-model="merchantForm.credit_code" maxlength="18" placeholder="18 位统一社会信用代码" />
            </el-form-item>
            <el-form-item label="营业执照号">
              <el-input v-model="merchantForm.license_no" placeholder="可与信用代码相同" />
            </el-form-item>
            <el-form-item label="法定代表人">
              <el-input v-model="merchantForm.legal_person" />
            </el-form-item>
            <el-form-item label="注册地址">
              <el-input v-model="merchantForm.registered_address" />
            </el-form-item>
            <el-form-item label="执照扫描件">
              <el-upload
                :show-file-list="false"
                accept=".jpg,.jpeg,.png,.webp,.pdf"
                :http-request="uploadLicense"
              >
                <el-button :loading="uploading">上传 JPG / PNG / PDF</el-button>
              </el-upload>
              <p class="hint">单文件不超过 8MB，用于存档核验。</p>
              <div v-if="merchantForm.license_image_url" class="license-preview">
                <img v-if="isImageUrl(merchantForm.license_image_url)" :src="merchantForm.license_image_url" alt="执照预览" />
                <a v-else :href="merchantForm.license_image_url" target="_blank" rel="noreferrer">已上传文件，点击查看</a>
                <el-button link type="danger" @click="clearLicense">移除</el-button>
              </div>
            </el-form-item>
          </el-tab-pane>

          <el-tab-pane label="联系人" name="contacts">
            <p class="hint" style="margin-top: 0">可添加多名紧急联系人；姓名与电话需成对填写。</p>
            <div v-for="(c, index) in merchantForm.contacts" :key="index" class="contact-card">
              <div class="contact-head">
                <strong>联系人 {{ index + 1 }}</strong>
                <el-button link type="danger" @click="removeContact(index)">删除</el-button>
              </div>
              <el-form-item label="类型">
                <el-select v-model="c.kind" style="width: 100%">
                  <el-option v-for="o in kindOptions" :key="o.value" :label="o.label" :value="o.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="姓名">
                <el-input v-model="c.name" placeholder="联系人姓名" />
              </el-form-item>
              <el-form-item label="电话">
                <el-input v-model="c.phone" placeholder="手机或座机" />
              </el-form-item>
              <el-form-item label="职务">
                <el-input v-model="c.title" placeholder="如：店长 / 值班经理" />
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="c.remark" placeholder="选填" />
              </el-form-item>
            </div>
            <el-button @click="addContact('emergency')">添加紧急联系人</el-button>
            <el-button @click="addContact('other')">添加其他联系人</el-button>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer>
        <el-button @click="merchantDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveMerchant">保存</el-button>
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
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0;
}
.filters {
  margin-bottom: 8px;
}
.hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.muted {
  margin-left: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.qr-box {
  text-align: center;
  min-height: 160px;
}
.qr-img {
  width: 240px;
  height: 240px;
  margin: 0 auto 12px;
  display: block;
}
.qr-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  text-align: left;
}
.contact-card {
  margin-bottom: 14px;
  padding: 12px 12px 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--admin-surface);
}
.contact-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.license-preview {
  margin-top: 10px;
}
.license-preview img {
  display: block;
  max-width: 100%;
  max-height: 220px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-light);
  margin-bottom: 8px;
}
.block-title {
  margin: 18px 0 10px;
  font-size: 14px;
}
.drawer-actions {
  margin-top: 16px;
}
.lease-cell {
  min-width: 160px;
}
.lease-remain {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--brand-black);
}
.lease-track {
  height: 6px;
  margin: 6px 0 4px;
  border-radius: 99px;
  background: rgba(125, 131, 137, 0.18);
  overflow: hidden;
}
.lease-fill {
  height: 100%;
  border-radius: inherit;
  background: var(--brand-orange);
  transition: width 0.2s ease;
}
.lease-dates {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}
.lease-cell.is-expiring .lease-remain {
  color: #c45616;
}
.lease-cell.is-expiring .lease-fill {
  background: #e6a23c;
}
.lease-cell.is-expired .lease-remain {
  color: #c45656;
}
.lease-cell.is-expired .lease-fill {
  background: #f56c6c;
}
.lease-cell.is-not_started .lease-remain {
  color: var(--brand-cyan);
}
.lease-cell.is-not_started .lease-fill {
  background: var(--brand-cyan);
}
.lease-cell.is-unset .lease-remain {
  font-weight: 400;
  color: var(--el-text-color-secondary);
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
