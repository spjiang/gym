<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Course = {
  id: number
  name: string
  difficulty: string | null
  default_duration_minutes: number
  default_capacity: number
  book_ahead_minutes: number
  cancel_ahead_minutes: number
  is_active: boolean
}

const merchants = ref<Merchant[]>([])
const courses = ref<Course[]>([])
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const query = reactive({
  q: '',
  difficulty: '',
  status: '' as '' | 'active' | 'inactive',
  duration_min: undefined as number | undefined,
  duration_max: undefined as number | undefined,
  capacity_min: undefined as number | undefined,
  capacity_max: undefined as number | undefined,
})
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  difficulty: '',
  default_duration_minutes: 60,
  default_capacity: 20,
  book_ahead_minutes: 0,
  cancel_ahead_minutes: 0,
})
const rules: FormRules = {
  name: [{ required: true, message: '请填写课程名称', trigger: 'blur' }],
}

async function refresh() {
  loading.value = true
  try {
    const { data } = await http.get('/merchants')
    merchants.value = merchantsWithSystem(data, 'gym')
    if (merchantId.value && !merchants.value.some((m) => m.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const { data: rows } = await http.get('/group-courses', {
      params: {
        merchant_id: merchantId.value,
        q: query.q.trim() || undefined,
        difficulty: query.difficulty.trim() || undefined,
        is_active: query.status === 'active' ? true : query.status === 'inactive' ? false : undefined,
        duration_min: query.duration_min,
        duration_max: query.duration_max,
        capacity_min: query.capacity_min,
        capacity_max: query.capacity_max,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    courses.value = rows.items
    total.value = rows.total
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
  query.difficulty = ''
  query.status = ''
  query.duration_min = undefined
  query.duration_max = undefined
  query.capacity_min = undefined
  query.capacity_max = undefined
  page.value = 1
  void refresh()
}

function openCreate() {
  editingId.value = null
  form.name = ''
  form.difficulty = ''
  form.default_duration_minutes = 60
  form.default_capacity = 20
  form.book_ahead_minutes = 0
  form.cancel_ahead_minutes = 0
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

function openEdit(row: Course) {
  editingId.value = row.id
  form.name = row.name
  form.difficulty = row.difficulty || ''
  form.default_duration_minutes = row.default_duration_minutes
  form.default_capacity = row.default_capacity
  form.book_ahead_minutes = row.book_ahead_minutes
  form.cancel_ahead_minutes = row.cancel_ahead_minutes
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    const payload = {
      merchant_id: mid,
      name: form.name.trim(),
      difficulty: form.difficulty.trim() || null,
      default_duration_minutes: form.default_duration_minutes,
      default_capacity: form.default_capacity,
      book_ahead_minutes: form.book_ahead_minutes,
      cancel_ahead_minutes: form.cancel_ahead_minutes,
    }
    if (editingId.value) {
      await http.patch(`/group-courses/${editingId.value}`, payload)
      ElMessage.success('模板已更新')
    } else {
      await http.post('/group-courses', payload)
      ElMessage.success('模板已创建')
    }
    dialogVisible.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>团课模板</h3>
        <p class="lead">配置课种、时长与人数上限。排课在「团课管理 → 团课排课」，代约在「团课管理 → 团课代约」。</p>
      </div>
      <el-button type="primary" @click="openCreate">新建模板</el-button>
    </div>
    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="search">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="名称 / ID" style="width: 160px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="难度">
        <el-input v-model="query.difficulty" clearable placeholder="如：入门" style="width: 120px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 110px">
          <el-option label="启用" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>
      </el-form-item>
      <el-form-item label="时长">
        <el-input-number v-model="query.duration_min" :min="1" :controls="false" placeholder="最少" style="width: 90px" />
        <span class="range-sep">—</span>
        <el-input-number v-model="query.duration_max" :min="1" :controls="false" placeholder="最多" style="width: 90px" />
      </el-form-item>
      <el-form-item label="上限">
        <el-input-number v-model="query.capacity_min" :min="1" :controls="false" placeholder="最少" style="width: 90px" />
        <span class="range-sep">—</span>
        <el-input-number v-model="query.capacity_max" :min="1" :controls="false" placeholder="最多" style="width: 90px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>
    <el-table :data="courses" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column label="难度" width="100">
        <template #default="{ row }">{{ row.difficulty || '—' }}</template>
      </el-table-column>
      <el-table-column prop="default_duration_minutes" label="时长(分)" width="100" />
      <el-table-column prop="default_capacity" label="默认上限" width="100" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
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
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑模板' : '新建模板'" width="500px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：燃脂操 / 瑜伽" maxlength="128" />
        </el-form-item>
        <el-form-item label="难度">
          <el-input v-model="form.difficulty" placeholder="如：入门 / 进阶" maxlength="32" />
        </el-form-item>
        <el-form-item label="默认时长">
          <el-input-number v-model="form.default_duration_minutes" :min="15" :step="15" style="width: 100%" />
        </el-form-item>
        <el-form-item label="默认上限">
          <el-input-number v-model="form.default_capacity" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="预约提前(分)">
          <el-input-number v-model="form.book_ahead_minutes" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="取消提前(分)">
          <el-input-number v-model="form.cancel_ahead_minutes" :min="0" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">{{ editingId ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
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
.range-sep {
  margin: 0 6px;
  color: var(--el-text-color-secondary);
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
