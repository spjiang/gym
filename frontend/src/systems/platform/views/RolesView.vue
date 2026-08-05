<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'
import { useAuthStore } from '../../../core/stores/auth'

type Role = {
  id: number
  code: string
  name: string
  merchant_id: number | null
  is_system: boolean
  permission_codes: string[]
  menu_codes: string[]
}
type Perm = { code: string; subsystem_code: string; name: string }
type Menu = { code: string; subsystem_code: string; name: string; path: string }
type Merchant = { id: number; name: string }

const auth = useAuthStore()
const roles = ref<Role[]>([])
const perms = ref<Perm[]>([])
const menus = ref<Menu[]>([])
const merchants = ref<Merchant[]>([])
const loading = ref(false)
const drawer = ref(false)
const editing = ref<Role | null>(null)
const grantPerms = ref<string[]>([])
const grantMenus = ref<string[]>([])
const creating = ref(false)
const form = reactive({
  code: '',
  name: '',
  merchant_id: undefined as number | undefined,
})

const isSiteAdmin = computed(() => auth.isSiteAdmin())

const permsBySystem = computed(() => {
  const map: Record<string, Perm[]> = {}
  for (const p of perms.value) {
    ;(map[p.subsystem_code] ||= []).push(p)
  }
  return map
})

const menusBySystem = computed(() => {
  const map: Record<string, Menu[]> = {}
  for (const m of menus.value) {
    ;(map[m.subsystem_code] ||= []).push(m)
  }
  return map
})

async function load() {
  loading.value = true
  try {
    const [r, p, m, ms] = await Promise.all([
      http.get('/rbac/roles'),
      http.get('/rbac/permission-defs'),
      http.get('/rbac/menu-defs'),
      http.get('/merchants'),
    ])
    roles.value = r.data
    perms.value = p.data
    menus.value = m.data
    merchants.value = ms.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openGrants(row: Role) {
  editing.value = row
  grantPerms.value = [...row.permission_codes]
  grantMenus.value = [...row.menu_codes]
  drawer.value = true
}

async function saveGrants() {
  if (!editing.value) return
  try {
    await http.put(`/rbac/roles/${editing.value.id}/grants`, {
      permission_codes: grantPerms.value,
      menu_codes: grantMenus.value,
    })
    ElMessage.success('授权已保存')
    drawer.value = false
    await load()
    await auth.fetchNavigation()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  }
}

async function createRole() {
  if (!form.code.trim() || !form.name.trim()) {
    ElMessage.warning('请填写编码与名称')
    return
  }
  creating.value = true
  try {
    const body: Record<string, unknown> = {
      code: form.code.trim(),
      name: form.name.trim(),
    }
    if (isSiteAdmin.value) {
      body.merchant_id = form.merchant_id ?? null
    }
    await http.post('/rbac/roles', body)
    ElMessage.success('角色已创建')
    form.code = ''
    form.name = ''
    form.merchant_id = undefined
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    creating.value = false
  }
}

async function removeRole(row: Role) {
  try {
    await ElMessageBox.confirm(`删除角色「${row.name}」？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await http.delete(`/rbac/roles/${row.id}`)
    ElMessage.success('已删除')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

function merchantName(id: number | null) {
  if (id == null) return '场地级'
  return merchants.value.find((m) => m.id === id)?.name || `#${id}`
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>角色权限</h3>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-card shadow="never" class="create-card">
      <div class="create-row">
        <el-input v-model="form.code" placeholder="角色编码" style="width: 160px" />
        <el-input v-model="form.name" placeholder="显示名称" style="width: 180px" />
        <el-select
          v-if="isSiteAdmin"
          v-model="form.merchant_id"
          clearable
          placeholder="场地级（空）或商户"
          style="width: 220px"
        >
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
        <el-button type="primary" :loading="creating" @click="createRole">新建角色</el-button>
      </div>
    </el-card>

    <el-table :data="roles" v-loading="loading" stripe style="margin-top: 16px">
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="范围" width="160">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
      <el-table-column label="系统" width="80">
        <template #default="{ row }">{{ row.is_system ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="权限数" width="90">
        <template #default="{ row }">{{ row.permission_codes.length }}</template>
      </el-table-column>
      <el-table-column label="菜单数" width="90">
        <template #default="{ row }">{{ row.menu_codes.length }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button size="small" @click="openGrants(row)">授权</el-button>
          <el-button size="small" :disabled="row.is_system" @click="removeRole(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-drawer v-model="drawer" :title="editing ? `授权 · ${editing.name}` : '授权'" size="520px">
      <h4>权限点</h4>
      <div v-for="(list, sys) in permsBySystem" :key="sys" class="group">
        <div class="group-title">{{ sys }}</div>
        <el-checkbox-group v-model="grantPerms">
          <el-checkbox v-for="p in list" :key="p.code" :label="p.code">{{ p.name }} ({{ p.code }})</el-checkbox>
        </el-checkbox-group>
      </div>
      <h4>可见菜单</h4>
      <div v-for="(list, sys) in menusBySystem" :key="'m' + sys" class="group">
        <div class="group-title">{{ sys }}</div>
        <el-checkbox-group v-model="grantMenus">
          <el-checkbox v-for="m in list" :key="m.code" :label="m.code">{{ m.name }}</el-checkbox>
        </el-checkbox-group>
      </div>
      <el-button type="primary" style="margin-top: 16px" @click="saveGrants">保存授权</el-button>
    </el-drawer>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.toolbar h3 {
  margin: 0;
}
.create-card {
  margin-top: 12px;
}
.create-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.group {
  margin-bottom: 14px;
}
.group-title {
  font-weight: 600;
  margin-bottom: 6px;
}
.el-checkbox {
  display: flex;
  margin: 4px 0;
}
</style>
