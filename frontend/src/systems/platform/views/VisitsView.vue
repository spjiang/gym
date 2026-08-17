<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { visitStatusLabel } from '../../../core/labels'

type Merchant = { id: number; name: string }
type Member = { id: number; name: string; phone: string }
type AccessPoint = { id: number; name: string }
type Visit = {
  id: number
  member_id: number
  access_point_id: number
  hours: number
  status: string
  created_at: string
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const points = ref<AccessPoint[]>([])
const visits = ref<Visit[]>([])
const merchantId = ref<number | undefined>()
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ q: '', status: '', access_point_id: undefined as number | undefined })

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  member_id: undefined as number | undefined,
  access_point_id: undefined as number | undefined,
  hours: 2,
})

const rules: FormRules = {
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
  access_point_id: [{ required: true, message: '请选择门禁点', trigger: 'change' }],
  hours: [{ required: true, message: '请填写有效小时数', trigger: 'change' }],
}

function memberName(id: number) {
  const m = members.value.find((x) => x.id === id)
  return m ? `${m.name}(${m.phone})` : `#${id}`
}

function pointName(id: number) {
  return points.value.find((p) => p.id === id)?.name || `#${id}`
}

async function refresh() {
  loading.value = true
  try {
    const { data: m } = await http.get('/merchants')
    merchants.value = m
    const [mem, pts, vs] = await Promise.all([
      http.get('/members', { params: { page: 1, page_size: 100 } }),
      http.get('/access-points', { params: { merchant_id: merchantId.value } }),
      http.get<Page<Visit>>('/visits', {
        params: {
          merchant_id: merchantId.value,
          q: query.q.trim() || undefined,
          status: query.status || undefined,
          access_point_id: query.access_point_id,
          page: page.value,
          page_size: pageSize.value,
        },
      }),
    ])
    members.value = mem.data.items
    points.value = Array.isArray(pts.data) ? pts.data : pts.data.items
    visits.value = vs.data.items
    total.value = vs.data.total
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
  query.access_point_id = undefined
  merchantId.value = undefined
  page.value = 1
  void refresh()
}

function openDialog(row?: Visit) {
  editingId.value = row?.id ?? null
  form.member_id = row?.member_id
  form.access_point_id = row?.access_point_id ?? points.value[0]?.id
  form.hours = row?.hours ?? 2
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function submitVisit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    if (editingId.value) {
      await http.patch(`/visits/${editingId.value}`, { ...form })
      ElMessage.success('临访已更新')
    } else {
      await http.post('/visits', { merchant_id: merchantId.value, ...form })
      ElMessage.success('临访已登记')
    }
    dialogVisible.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function revokeVisit(id: number) {
  try {
    await http.post(`/visits/${id}/revoke`)
    ElMessage.success('已撤销')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '撤销失败')
  }
}

async function removeVisit(row: Visit) {
  try {
    await ElMessageBox.confirm(`删除临访 #${row.id}？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await http.delete(`/visits/${row.id}`)
    ElMessage.success('已删除')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>临访登记</h3>
      <el-button type="primary" @click="openDialog()">登记临访</el-button>
    </div>

    <div class="filters">
      <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="search">
        <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-input v-model="query.q" clearable placeholder="会员姓名 / 手机号" style="width: 200px" @keyup.enter="search" />
      <el-select v-model="query.status" clearable placeholder="状态" style="width: 140px">
        <el-option label="有效" value="active" />
        <el-option label="已撤销" value="revoked" />
      </el-select>
      <el-select v-model="query.access_point_id" clearable placeholder="门禁点" style="width: 180px">
        <el-option v-for="p in points" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="visits" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="会员" width="200">
        <template #default="{ row }">{{ memberName(row.member_id) }}</template>
      </el-table-column>
      <el-table-column label="门禁点" width="180">
        <template #default="{ row }">{{ pointName(row.access_point_id) }}</template>
      </el-table-column>
      <el-table-column prop="hours" label="小时" width="80" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ visitStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button v-if="row.status === 'active'" link type="danger" @click="revokeVisit(row.id)">撤销</el-button>
          <el-button link type="danger" @click="removeVisit(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑临访' : '登记临访'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="会员" prop="member_id">
          <el-select v-model="form.member_id" filterable placeholder="选择会员" style="width: 100%">
            <el-option
              v-for="m in members"
              :key="m.id"
              :label="`${m.name} (${m.phone})`"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="门禁点" prop="access_point_id">
          <el-select v-model="form.access_point_id" placeholder="选择门禁点" style="width: 100%">
            <el-option v-for="p in points" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效小时" prop="hours">
          <el-input-number v-model="form.hours" :min="1" :max="72" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitVisit">保存</el-button>
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
  font-size: 1.1rem;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
