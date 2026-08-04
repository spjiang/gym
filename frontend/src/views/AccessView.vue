<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../api/http'

type Point = { id: number; name: string; merchant_id: number | null }
type Device = { id: number; device_code: string; access_point_id: number; is_online: boolean }
type Grant = { id: number; member_id: number; access_point_id: number; revoked: boolean }
type Member = { id: number; name: string; phone: string }
type Merchant = { id: number; name: string }

const points = ref<Point[]>([])
const devices = ref<Device[]>([])
const grants = ref<Grant[]>([])
const members = ref<Member[]>([])
const merchants = ref<Merchant[]>([])
const loading = ref(false)

const pointDialog = ref(false)
const deviceDialog = ref(false)
const grantDialog = ref(false)
const submitting = ref(false)

const pointFormRef = ref<FormInstance>()
const deviceFormRef = ref<FormInstance>()
const grantFormRef = ref<FormInstance>()

const pointForm = reactive({ name: '', merchant_id: undefined as number | undefined })
const deviceForm = reactive({ access_point_id: undefined as number | undefined, device_code: '', api_key: '' })
const grantForm = reactive({
  member_id: undefined as number | undefined,
  access_point_id: undefined as number | undefined,
  merchant_id: undefined as number | undefined,
  days: 30,
})

const pointRules: FormRules = {
  name: [{ required: true, message: '请填写门禁点名称', trigger: 'blur' }],
  merchant_id: [{ required: true, message: '请选择商户', trigger: 'change' }],
}

const deviceRules: FormRules = {
  access_point_id: [{ required: true, message: '请选择门禁点', trigger: 'change' }],
  device_code: [{ required: true, message: '请填写设备码', trigger: 'blur' }],
  api_key: [{ required: true, message: '请填写 API Key', trigger: 'blur' }],
}

const grantRules: FormRules = {
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
  access_point_id: [{ required: true, message: '请选择门禁点', trigger: 'change' }],
}

function pointName(id: number | null | undefined) {
  return points.value.find((p) => p.id === id)?.name || (id == null ? '—' : `#${id}`)
}

function merchantName(id: number | null | undefined) {
  return merchants.value.find((m) => m.id === id)?.name || (id == null ? '—' : `#${id}`)
}

function memberName(id: number) {
  const m = members.value.find((x) => x.id === id)
  return m ? `${m.name}(${m.phone})` : `#${id}`
}

async function load() {
  loading.value = true
  try {
    const [p, d, g, m, ms] = await Promise.all([
      http.get('/access-points'),
      http.get('/devices'),
      http.get('/grants'),
      http.get('/members'),
      http.get('/merchants'),
    ])
    points.value = p.data
    devices.value = d.data
    grants.value = g.data
    members.value = m.data
    merchants.value = ms.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openPointDialog() {
  pointForm.name = ''
  pointForm.merchant_id = merchants.value[0]?.id
  pointFormRef.value?.clearValidate()
  pointDialog.value = true
}

async function createPoint() {
  const ok = await pointFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/access-points', { ...pointForm, name: pointForm.name.trim() })
    ElMessage.success('门禁点已创建')
    pointDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openDeviceDialog() {
  deviceForm.access_point_id = points.value[0]?.id
  deviceForm.device_code = ''
  deviceForm.api_key = ''
  deviceFormRef.value?.clearValidate()
  deviceDialog.value = true
}

async function registerDevice() {
  const ok = await deviceFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/devices', deviceForm)
    ElMessage.success('设备已注册')
    deviceDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '注册失败')
  } finally {
    submitting.value = false
  }
}

function openGrantDialog() {
  grantForm.member_id = undefined
  grantForm.access_point_id = points.value[0]?.id
  grantForm.merchant_id = merchants.value[0]?.id
  grantForm.days = 30
  grantFormRef.value?.clearValidate()
  grantDialog.value = true
}

async function createGrant() {
  const ok = await grantFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    const now = new Date()
    const until = new Date(now.getTime() + grantForm.days * 86400000)
    await http.post('/grants', {
      member_id: grantForm.member_id,
      access_point_id: grantForm.access_point_id,
      merchant_id: grantForm.merchant_id ?? null,
      valid_from: now.toISOString(),
      valid_until: until.toISOString(),
    })
    ElMessage.success('授权已发放')
    grantDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '发放失败')
  } finally {
    submitting.value = false
  }
}

async function revoke(id: number) {
  await http.post(`/grants/${id}/revoke`)
  ElMessage.success('已撤销')
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>门禁设备</h3>
      <div class="toolbar-actions">
        <el-button type="primary" plain @click="openPointDialog">创建门禁点</el-button>
        <el-button type="primary" plain @click="openDeviceDialog">注册设备</el-button>
        <el-button type="primary" @click="openGrantDialog">发放授权</el-button>
      </div>
    </div>

    <h3 class="section-title">门禁点</h3>
    <el-table :data="points" v-loading="loading" style="margin-bottom: 28px">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="商户" width="200">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
    </el-table>

    <h3 class="section-title">设备</h3>
    <el-table :data="devices" v-loading="loading" style="margin-bottom: 28px">
      <el-table-column prop="device_code" label="设备码" />
      <el-table-column label="门禁点" width="200">
        <template #default="{ row }">{{ pointName(row.access_point_id) }}</template>
      </el-table-column>
      <el-table-column label="在线状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.is_online ? 'success' : 'info'" size="small">
            {{ row.is_online ? '在线' : '离线' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <h3 class="section-title">通行授权</h3>
    <el-table :data="grants" v-loading="loading">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="会员" width="200">
        <template #default="{ row }">{{ memberName(row.member_id) }}</template>
      </el-table-column>
      <el-table-column label="门禁点" width="200">
        <template #default="{ row }">{{ pointName(row.access_point_id) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.revoked ? 'info' : 'success'" size="small">
            {{ row.revoked ? '已撤销' : '有效' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" :disabled="row.revoked" @click="revoke(row.id)">撤销</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建门禁点弹窗 -->
    <el-dialog v-model="pointDialog" title="创建门禁点" width="460px" destroy-on-close>
      <el-form ref="pointFormRef" :model="pointForm" :rules="pointRules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="pointForm.name" placeholder="如：正门 / 侧门 / 更衣室" maxlength="64" />
        </el-form-item>
        <el-form-item label="商户" prop="merchant_id">
          <el-select v-model="pointForm.merchant_id" style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pointDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createPoint">创建</el-button>
      </template>
    </el-dialog>

    <!-- 设备注册弹窗 -->
    <el-dialog v-model="deviceDialog" title="注册门禁设备" width="480px" destroy-on-close>
      <el-form ref="deviceFormRef" :model="deviceForm" :rules="deviceRules" label-width="90px">
        <el-form-item label="门禁点" prop="access_point_id">
          <el-select v-model="deviceForm.access_point_id" style="width: 100%">
            <el-option v-for="p in points" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备码" prop="device_code">
          <el-input v-model="deviceForm.device_code" placeholder="设备唯一标识" maxlength="128" />
        </el-form-item>
        <el-form-item label="API Key" prop="api_key">
          <el-input v-model="deviceForm.api_key" placeholder="设备接入凭证" maxlength="256" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deviceDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="registerDevice">注册</el-button>
      </template>
    </el-dialog>

    <!-- 发放授权弹窗 -->
    <el-dialog v-model="grantDialog" title="发放通行授权" width="480px" destroy-on-close>
      <el-form ref="grantFormRef" :model="grantForm" :rules="grantRules" label-width="90px">
        <el-form-item label="会员" prop="member_id">
          <el-select v-model="grantForm.member_id" filterable style="width: 100%">
            <el-option v-for="m in members" :key="m.id" :label="`${m.name}(${m.phone})`" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="门禁点" prop="access_point_id">
          <el-select v-model="grantForm.access_point_id" style="width: 100%">
            <el-option v-for="p in points" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="商户">
          <el-select v-model="grantForm.merchant_id" clearable style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效天数" prop="days">
          <el-input-number v-model="grantForm.days" :min="1" :max="3650" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="grantDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createGrant">发放</el-button>
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
  margin-bottom: 20px;
}

.toolbar h3 {
  margin: 0;
  font-size: 1.1rem;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.section-title {
  margin: 0 0 12px;
  font-size: 0.95rem;
}
</style>
