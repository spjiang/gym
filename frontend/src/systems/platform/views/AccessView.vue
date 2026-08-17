<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'

type Point = { id: number; name: string; merchant_id: number | null; is_public_area?: boolean }
type Device = { id: number; device_code: string; access_point_id: number; is_online: boolean }
type Grant = {
  id: number
  member_id: number
  access_point_id: number
  revoked: boolean
  valid_from?: string
  valid_until?: string
}
type Member = { id: number; name: string; phone: string }
type Merchant = { id: number; name: string }
type AccessEvent = {
  id: number
  access_point_id: number
  member_id: number | null
  allowed: boolean
  reason: string | null
  created_at: string
  member?: { id: number; name: string; phone: string } | null
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const activeTab = ref('points')
const points = ref<Point[]>([])
const devices = ref<Device[]>([])
const grants = ref<Grant[]>([])
const events = ref<AccessEvent[]>([])
const members = ref<Member[]>([])
const merchants = ref<Merchant[]>([])
const allPoints = ref<Point[]>([])

const pointTotal = ref(0)
const deviceTotal = ref(0)
const grantTotal = ref(0)
const eventTotal = ref(0)
const pointPage = ref(1)
const devicePage = ref(1)
const grantPage = ref(1)
const eventPage = ref(1)
const pageSize = ref(20)

const pointQuery = reactive({ q: '', merchant_id: undefined as number | undefined, is_public_area: '' as string })
const deviceQuery = reactive({
  q: '',
  access_point_id: undefined as number | undefined,
  is_online: '' as string,
})
const grantQuery = reactive({ q: '', access_point_id: undefined as number | undefined, revoked: '' })
const eventQuery = reactive({
  q: '',
  allowed: '',
  access_point_id: undefined as number | undefined,
})

const loading = ref(false)
const submitting = ref(false)
const pointDialog = ref(false)
const deviceDialog = ref(false)
const grantDialog = ref(false)
const eventDetailVisible = ref(false)
const eventDetail = ref<AccessEvent | null>(null)
const eventEditVisible = ref(false)
const eventEditReason = ref('')
const editingEventId = ref<number | null>(null)
const editingPointId = ref<number | null>(null)
const editingDeviceId = ref<number | null>(null)
const editingGrantId = ref<number | null>(null)

const pointFormRef = ref<FormInstance>()
const deviceFormRef = ref<FormInstance>()
const grantFormRef = ref<FormInstance>()
const pointForm = reactive({ name: '', merchant_id: undefined as number | undefined, is_public_area: false })
const deviceForm = reactive({ access_point_id: undefined as number | undefined, device_code: '', api_key: '' })
const grantForm = reactive({
  member_id: undefined as number | undefined,
  access_point_id: undefined as number | undefined,
  merchant_id: undefined as number | undefined,
  days: 30,
})

const pointRules: FormRules = { name: [{ required: true, message: '请填写门禁点名称', trigger: 'blur' }] }
const deviceRules: FormRules = {
  access_point_id: [{ required: true, message: '请选择门禁点', trigger: 'change' }],
  device_code: [{ required: true, message: '请填写设备码', trigger: 'blur' }],
}
const grantRules: FormRules = {
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
  access_point_id: [{ required: true, message: '请选择门禁点', trigger: 'change' }],
}

function pointName(id: number | null | undefined) {
  return allPoints.value.find((p) => p.id === id)?.name || points.value.find((p) => p.id === id)?.name || (id == null ? '—' : `#${id}`)
}
function merchantName(id: number | null | undefined) {
  return merchants.value.find((m) => m.id === id)?.name || (id == null ? '公共' : `#${id}`)
}
function memberName(id: number) {
  const m = members.value.find((x) => x.id === id)
  return m ? `${m.name}(${m.phone})` : `#${id}`
}
function eventMemberLabel(row: AccessEvent) {
  if (row.member) return `${row.member.name}(${row.member.phone})`
  if (row.member_id) return memberName(row.member_id)
  return '—'
}

async function loadLookups() {
  const [m, mem, pts] = await Promise.all([
    http.get('/merchants'),
    http.get('/members', { params: { page: 1, page_size: 100 } }),
    http.get('/access-points'),
  ])
  merchants.value = m.data
  members.value = mem.data.items
  allPoints.value = Array.isArray(pts.data) ? pts.data : pts.data.items
}

async function loadPoints() {
  loading.value = true
  try {
    const { data } = await http.get<Page<Point>>('/access-points', {
      params: {
        page: pointPage.value,
        page_size: pageSize.value,
        q: pointQuery.q.trim() || undefined,
        merchant_id: pointQuery.merchant_id,
        is_public_area: pointQuery.is_public_area === '' ? undefined : pointQuery.is_public_area === '1',
      },
    })
    points.value = data.items
    pointTotal.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadDevices() {
  loading.value = true
  try {
    const { data } = await http.get<Page<Device>>('/devices', {
      params: {
        page: devicePage.value,
        page_size: pageSize.value,
        q: deviceQuery.q.trim() || undefined,
        access_point_id: deviceQuery.access_point_id,
        is_online: deviceQuery.is_online === '' ? undefined : deviceQuery.is_online === '1',
      },
    })
    devices.value = data.items
    deviceTotal.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadGrants() {
  loading.value = true
  try {
    const { data } = await http.get<Page<Grant>>('/grants', {
      params: {
        page: grantPage.value,
        page_size: pageSize.value,
        q: grantQuery.q.trim() || undefined,
        access_point_id: grantQuery.access_point_id,
        revoked: grantQuery.revoked === '' ? undefined : grantQuery.revoked === '1',
      },
    })
    grants.value = data.items
    grantTotal.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadEvents() {
  loading.value = true
  try {
    const { data } = await http.get<Page<AccessEvent>>('/access-events', {
      params: {
        page: eventPage.value,
        page_size: pageSize.value,
        q: eventQuery.q.trim() || undefined,
        allowed: eventQuery.allowed === '' ? undefined : eventQuery.allowed === '1',
        access_point_id: eventQuery.access_point_id,
      },
    })
    events.value = data.items
    eventTotal.value = data.total
  } finally {
    loading.value = false
  }
}

function onTab(name: string) {
  if (name === 'points') void loadPoints()
  if (name === 'devices') void loadDevices()
  if (name === 'grants') void loadGrants()
  if (name === 'events') void loadEvents()
}

function openPoint(row?: Point) {
  editingPointId.value = row?.id ?? null
  pointForm.name = row?.name || ''
  pointForm.merchant_id = row?.merchant_id ?? merchants.value[0]?.id
  pointForm.is_public_area = !!row?.is_public_area
  pointDialog.value = true
}

async function savePoint() {
  const ok = await pointFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    const payload = { name: pointForm.name.trim(), merchant_id: pointForm.merchant_id, is_public_area: pointForm.is_public_area }
    if (editingPointId.value) await http.patch(`/access-points/${editingPointId.value}`, payload)
    else await http.post('/access-points', payload)
    ElMessage.success('已保存')
    pointDialog.value = false
    await loadLookups()
    await loadPoints()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

function openDevice(row?: Device) {
  editingDeviceId.value = row?.id ?? null
  deviceForm.access_point_id = row?.access_point_id ?? allPoints.value[0]?.id
  deviceForm.device_code = row?.device_code || ''
  deviceForm.api_key = ''
  deviceDialog.value = true
}

async function saveDevice() {
  const ok = await deviceFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!editingDeviceId.value && !deviceForm.api_key) {
    ElMessage.warning('请填写 API Key')
    return
  }
  submitting.value = true
  try {
    const payload: Record<string, unknown> = { access_point_id: deviceForm.access_point_id, device_code: deviceForm.device_code }
    if (deviceForm.api_key) payload.api_key = deviceForm.api_key
    if (editingDeviceId.value) await http.patch(`/devices/${editingDeviceId.value}`, payload)
    else await http.post('/devices', payload)
    ElMessage.success('已保存')
    deviceDialog.value = false
    await loadDevices()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

function openGrant(row?: Grant) {
  editingGrantId.value = row?.id ?? null
  grantForm.member_id = row?.member_id
  grantForm.access_point_id = row?.access_point_id ?? allPoints.value[0]?.id
  grantForm.merchant_id = merchants.value[0]?.id
  grantForm.days = 30
  grantDialog.value = true
}

async function saveGrant() {
  const ok = await grantFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    if (editingGrantId.value) {
      await http.patch(`/grants/${editingGrantId.value}`, { access_point_id: grantForm.access_point_id })
    } else {
      const now = new Date()
      await http.post('/grants', {
        member_id: grantForm.member_id,
        access_point_id: grantForm.access_point_id,
        merchant_id: grantForm.merchant_id ?? null,
        valid_from: now.toISOString(),
        valid_until: new Date(now.getTime() + grantForm.days * 86400000).toISOString(),
      })
    }
    ElMessage.success('已保存')
    grantDialog.value = false
    await loadGrants()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

function openEventEdit(row: AccessEvent) {
  editingEventId.value = row.id
  eventEditReason.value = row.reason || ''
  eventEditVisible.value = true
}

async function saveEvent() {
  if (!editingEventId.value) return
  submitting.value = true
  try {
    await http.patch(`/access-events/${editingEventId.value}`, { reason: eventEditReason.value })
    ElMessage.success('已保存')
    eventEditVisible.value = false
    await loadEvents()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function revoke(id: number) {
  await http.post(`/grants/${id}/revoke`)
  ElMessage.success('已撤销')
  await loadGrants()
}

onMounted(async () => {
  await loadLookups()
  await loadPoints()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>门禁设备</h3>
    </div>
    <el-tabs v-model="activeTab" @tab-change="onTab">
      <el-tab-pane label="门禁点" name="points">
        <div class="filters">
          <el-input v-model="pointQuery.q" clearable placeholder="门禁点名称" style="width: 200px" @keyup.enter="loadPoints" />
          <el-select v-model="pointQuery.merchant_id" clearable placeholder="商户" style="width: 180px">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
          <el-select v-model="pointQuery.is_public_area" clearable placeholder="区域类型" style="width: 130px">
            <el-option label="商户门禁" value="0" />
            <el-option label="公共区域" value="1" />
          </el-select>
          <el-button type="primary" @click="pointPage = 1; loadPoints()">查询</el-button>
          <el-button @click="pointQuery.q = ''; pointQuery.merchant_id = undefined; pointQuery.is_public_area = ''; pointPage = 1; loadPoints()">重置</el-button>
          <el-button type="primary" @click="openPoint()">新建</el-button>
        </div>
        <el-table :data="points" v-loading="loading" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="name" label="名称" />
          <el-table-column label="商户" width="200">
            <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" @click="openPoint(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager">
          <el-pagination v-model:current-page="pointPage" v-model:page-size="pageSize" :total="pointTotal" layout="total, sizes, prev, pager, next" background @current-change="loadPoints" @size-change="() => { pointPage = 1; loadPoints() }" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="设备" name="devices">
        <div class="filters">
          <el-input v-model="deviceQuery.q" clearable placeholder="设备码" style="width: 200px" @keyup.enter="loadDevices" />
          <el-select v-model="deviceQuery.access_point_id" clearable placeholder="门禁点" style="width: 180px">
            <el-option v-for="p in allPoints" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <el-select v-model="deviceQuery.is_online" clearable placeholder="在线状态" style="width: 120px">
            <el-option label="在线" value="1" />
            <el-option label="离线" value="0" />
          </el-select>
          <el-button type="primary" @click="devicePage = 1; loadDevices()">查询</el-button>
          <el-button @click="deviceQuery.q = ''; deviceQuery.access_point_id = undefined; deviceQuery.is_online = ''; devicePage = 1; loadDevices()">重置</el-button>
          <el-button type="primary" @click="openDevice()">注册</el-button>
        </div>
        <el-table :data="devices" v-loading="loading" stripe>
          <el-table-column prop="device_code" label="设备码" />
          <el-table-column label="门禁点" width="200">
            <template #default="{ row }">{{ pointName(row.access_point_id) }}</template>
          </el-table-column>
          <el-table-column label="在线" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_online ? 'success' : 'info'" size="small">{{ row.is_online ? '在线' : '离线' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" @click="openDevice(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager">
          <el-pagination v-model:current-page="devicePage" v-model:page-size="pageSize" :total="deviceTotal" layout="total, sizes, prev, pager, next" background @current-change="loadDevices" @size-change="() => { devicePage = 1; loadDevices() }" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="通行授权" name="grants">
        <div class="filters">
          <el-input v-model="grantQuery.q" clearable placeholder="会员姓名/手机" style="width: 200px" @keyup.enter="loadGrants" />
          <el-select v-model="grantQuery.access_point_id" clearable placeholder="门禁点" style="width: 180px">
            <el-option v-for="p in allPoints" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <el-select v-model="grantQuery.revoked" clearable placeholder="状态" style="width: 120px">
            <el-option label="有效" value="0" />
            <el-option label="已撤销" value="1" />
          </el-select>
          <el-button type="primary" @click="grantPage = 1; loadGrants()">查询</el-button>
          <el-button @click="grantQuery.q = ''; grantQuery.access_point_id = undefined; grantQuery.revoked = ''; grantPage = 1; loadGrants()">重置</el-button>
          <el-button type="primary" @click="openGrant()">发放</el-button>
        </div>
        <el-table :data="grants" v-loading="loading" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="会员" width="200">
            <template #default="{ row }">{{ memberName(row.member_id) }}</template>
          </el-table-column>
          <el-table-column label="门禁点">
            <template #default="{ row }">{{ pointName(row.access_point_id) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.revoked ? 'info' : 'success'" size="small">{{ row.revoked ? '已撤销' : '有效' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button size="small" @click="openGrant(row)">编辑</el-button>
              <el-button size="small" :disabled="row.revoked" @click="revoke(row.id)">撤销</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager">
          <el-pagination v-model:current-page="grantPage" v-model:page-size="pageSize" :total="grantTotal" layout="total, sizes, prev, pager, next" background @current-change="loadGrants" @size-change="() => { grantPage = 1; loadGrants() }" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="通行事件" name="events">
        <div class="filters">
          <el-input v-model="eventQuery.q" clearable placeholder="会员手机/姓名" style="width: 200px" @keyup.enter="loadEvents" />
          <el-select v-model="eventQuery.access_point_id" clearable placeholder="门禁点" style="width: 180px">
            <el-option v-for="p in allPoints" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <el-select v-model="eventQuery.allowed" clearable placeholder="结果" style="width: 120px">
            <el-option label="放行" value="1" />
            <el-option label="拒绝" value="0" />
          </el-select>
          <el-button type="primary" @click="eventPage = 1; loadEvents()">查询</el-button>
          <el-button @click="eventQuery.q = ''; eventQuery.allowed = ''; eventQuery.access_point_id = undefined; eventPage = 1; loadEvents()">重置</el-button>
        </div>
        <el-table :data="events" v-loading="loading" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="会员" min-width="160">
            <template #default="{ row }">{{ eventMemberLabel(row) }}</template>
          </el-table-column>
          <el-table-column label="门禁点" width="160">
            <template #default="{ row }">{{ pointName(row.access_point_id) }}</template>
          </el-table-column>
          <el-table-column label="结果" width="100">
            <template #default="{ row }">
              <el-tag :type="row.allowed ? 'success' : 'danger'" size="small">{{ row.allowed ? '放行' : '拒绝' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="原因" />
          <el-table-column label="时间" width="180">
            <template #default="{ row }">{{ row.created_at?.slice(0, 19).replace('T', ' ') }}</template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEventEdit(row)">编辑</el-button>
              <el-button link type="primary" @click="eventDetail = row; eventDetailVisible = true">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager">
          <el-pagination v-model:current-page="eventPage" v-model:page-size="pageSize" :total="eventTotal" layout="total, sizes, prev, pager, next" background @current-change="loadEvents" @size-change="() => { eventPage = 1; loadEvents() }" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="pointDialog" :title="editingPointId ? '编辑门禁点' : '创建门禁点'" width="460px">
      <el-form ref="pointFormRef" :model="pointForm" :rules="pointRules" label-width="80px">
        <el-form-item label="名称" prop="name"><el-input v-model="pointForm.name" /></el-form-item>
        <el-form-item label="商户"><el-select v-model="pointForm.merchant_id" clearable style="width: 100%"><el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" /></el-select></el-form-item>
        <el-form-item label="公共区域"><el-switch v-model="pointForm.is_public_area" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pointDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="savePoint">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deviceDialog" :title="editingDeviceId ? '编辑设备' : '注册设备'" width="480px">
      <el-form ref="deviceFormRef" :model="deviceForm" :rules="deviceRules" label-width="90px">
        <el-form-item label="门禁点" prop="access_point_id"><el-select v-model="deviceForm.access_point_id" style="width: 100%"><el-option v-for="p in allPoints" :key="p.id" :label="p.name" :value="p.id" /></el-select></el-form-item>
        <el-form-item label="设备码" prop="device_code"><el-input v-model="deviceForm.device_code" /></el-form-item>
        <el-form-item label="API Key"><el-input v-model="deviceForm.api_key" show-password :placeholder="editingDeviceId ? '留空不修改' : '设备接入凭证'" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deviceDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveDevice">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="grantDialog" :title="editingGrantId ? '编辑授权' : '发放授权'" width="480px">
      <el-form ref="grantFormRef" :model="grantForm" :rules="grantRules" label-width="90px">
        <el-form-item v-if="!editingGrantId" label="会员" prop="member_id"><el-select v-model="grantForm.member_id" filterable style="width: 100%"><el-option v-for="m in members" :key="m.id" :label="`${m.name}(${m.phone})`" :value="m.id" /></el-select></el-form-item>
        <el-form-item label="门禁点" prop="access_point_id"><el-select v-model="grantForm.access_point_id" style="width: 100%"><el-option v-for="p in allPoints" :key="p.id" :label="p.name" :value="p.id" /></el-select></el-form-item>
        <el-form-item v-if="!editingGrantId" label="有效天数"><el-input-number v-model="grantForm.days" :min="1" :max="3650" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="grantDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveGrant">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="eventEditVisible" title="编辑通行事件" width="440px">
      <el-form label-width="80px">
        <el-form-item label="原因/备注">
          <el-input v-model="eventEditReason" type="textarea" :rows="3" maxlength="128" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="eventEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveEvent">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="eventDetailVisible" title="通行事件详情" size="400px">
      <template v-if="eventDetail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="ID">{{ eventDetail.id }}</el-descriptions-item>
          <el-descriptions-item label="会员">{{ eventMemberLabel(eventDetail) }}</el-descriptions-item>
          <el-descriptions-item label="门禁点">{{ pointName(eventDetail.access_point_id) }}</el-descriptions-item>
          <el-descriptions-item label="结果">{{ eventDetail.allowed ? '放行' : '拒绝' }}</el-descriptions-item>
          <el-descriptions-item label="原因">{{ eventDetail.reason || '—' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.toolbar h3 { margin: 0 0 12px; }
.filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.pager { margin-top: 12px; display: flex; justify-content: flex-end; }
</style>
