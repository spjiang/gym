<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
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

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const points = ref<AccessPoint[]>([])
const visits = ref<Visit[]>([])
const merchantId = ref<number | undefined>()
const loading = ref(false)

const dialogVisible = ref(false)
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
    if (!merchantId.value && m[0]) merchantId.value = m[0].id
    if (!merchantId.value) return
    const [mem, pts, vs] = await Promise.all([
      http.get('/members', { params: { page: 1, page_size: 100 } }),
      http.get('/access-points', { params: { merchant_id: merchantId.value } }),
      http.get('/visits', { params: { merchant_id: merchantId.value } }),
    ])
    members.value = mem.data.items
    points.value = pts.data
    visits.value = vs.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openDialog() {
  form.member_id = undefined
  form.access_point_id = points.value[0]?.id
  form.hours = 2
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function createVisit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/visits', { merchant_id: merchantId.value, ...form })
    ElMessage.success('临访已登记')
    dialogVisible.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '登记失败')
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

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>临访登记</h3>
      <el-button type="primary" @click="openDialog">登记临访</el-button>
    </div>

    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

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
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="row.status === 'active'" link type="danger" @click="revokeVisit(row.id)">
            撤销
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 登记临访弹窗 -->
    <el-dialog v-model="dialogVisible" title="登记临访" width="480px" destroy-on-close>
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
          <div class="form-hint">登记后该会员可在所选门禁点通行指定小时数</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createVisit">登记</el-button>
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

.form-hint {
  width: 100%;
  margin-top: 6px;
  font-size: 0.78rem;
  color: var(--admin-ink-muted);
}
</style>
