<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'
import { useAuthStore } from '../../../core/stores/auth'

type Role = {
  id: number
  code: string
  name: string
  merchant_id: number | null
  is_site_scope: boolean
  is_system: boolean
  permission_codes: string[]
  menu_codes: string[]
}

/** 范围筛选：场地级 / 角色模板 / 具体商户 id */
type ScopeFilter = '' | 'site' | 'template' | number
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
const createVisible = ref(false)
const query = reactive({
  q: '',
  scope: '' as ScopeFilter,
  code_prefix: '' as string,
  perm_q: '',
  is_system: '' as string,
  wildcard_only: false,
})
const form = reactive({
  code: '',
  name: '',
  merchant_id: undefined as number | undefined,
})

const page = ref(1)
const pageSize = ref(20)
const filteredRoles = computed(() => {
  return roles.value.filter((r) => {
    const kw = query.q.trim().toLowerCase()
    if (kw && !r.code.toLowerCase().includes(kw) && !r.name.toLowerCase().includes(kw)) return false

    if (query.scope === 'site') {
      if (!(r.merchant_id == null && r.is_site_scope)) return false
    } else if (query.scope === 'template') {
      if (!(r.merchant_id == null && r.code.startsWith('tpl_'))) return false
    } else if (typeof query.scope === 'number' && r.merchant_id !== query.scope) {
      return false
    }

    if (query.code_prefix && !r.code.startsWith(query.code_prefix)) return false

    const permKw = query.perm_q.trim().toLowerCase()
    if (permKw && !r.permission_codes.some((p) => p.toLowerCase().includes(permKw))) return false

    if (query.is_system === '1' && !r.is_system) return false
    if (query.is_system === '0' && r.is_system) return false

    if (query.wildcard_only && !r.permission_codes.includes('*')) return false

    return true
  })
})
const pagedRoles = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRoles.value.slice(start, start + pageSize.value)
})
watch(query, () => {
  page.value = 1
}, { deep: true })

function resetRoleSearch() {
  query.q = ''
  query.scope = ''
  query.code_prefix = ''
  query.perm_q = ''
  query.is_system = ''
  query.wildcard_only = false
  page.value = 1
}

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
    createVisible.value = false
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

function scopeLabel(row: Role) {
  if (row.merchant_id != null) {
    return merchants.value.find((m) => m.id === row.merchant_id)?.name || `#${row.merchant_id}`
  }
  if (row.is_site_scope) return '场地级'
  if (row.code.startsWith('tpl_gym_')) return '健身房 · 模板'
  if (row.code.startsWith('tpl_bar_')) return '清吧 · 模板'
  if (row.code.startsWith('tpl_')) return '角色模板'
  return '未绑定商户'
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>角色配置</h3>
      <div>
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="createVisible = true">新建角色</el-button>
      </div>
    </div>

    <div class="filters">
      <el-input v-model="query.q" clearable placeholder="编码 / 名称" style="width: 180px" />
      <el-select v-if="isSiteAdmin" v-model="query.scope" clearable placeholder="范围" style="width: 180px">
        <el-option label="场地级" value="site" />
        <el-option label="角色模板" value="template" />
        <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-select v-model="query.code_prefix" clearable placeholder="编码前缀" style="width: 140px">
        <el-option label="site_" value="site_" />
        <el-option label="tpl_" value="tpl_" />
        <el-option label="gym_" value="gym_" />
        <el-option label="bar_" value="bar_" />
      </el-select>
      <el-input v-model="query.perm_q" clearable placeholder="权限关键字" style="width: 160px" />
      <el-select v-model="query.is_system" clearable placeholder="是否系统角色" style="width: 140px">
        <el-option label="系统角色" value="1" />
        <el-option label="自定义" value="0" />
      </el-select>
      <el-checkbox v-model="query.wildcard_only">仅超管权限</el-checkbox>
      <el-button @click="resetRoleSearch">重置</el-button>
    </div>

    <el-table :data="pagedRoles" v-loading="loading" stripe style="margin-top: 16px">
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="范围" width="160">
        <template #default="{ row }">{{ scopeLabel(row) }}</template>
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

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="filteredRoles.length"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
      />
    </div>

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

    <el-dialog v-model="createVisible" title="新建角色" width="480px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="角色编码">
          <el-input v-model="form.code" placeholder="如 gym_cashier" />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item v-if="isSiteAdmin" label="所属范围">
          <el-select v-model="form.merchant_id" clearable placeholder="场地级（空）或商户" style="width: 100%">
            <el-option :value="undefined" label="场地级" />
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createRole">创建</el-button>
      </template>
    </el-dialog>
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
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
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
