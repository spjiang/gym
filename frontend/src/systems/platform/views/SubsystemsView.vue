<script setup lang="ts">
import { onMounted, ref } from 'vue'
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

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>子系统配置</h3>
      <el-button @click="load">刷新</el-button>
    </div>
    <p class="hint">启停会影响全场导航与菜单；能力目录由各子系统代码注册，不可在此手造权限码。</p>
    <el-table :data="rows" v-loading="loading" stripe>
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
    </el-table>
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
</style>
