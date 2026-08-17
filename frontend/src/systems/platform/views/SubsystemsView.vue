<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'

type Subsystem = {
  code: string
  name: string
  description: string | null
  is_business: boolean
  sort_order: number
  is_enabled: boolean
}

const rows = ref<Subsystem[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ q: '', is_business: '' as string, is_enabled: '' as string })
const filteredRows = computed(() => {
  const kw = query.q.trim()
  return rows.value.filter((row) => {
    if (kw && !row.code.includes(kw) && !row.name.includes(kw) && !(row.description || '').includes(kw)) return false
    if (query.is_business === '1' && !row.is_business) return false
    if (query.is_business === '0' && row.is_business) return false
    if (query.is_enabled === '1' && !row.is_enabled) return false
    if (query.is_enabled === '0' && row.is_enabled) return false
    return true
  })
})
const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})
const dialogVisible = ref(false)
const submitting = ref(false)
const editing = ref<Subsystem | null>(null)
const form = reactive({ name: '', description: '', sort_order: 0, is_enabled: true })

async function load() {
  loading.value = true
  try {
    const { data } = await http.get('/rbac/subsystems')
    rows.value = data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function toggle(row: Subsystem, enabled: boolean) {
  try {
    await http.patch(`/rbac/subsystems/${row.code}`, { is_enabled: enabled })
    ElMessage.success(enabled ? '已启用' : '已停用')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '更新失败')
  }
}

function openEdit(row: Subsystem) {
  editing.value = row
  form.name = row.name
  form.description = row.description || ''
  form.sort_order = row.sort_order
  form.is_enabled = row.is_enabled
  dialogVisible.value = true
}

async function saveEdit() {
  if (!editing.value) return
  submitting.value = true
  try {
    await http.patch(`/rbac/subsystems/${editing.value.code}`, {
      name: form.name.trim(),
      description: form.description.trim(),
      sort_order: form.sort_order,
      is_enabled: form.is_enabled,
    })
    ElMessage.success('已保存')
    dialogVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>子系统配置</h3>
      <el-button @click="load">刷新</el-button>
    </div>
    <p class="hint">启停会影响全场导航与菜单；能力目录由各子系统代码注册，不可在此手造权限码。</p>
    <el-form inline class="filters">
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="编码 / 名称" style="width: 180px" @input="page = 1" />
      </el-form-item>
      <el-form-item label="业态">
        <el-select v-model="query.is_business" clearable placeholder="全部" style="width: 110px" @change="page = 1">
          <el-option label="是" value="1" />
          <el-option label="否" value="0" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用">
        <el-select v-model="query.is_enabled" clearable placeholder="全部" style="width: 110px" @change="page = 1">
          <el-option label="启用" value="1" />
          <el-option label="停用" value="0" />
        </el-select>
      </el-form-item>
    </el-form>
    <el-table :data="pagedRows" v-loading="loading" stripe>
      <el-table-column prop="code" label="编码" width="120" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column label="业态" width="90">
        <template #default="{ row }">{{ row.is_business ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column prop="sort_order" label="排序" width="80" />
      <el-table-column label="启用" width="100">
        <template #default="{ row }">
          <el-switch :model-value="row.is_enabled" @change="(v: boolean) => toggle(row, v)" />
        </template>
      </el-table-column>
      <el-table-column prop="description" label="说明" min-width="220" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="filteredRows.length"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
      />
    </div>

    <el-dialog v-model="dialogVisible" title="编辑子系统" width="480px">
      <el-form label-width="80px">
        <el-form-item label="编码">
          <el-input :model-value="editing?.code" disabled />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.toolbar h3 {
  margin: 0;
}
.hint {
  color: var(--admin-ink-muted);
  font-size: 13px;
  margin: 0 0 16px;
}
.filters {
  margin-bottom: 4px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
