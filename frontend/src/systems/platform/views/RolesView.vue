<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'
import { auditSubsystemLabel } from '../../../core/labels'
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
const grantVisible = ref(false)
const grantTab = ref<'perms' | 'menus'>('perms')
const grantSearch = ref('')
const savingGrants = ref(false)
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

function filterGrantItems<T extends { code: string; name: string }>(items: T[]) {
  const kw = grantSearch.value.trim().toLowerCase()
  if (!kw) return items
  return items.filter((item) => item.name.toLowerCase().includes(kw) || item.code.toLowerCase().includes(kw))
}

const filteredPermsBySystem = computed(() => {
  const out: Record<string, Perm[]> = {}
  for (const [sys, list] of Object.entries(permsBySystem.value)) {
    const filtered = filterGrantItems(list)
    if (filtered.length) out[sys] = filtered
  }
  return out
})

const filteredMenusBySystem = computed(() => {
  const out: Record<string, Menu[]> = {}
  for (const [sys, list] of Object.entries(menusBySystem.value)) {
    const filtered = filterGrantItems(list)
    if (filtered.length) out[sys] = filtered
  }
  return out
})

const grantPermCount = computed(() => grantPerms.value.length)
const grantMenuCount = computed(() => grantMenus.value.length)

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
  grantTab.value = 'perms'
  grantSearch.value = ''
  grantVisible.value = true
}

function closeGrants() {
  grantVisible.value = false
}

function permCodesInView(sys: string) {
  return (filteredPermsBySystem.value[sys] || []).map((p) => p.code)
}

function menuCodesInView(sys: string) {
  return (filteredMenusBySystem.value[sys] || []).map((m) => m.code)
}

function selectedCountIn(codes: string[], selected: string[]) {
  return codes.filter((code) => selected.includes(code)).length
}

function isPermGroupAll(sys: string) {
  const codes = permCodesInView(sys)
  return codes.length > 0 && codes.every((code) => grantPerms.value.includes(code))
}

function isPermGroupIndeterminate(sys: string) {
  const codes = permCodesInView(sys)
  const hit = selectedCountIn(codes, grantPerms.value)
  return hit > 0 && hit < codes.length
}

function isMenuGroupAll(sys: string) {
  const codes = menuCodesInView(sys)
  return codes.length > 0 && codes.every((code) => grantMenus.value.includes(code))
}

function isMenuGroupIndeterminate(sys: string) {
  const codes = menuCodesInView(sys)
  const hit = selectedCountIn(codes, grantMenus.value)
  return hit > 0 && hit < codes.length
}

function togglePermGroup(sys: string, checked: boolean) {
  const codes = permCodesInView(sys)
  if (checked) {
    grantPerms.value = [...new Set([...grantPerms.value, ...codes])]
    return
  }
  grantPerms.value = grantPerms.value.filter((code) => !codes.includes(code))
}

function toggleMenuGroup(sys: string, checked: boolean) {
  const codes = menuCodesInView(sys)
  if (checked) {
    grantMenus.value = [...new Set([...grantMenus.value, ...codes])]
    return
  }
  grantMenus.value = grantMenus.value.filter((code) => !codes.includes(code))
}

function selectAllPerms() {
  grantPerms.value = perms.value.map((p) => p.code)
}

function selectAllMenus() {
  grantMenus.value = menus.value.map((m) => m.code)
}

function clearGrantPerms() {
  grantPerms.value = []
}

function clearGrantMenus() {
  grantMenus.value = []
}

async function saveGrants() {
  if (!editing.value) return
  savingGrants.value = true
  try {
    await http.put(`/rbac/roles/${editing.value.id}/grants`, {
      permission_codes: grantPerms.value,
      menu_codes: grantMenus.value,
    })
    ElMessage.success('授权已保存')
    grantVisible.value = false
    await load()
    await auth.fetchNavigation()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    savingGrants.value = false
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
          <el-button size="small" type="primary" plain @click="openGrants(row)">授权</el-button>
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

    <el-dialog
      v-model="grantVisible"
      class="grant-dialog"
      width="760px"
      top="4vh"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <template #header>
        <div class="grant-dialog__title">
          <span>角色授权</span>
          <span v-if="editing" class="grant-dialog__role">{{ editing.name }}</span>
        </div>
      </template>

      <div class="grant-dialog__inner">
        <div v-if="editing" class="grant-summary">
          <div class="grant-summary__main">
            <div class="grant-summary__name">{{ editing.name }}</div>
            <div class="grant-summary__meta">
              <span class="grant-tag">{{ editing.code }}</span>
              <span>{{ scopeLabel(editing) }}</span>
              <span v-if="editing.is_system">系统内置</span>
            </div>
          </div>
          <div class="grant-summary__stats">
            <span class="grant-pill">权限 {{ grantPermCount }}</span>
            <span class="grant-pill">菜单 {{ grantMenuCount }}</span>
          </div>
        </div>

        <div class="grant-toolbar">
          <el-input
            v-model="grantSearch"
            clearable
            placeholder="搜索权限或菜单名称、编码"
            :prefix-icon="Search"
          />
          <div class="grant-toolbar__actions">
            <el-button v-if="grantTab === 'perms'" link type="primary" @click="selectAllPerms">全选权限</el-button>
            <el-button v-else link type="primary" @click="selectAllMenus">全选菜单</el-button>
            <el-button v-if="grantTab === 'perms'" link @click="clearGrantPerms">清空权限</el-button>
            <el-button v-else link @click="clearGrantMenus">清空菜单</el-button>
          </div>
        </div>

        <el-tabs v-model="grantTab" class="grant-tabs">
        <el-tab-pane name="perms">
          <template #label>
            <span>权限点</span>
            <el-tag size="small" round type="info" class="grant-tab-tag">{{ grantPermCount }}</el-tag>
          </template>
          <div class="grant-body">
            <el-alert
              v-if="grantPerms.includes('*')"
              title="已勾选超管通配权限 *，该角色拥有全部操作权限"
              type="warning"
              :closable="false"
              show-icon
              class="grant-alert"
            />
            <div v-for="(list, sys) in filteredPermsBySystem" :key="sys" class="grant-group">
              <div class="grant-group__head">
                <el-checkbox
                  :model-value="isPermGroupAll(sys)"
                  :indeterminate="isPermGroupIndeterminate(sys)"
                  @change="(checked: boolean) => togglePermGroup(sys, checked)"
                >
                  <span class="grant-group__title">{{ auditSubsystemLabel(sys) }}</span>
                  <span class="grant-group__count">
                    {{ selectedCountIn(permCodesInView(sys), grantPerms) }}/{{ list.length }}
                  </span>
                </el-checkbox>
              </div>
              <el-checkbox-group v-model="grantPerms" class="grant-grid">
                <el-checkbox v-for="p in list" :key="p.code" :label="p.code" class="grant-item">
                  <span class="grant-item__name">{{ p.name }}</span>
                  <span class="grant-item__code">{{ p.code }}</span>
                </el-checkbox>
              </el-checkbox-group>
            </div>
            <el-empty v-if="!Object.keys(filteredPermsBySystem).length" description="无匹配权限" />
          </div>
        </el-tab-pane>

        <el-tab-pane name="menus">
          <template #label>
            <span>可见菜单</span>
            <el-tag size="small" round type="info" class="grant-tab-tag">{{ grantMenuCount }}</el-tag>
          </template>
          <div class="grant-body">
            <div v-for="(list, sys) in filteredMenusBySystem" :key="'m' + sys" class="grant-group">
              <div class="grant-group__head">
                <el-checkbox
                  :model-value="isMenuGroupAll(sys)"
                  :indeterminate="isMenuGroupIndeterminate(sys)"
                  @change="(checked: boolean) => toggleMenuGroup(sys, checked)"
                >
                  <span class="grant-group__title">{{ auditSubsystemLabel(sys) }}</span>
                  <span class="grant-group__count">
                    {{ selectedCountIn(menuCodesInView(sys), grantMenus) }}/{{ list.length }}
                  </span>
                </el-checkbox>
              </div>
              <el-checkbox-group v-model="grantMenus" class="grant-grid">
                <el-checkbox v-for="m in list" :key="m.code" :label="m.code" class="grant-item">
                  <span class="grant-item__name">{{ m.name }}</span>
                  <span class="grant-item__code">{{ m.path }}</span>
                </el-checkbox>
              </el-checkbox-group>
            </div>
            <el-empty v-if="!Object.keys(filteredMenusBySystem).length" description="无匹配菜单" />
          </div>
        </el-tab-pane>
      </el-tabs>
      </div>

      <template #footer>
        <div class="grant-footer">
          <span class="grant-footer__hint">保存后立即影响该角色下所有员工的菜单与操作权限</span>
          <div class="grant-footer__actions">
            <el-button @click="closeGrants">取消</el-button>
            <el-button type="primary" :loading="savingGrants" @click="saveGrants">保存授权</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

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

.grant-dialog__title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: var(--admin-ink);
}

.grant-dialog__role {
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--admin-accent-soft);
  color: var(--admin-accent);
  font-size: 13px;
  font-weight: 600;
}

.grant-summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  margin-bottom: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: linear-gradient(180deg, #fffaf3 0%, #f7f2ea 100%);
}

.grant-summary__name {
  font-size: 15px;
  font-weight: 700;
  color: var(--admin-ink);
}

.grant-summary__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--admin-ink-muted);
}

.grant-tag {
  padding: 1px 8px;
  border-radius: 6px;
  background: rgba(23, 27, 31, 0.06);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.grant-summary__stats {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.grant-pill {
  padding: 4px 10px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter);
  font-size: 12px;
  font-weight: 600;
  color: var(--admin-accent);
  white-space: nowrap;
}

.grant-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.grant-toolbar .el-input {
  flex: 1;
}

.grant-toolbar__actions {
  display: flex;
  flex-shrink: 0;
  gap: 4px;
}

.grant-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.grant-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
  flex-shrink: 0;
}

.grant-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
}

.grant-tabs :deep(.el-tab-pane) {
  height: 100%;
}

.grant-tab-tag {
  margin-left: 6px;
  vertical-align: middle;
}

.grant-body {
  height: 100%;
  max-height: 100%;
  overflow: auto;
  padding: 10px 2px 4px;
}

.grant-alert {
  margin-bottom: 12px;
}

.grant-group {
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: #fff;
}

.grant-group__head {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}

.grant-group__title {
  font-weight: 700;
  color: var(--admin-ink);
}

.grant-group__count {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 500;
  color: var(--admin-ink-muted);
}

.grant-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
}

.grant-item {
  display: flex;
  align-items: flex-start;
  margin: 0;
  height: auto;
  white-space: normal;
}

.grant-item :deep(.el-checkbox__label) {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.35;
  white-space: normal;
}

.grant-item__name {
  font-size: 13px;
  color: var(--admin-ink);
}

.grant-item__code {
  font-size: 11px;
  color: var(--admin-ink-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.grant-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.grant-footer__hint {
  font-size: 12px;
  color: var(--admin-ink-muted);
}

.grant-footer__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

@media (max-width: 860px) {
  .grant-grid {
    grid-template-columns: 1fr;
  }

  .grant-summary {
    flex-direction: column;
  }

  .grant-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .grant-footer {
    flex-direction: column;
    align-items: flex-end;
  }
}
</style>

<style>
.grant-dialog.el-dialog {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 48px);
  margin-bottom: 24px;
}

.grant-dialog .el-dialog__header,
.grant-dialog .el-dialog__footer {
  flex-shrink: 0;
}

.grant-dialog .el-dialog__body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding-top: 8px;
  padding-bottom: 12px;
}

.grant-dialog__inner {
  display: flex;
  flex-direction: column;
  height: min(62vh, calc(100vh - 280px));
  min-height: 280px;
}
</style>
