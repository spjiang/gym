<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { ptAppointmentStatusLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Coach = { id: number; display_name: string; is_active?: boolean }
type AvailablePackage = { id: number; remaining_sessions: number; ends_at: string | null }
type Appointment = {
  id: number
  merchant_id: number
  member_id: number
  coach_id: number
  package_id: number | null
  starts_at: string
  ends_at: string
  status: string
  location: string | null
  note: string | null
  completed_at: string | null
  cancel_reason: string | null
  member?: Member | null
  coach_name: string | null
  package_remaining_sessions: number | null
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const coaches = ref<Coach[]>([])
const rows = ref<Appointment[]>([])
const packages = ref<AvailablePackage[]>([])
const loading = ref(false)
const submitting = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dialog = ref(false)
const editing = ref<Appointment | null>(null)
const formRef = ref<FormInstance>()

const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})

const query = reactive({
  q: '',
  coach_id: undefined as number | undefined,
  status: 'booked' as string,
  range: undefined as [string, string] | undefined,
})

const form = reactive({
  member_id: undefined as number | undefined,
  coach_id: undefined as number | undefined,
  package_id: undefined as number | undefined,
  starts_at: '',
  ends_at: '',
  location: '',
  note: '',
})

const rules: FormRules = {
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
  coach_id: [{ required: true, message: '请选择教练', trigger: 'change' }],
  starts_at: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  ends_at: [{ required: true, message: '请选择结束时间', trigger: 'change' }],
}

const dialogTitle = computed(() => (editing.value ? `改期 · 预约 #${editing.value.id}` : '新建私教排期'))

function fmtTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function memberText(row: Appointment) {
  if (row.member) return `${row.member.name} ${row.member.phone}`
  const m = members.value.find((x) => x.id === row.member_id)
  return m ? `${m.name} ${m.phone}` : `#${row.member_id}`
}

function statusTagType(status: string) {
  if (status === 'completed') return 'success'
  if (status === 'booked') return 'primary'
  if (status === 'no_show') return 'warning'
  return 'info'
}

async function loadPackages(memberId: number | undefined) {
  packages.value = []
  form.package_id = undefined
  if (!memberId || !merchantId.value) return
  try {
    const { data } = await http.get<AvailablePackage[]>('/pt-appointments/available-packages', {
      params: { member_id: memberId, merchant_id: merchantId.value },
    })
    packages.value = data
    if (data.length === 1) form.package_id = data[0].id
  } catch {
    packages.value = []
  }
}

watch(
  () => form.member_id,
  (val) => {
    if (!editing.value) void loadPackages(val)
  },
)

async function refresh() {
  loading.value = true
  try {
    const [m, mem] = await Promise.all([
      http.get('/merchants'),
      http.get('/members', { params: { page: 1, page_size: 100 } }),
    ])
    merchants.value = merchantsWithSystem(m.data, 'gym')
    members.value = mem.data.items
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const [co, list] = await Promise.all([
      http.get('/coaches', { params: { merchant_id: merchantId.value, page: 1, page_size: 100 } }),
      http.get<Page<Appointment>>('/pt-appointments', {
        params: {
          merchant_id: merchantId.value,
          coach_id: query.coach_id,
          status: query.status || undefined,
          q: query.q.trim() || undefined,
          date_from: query.range?.[0] || undefined,
          date_to: query.range?.[1] || undefined,
          page: page.value,
          page_size: pageSize.value,
        },
      }),
    ])
    coaches.value = co.data.items
    rows.value = list.data.items
    total.value = list.data.total
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
  query.coach_id = undefined
  query.status = 'booked'
  query.range = undefined
  page.value = 1
  void refresh()
}

function openCreate() {
  if (!requireMerchant('请先选择商户后再排期')) return
  editing.value = null
  Object.assign(form, {
    member_id: undefined,
    coach_id: undefined,
    package_id: undefined,
    starts_at: '',
    ends_at: '',
    location: '',
    note: '',
  })
  packages.value = []
  formRef.value?.clearValidate()
  dialog.value = true
}

function openEdit(row: Appointment) {
  editing.value = row
  Object.assign(form, {
    member_id: row.member_id,
    coach_id: row.coach_id,
    package_id: row.package_id ?? undefined,
    starts_at: row.starts_at,
    ends_at: row.ends_at,
    location: row.location || '',
    note: row.note || '',
  })
  formRef.value?.clearValidate()
  dialog.value = true
}

async function submit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    if (editing.value) {
      await http.patch(`/pt-appointments/${editing.value.id}`, {
        coach_id: form.coach_id,
        starts_at: form.starts_at,
        ends_at: form.ends_at,
        location: form.location.trim() || null,
        note: form.note.trim() || null,
      })
      ElMessage.success('已改期')
    } else {
      const mid = requireMerchant('请先选择商户后再排期')
      if (!mid) return
      await http.post('/pt-appointments', {
        merchant_id: mid,
        member_id: form.member_id,
        coach_id: form.coach_id,
        package_id: form.package_id ?? null,
        starts_at: form.starts_at,
        ends_at: form.ends_at,
        location: form.location.trim() || null,
        note: form.note.trim() || null,
      })
      ElMessage.success('排期成功，已通知会员')
    }
    dialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function complete(row: Appointment) {
  const tip = row.package_id
    ? '完成后将核销课包 1 节课时并按规则计提教练提成，确认？'
    : '完成后将按规则计提教练提成，确认？'
  try {
    await ElMessageBox.confirm(tip, '完成私教课', { type: 'info' })
  } catch {
    return
  }
  try {
    await http.post(`/pt-appointments/${row.id}/complete`)
    ElMessage.success('已完成核销')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

async function cancel(row: Appointment) {
  try {
    const { value } = await ElMessageBox.prompt('请填写取消原因（选填）', '取消排期', {
      inputPlaceholder: '如 会员出差',
      inputValidator: (v: string) => v.length <= 255 || '原因不超过 255 字',
    })
    await http.post(`/pt-appointments/${row.id}/cancel`, { reason: value || null })
    ElMessage.success('已取消')
    await refresh()
  } catch (e: unknown) {
    if (e instanceof Error) ElMessage.error(e.message)
  }
}

async function noShow(row: Appointment) {
  try {
    await ElMessageBox.confirm(
      row.package_id ? '标记未到并扣除 1 节课时？' : '标记该会员未到场？',
      '标记未到',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await http.post(`/pt-appointments/${row.id}/no-show`, { consume_session: true })
    ElMessage.success('已标记未到')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>私教预约</h3>
        <p class="lead">
          一对一私教排期：选课包后完成核销自动扣课时并计提教练提成；同一教练与会员的时段不可重叠。
        </p>
      </div>
      <el-button type="primary" @click="openCreate">新建排期</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="教练">
        <el-select v-model="query.coach_id" clearable placeholder="全部" style="width: 150px">
          <el-option v-for="c in coaches" :key="c.id" :label="c.display_name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 130px">
          <el-option label="待上课" value="booked" />
          <el-option label="已完成" value="completed" />
          <el-option label="未到场" value="no_show" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="会员 / 教练" style="width: 180px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="上课时间">
        <el-date-picker
          v-model="query.range"
          type="datetimerange"
          value-format="YYYY-MM-DDTHH:mm:ss"
          start-placeholder="起"
          end-placeholder="止"
          style="width: 320px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="会员" min-width="180">
        <template #default="{ row }">{{ memberText(row) }}</template>
      </el-table-column>
      <el-table-column label="教练" min-width="120">
        <template #default="{ row }">{{ row.coach_name || `#${row.coach_id}` }}</template>
      </el-table-column>
      <el-table-column label="上课时间" min-width="290">
        <template #default="{ row }">{{ fmtTime(row.starts_at) }} ~ {{ fmtTime(row.ends_at) }}</template>
      </el-table-column>
      <el-table-column label="课包" width="140">
        <template #default="{ row }">
          <span v-if="!row.package_id">未挂课包</span>
          <span v-else>#{{ row.package_id }}（剩 {{ row.package_remaining_sessions ?? '—' }} 节）</span>
        </template>
      </el-table-column>
      <el-table-column prop="location" label="场地" width="120">
        <template #default="{ row }">{{ row.location || '—' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTagType(row.status)">{{ ptAppointmentStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="row.status !== 'booked'" @click="complete(row)">完成</el-button>
          <el-button link type="primary" :disabled="row.status !== 'booked'" @click="openEdit(row)">改期</el-button>
          <el-button link type="warning" :disabled="row.status !== 'booked'" @click="noShow(row)">未到</el-button>
          <el-button link type="danger" :disabled="row.status !== 'booked'" @click="cancel(row)">取消</el-button>
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

    <el-dialog v-model="dialog" :title="dialogTitle" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="会员" prop="member_id">
          <el-select v-model="form.member_id" filterable :disabled="!!editing" style="width: 100%">
            <el-option v-for="x in members" :key="x.id" :label="`${x.name} ${x.phone}`" :value="x.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教练" prop="coach_id">
          <el-select v-model="form.coach_id" filterable style="width: 100%">
            <el-option v-for="c in coaches" :key="c.id" :label="c.display_name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!editing" label="课包">
          <el-select v-model="form.package_id" clearable placeholder="不挂课包（按教练课时费结算）" style="width: 100%">
            <el-option
              v-for="p in packages"
              :key="p.id"
              :label="`#${p.id} 剩 ${p.remaining_sessions} 节`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间" prop="starts_at">
          <el-date-picker v-model="form.starts_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束时间" prop="ends_at">
          <el-date-picker v-model="form.ends_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="场地">
          <el-input v-model="form.location" maxlength="128" placeholder="如 私教区 2 号" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" type="textarea" :rows="2" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
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
  margin-bottom: 8px;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
