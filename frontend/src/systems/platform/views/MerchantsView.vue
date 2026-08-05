<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { BUSINESS_SYSTEM_OPTIONS, defaultSubsystemsForTypeCode } from '../../../core/nav/systems'
import { merchantStatusLabel } from '../../../core/labels'

type MerchantType = { id: number; code: string; name: string }
type Merchant = {
  id: number
  name: string
  status: string
  merchant_type_id: number
  subsystem_codes: string[]
}

const types = ref<MerchantType[]>([])
const merchants = ref<Merchant[]>([])
const loading = ref(false)

const typeDialog = ref(false)
const merchantDialog = ref(false)
const subsystemDialog = ref(false)
const submitting = ref(false)
const typeFormRef = ref<FormInstance>()
const merchantFormRef = ref<FormInstance>()
const editingMerchant = ref<Merchant | null>(null)

const typeForm = reactive({ code: '', name: '' })
const merchantForm = reactive({
  merchant_type_id: undefined as number | undefined,
  name: '',
  status: 'active',
  subsystem_codes: ['gym'] as string[],
})
const subsystemForm = reactive({ subsystem_codes: [] as string[] })

const typeRules: FormRules = {
  code: [{ required: true, message: '请填写类型编码', trigger: 'blur' }],
  name: [{ required: true, message: '请填写类型名称', trigger: 'blur' }],
}

const merchantRules: FormRules = {
  merchant_type_id: [{ required: true, message: '请选择商户类型', trigger: 'change' }],
  name: [{ required: true, message: '请填写商户名称', trigger: 'blur' }],
  subsystem_codes: [{ type: 'array', required: true, min: 1, message: '请至少关联一个业态子系统', trigger: 'change' }],
}

const systemLabel = computed(() => {
  const map = Object.fromEntries(BUSINESS_SYSTEM_OPTIONS.map((o) => [o.value, o.label]))
  return (codes: string[]) => (codes || []).map((c) => map[c] || c).join('、') || '—'
})

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

function openTypeDialog() {
  typeForm.code = ''
  typeForm.name = ''
  typeFormRef.value?.clearValidate()
  typeDialog.value = true
}

async function createType() {
  const ok = await typeFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/merchant-types', { ...typeForm, code: typeForm.code.trim(), name: typeForm.name.trim() })
    ElMessage.success('已创建商户类型')
    typeDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function onTypeChange(typeId: number) {
  const t = types.value.find((x) => x.id === typeId)
  if (t) merchantForm.subsystem_codes = defaultSubsystemsForTypeCode(t.code)
}

function openMerchantDialog() {
  merchantForm.name = ''
  merchantForm.status = 'active'
  if (merchantForm.merchant_type_id === undefined && types.value[0]) {
    merchantForm.merchant_type_id = types.value[0].id
  }
  const t = types.value.find((x) => x.id === merchantForm.merchant_type_id)
  merchantForm.subsystem_codes = defaultSubsystemsForTypeCode(t?.code || 'gym')
  merchantFormRef.value?.clearValidate()
  merchantDialog.value = true
}

async function createMerchant() {
  const ok = await merchantFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!merchantForm.subsystem_codes.length) {
    ElMessage.warning('请至少关联一个业态子系统')
    return
  }
  submitting.value = true
  try {
    await http.post('/merchants', {
      merchant_type_id: merchantForm.merchant_type_id,
      name: merchantForm.name.trim(),
      status: merchantForm.status,
      subsystem_codes: merchantForm.subsystem_codes,
    })
    ElMessage.success('已创建商户')
    merchantDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openSubsystemDialog(row: Merchant) {
  editingMerchant.value = row
  subsystemForm.subsystem_codes = [...(row.subsystem_codes || [])]
  subsystemDialog.value = true
}

async function saveSubsystems() {
  if (!editingMerchant.value) return
  if (!subsystemForm.subsystem_codes.length) {
    ElMessage.warning('请至少关联一个业态子系统')
    return
  }
  submitting.value = true
  try {
    await http.put(`/merchants/${editingMerchant.value.id}/subsystems`, {
      subsystem_codes: subsystemForm.subsystem_codes,
    })
    ElMessage.success('子系统已更新')
    subsystemDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '更新失败')
  } finally {
    submitting.value = false
  }
}

async function setStatus(row: Merchant, status: string) {
  try {
    await http.patch(`/merchants/${row.id}?status=${status}`)
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

function typeName(id: number) {
  return types.value.find((t) => t.id === id)?.name || `#${id}`
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>商户组织</h3>
      <div class="toolbar-actions">
        <el-button type="primary" plain @click="openTypeDialog">新增类型</el-button>
        <el-button type="primary" @click="openMerchantDialog">新增商户</el-button>
      </div>
    </div>

    <h3 class="section-title">商户类型</h3>
    <el-table :data="types" v-loading="loading" style="margin-bottom: 28px">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="code" label="编码" />
      <el-table-column prop="name" label="名称" />
    </el-table>

    <h3 class="section-title">商户</h3>
    <el-table :data="merchants" v-loading="loading">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column label="类型" width="120">
        <template #default="{ row }">{{ typeName(row.merchant_type_id) }}</template>
      </el-table-column>
      <el-table-column label="关联子系统" min-width="160">
        <template #default="{ row }">
          <el-tag
            v-for="c in row.subsystem_codes || []"
            :key="c"
            size="small"
            style="margin-right: 4px"
          >
            {{ BUSINESS_SYSTEM_OPTIONS.find((o) => o.value === c)?.label || c }}
          </el-tag>
          <span v-if="!(row.subsystem_codes || []).length">—</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : row.status === 'preparing' ? 'warning' : 'info'" size="small">
            {{ merchantStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="320" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openQr(row)">获客码</el-button>
          <el-button link type="primary" @click="openSubsystemDialog(row)">子系统</el-button>
          <el-button
            v-if="row.status !== 'active'"
            link
            type="success"
            @click="setStatus(row, 'active')"
          >
            启用
          </el-button>
          <el-button
            v-if="row.status === 'active'"
            link
            type="danger"
            @click="setStatus(row, 'disabled')"
          >
            停用
          </el-button>
        </template>
      </el-table-column>
    </el-table>

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

    <el-dialog v-model="typeDialog" title="新增商户类型" width="440px" destroy-on-close>
      <el-form ref="typeFormRef" :model="typeForm" :rules="typeRules" label-width="90px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="typeForm.code" placeholder="如 gym / bar" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="typeForm.name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createType">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="merchantDialog" title="新增商户" width="520px" destroy-on-close>
      <el-form ref="merchantFormRef" :model="merchantForm" :rules="merchantRules" label-width="110px">
        <el-form-item label="商户类型" prop="merchant_type_id">
          <el-select
            v-model="merchantForm.merchant_type_id"
            style="width: 100%"
            @change="onTypeChange"
          >
            <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="merchantForm.name" placeholder="如：回龙观清吧" />
        </el-form-item>
        <el-form-item label="关联子系统" prop="subsystem_codes">
          <el-select
            v-model="merchantForm.subsystem_codes"
            multiple
            style="width: 100%"
            placeholder="可多选：健身 / 餐饮"
          >
            <el-option
              v-for="o in BUSINESS_SYSTEM_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
          <p class="hint">决定该商户可进入哪些业态能力；清吧请选择「餐饮管理」。</p>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="merchantForm.status" style="width: 100%">
            <el-option label="筹备" value="preparing" />
            <el-option label="营业" value="active" />
            <el-option label="停用" value="disabled" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="merchantDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createMerchant">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="subsystemDialog"
      :title="`调整子系统 · ${editingMerchant?.name || ''}`"
      width="480px"
      destroy-on-close
    >
      <el-select v-model="subsystemForm.subsystem_codes" multiple style="width: 100%">
        <el-option
          v-for="o in BUSINESS_SYSTEM_OPTIONS"
          :key="o.value"
          :label="o.label"
          :value="o.value"
        />
      </el-select>
      <p class="hint">当前：{{ systemLabel(subsystemForm.subsystem_codes) }}</p>
      <template #footer>
        <el-button @click="subsystemDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveSubsystems">保存</el-button>
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
  margin-bottom: 8px;
}
.toolbar h3 {
  margin: 0;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
}
.section-title {
  margin: 8px 0 12px;
  font-size: 0.95rem;
}
.hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
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
</style>
