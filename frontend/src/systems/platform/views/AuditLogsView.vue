<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import http from '../../../core/api/http'
import {
  auditActionLabel,
  auditActorTypeLabel,
  auditClientChannelLabel,
  auditSubsystemLabel,
  auditTargetTypeLabel,
} from '../../../core/labels'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string }
type AuditLog = {
  id: number
  merchant_id: number | null
  merchant_name: string | null
  actor_staff_id: number | null
  actor_member_id: number | null
  actor_type: string | null
  actor_name: string | null
  actor_account: string | null
  subsystem_code: string | null
  module: string | null
  client_channel: string | null
  http_method: string | null
  request_path: string | null
  client_ip: string | null
  user_agent: string | null
  status: string | null
  status_code: number | null
  duration_ms: number | null
  action: string
  target_type: string
  target_id: string
  summary: string
  detail_json: Record<string, unknown> | null
  created_at: string
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const rows = ref<AuditLog[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const { merchantId } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})

const today = new Date().toISOString().slice(0, 10)
const query = reactive({
  q: '',
  action: '',
  target_type: '',
  subsystem_code: '',
  module: '',
  client_channel: '',
  actor_type: '',
  status: '',
  date_from: today,
  date_to: today,
})
const detailVisible = ref(false)
const detail = ref<AuditLog | null>(null)

const subsystemOptions = [
  { value: 'platform', label: '综合平台' },
  { value: 'gym', label: '观野FIT' },
  { value: 'catering', label: '观野BAR' },
  { value: 'member', label: '会员端' },
  { value: 'device', label: '门禁设备' },
]
const channelOptions = [
  { value: 'admin_web', label: '管理后台' },
  { value: 'member_h5', label: '会员 H5' },
  { value: 'member_mp', label: '微信小程序' },
  { value: 'device_pad', label: '门禁 Pad' },
  { value: 'webhook', label: '支付回调' },
]
const actorTypeOptions = [
  { value: 'staff', label: '员工' },
  { value: 'member', label: '会员' },
  { value: 'device', label: '设备' },
  { value: 'system', label: '系统' },
  { value: 'anonymous', label: '匿名' },
]

function fmtTime(iso: string) {
  return iso ? iso.slice(0, 19).replace('T', ' ') : '—'
}

function actorLabel(row: AuditLog) {
  const name = row.actor_name || row.actor_account
  if (name) {
    return `${auditActorTypeLabel(row.actor_type)} · ${name}`
  }
  if (row.actor_staff_id) return `员工 #${row.actor_staff_id}`
  if (row.actor_member_id) return `会员 #${row.actor_member_id}`
  return auditActorTypeLabel(row.actor_type)
}

function statusTagType(status: string | null) {
  if (status === 'success') return 'success'
  if (status === 'failure') return 'danger'
  return 'info'
}

async function refresh() {
  loading.value = true
  try {
    const { data: m } = await http.get<Merchant[]>('/merchants')
    merchants.value = m
    const { data } = await http.get<Page<AuditLog>>('/audit-logs', {
      params: {
        merchant_id: merchantId.value || undefined,
        q: query.q.trim() || undefined,
        action: query.action.trim() || undefined,
        target_type: query.target_type.trim() || undefined,
        subsystem_code: query.subsystem_code || undefined,
        module: query.module.trim() || undefined,
        client_channel: query.client_channel || undefined,
        actor_type: query.actor_type || undefined,
        status: query.status || undefined,
        date_from: query.date_from || undefined,
        date_to: query.date_to || undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    rows.value = data.items
    total.value = data.total
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
  query.action = ''
  query.target_type = ''
  query.subsystem_code = ''
  query.module = ''
  query.client_channel = ''
  query.actor_type = ''
  query.status = ''
  query.date_from = today
  query.date_to = today
  page.value = 1
  void refresh()
}

function openDetail(row: AuditLog) {
  detail.value = row
  detailVisible.value = true
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>操作日志</h3>
      <p class="hint">
        记录管理后台、会员 H5、微信小程序及设备端的全部写操作；可按业务子系统、客户端与操作人追溯。
      </p>
    </div>

    <div class="filters">
      <el-select
        v-model="merchantId"
        clearable
        placeholder="商户"
        style="width: 180px"
        @change="
          () => {
            page = 1
            refresh()
          }
        "
      >
        <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-select v-model="query.subsystem_code" clearable placeholder="业务子系统" style="width: 130px">
        <el-option v-for="o in subsystemOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-model="query.client_channel" clearable placeholder="客户端" style="width: 130px">
        <el-option v-for="o in channelOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-model="query.actor_type" clearable placeholder="操作人类型" style="width: 120px">
        <el-option v-for="o in actorTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-date-picker
        v-model="query.date_from"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="开始日期"
        style="width: 140px"
      />
      <el-date-picker
        v-model="query.date_to"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="结束日期"
        style="width: 140px"
      />
      <el-input v-model="query.module" clearable placeholder="操作模块" style="width: 130px" @keyup.enter="search" />
      <el-input v-model="query.action" clearable placeholder="操作编码" style="width: 140px" @keyup.enter="search" />
      <el-input
        v-model="query.q"
        clearable
        placeholder="摘要 / 账号 / 路径"
        style="width: 180px"
        @keyup.enter="search"
      />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe @row-dblclick="openDetail">
      <el-table-column prop="id" label="ID" width="64" />
      <el-table-column label="时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="子系统" width="96">
        <template #default="{ row }">{{ auditSubsystemLabel(row.subsystem_code) }}</template>
      </el-table-column>
      <el-table-column label="客户端" width="108">
        <template #default="{ row }">{{ auditClientChannelLabel(row.client_channel) }}</template>
      </el-table-column>
      <el-table-column prop="module" label="模块" width="108" show-overflow-tooltip />
      <el-table-column label="操作" width="160" show-overflow-tooltip>
        <template #default="{ row }">
          {{ auditActionLabel(row.action) }}
          <span class="muted-code">{{ row.action }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作人" width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ actorLabel(row) }}</template>
      </el-table-column>
      <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
      <el-table-column label="结果" width="72">
        <template #default="{ row }">
          <el-tag v-if="row.status" size="small" :type="statusTagType(row.status)">
            {{ row.status_code ?? row.status }}
          </el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="" width="72" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[20, 50, 100]"
        @current-change="refresh"
        @size-change="
          () => {
            page = 1
            refresh()
          }
        "
      />
    </div>

    <el-dialog v-model="detailVisible" title="操作详情" width="720px" destroy-on-close>
      <el-descriptions v-if="detail" :column="2" border>
        <el-descriptions-item label="时间" :span="2">{{ fmtTime(detail.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="业务子系统">
          {{ auditSubsystemLabel(detail.subsystem_code) }}
        </el-descriptions-item>
        <el-descriptions-item label="客户端">
          {{ auditClientChannelLabel(detail.client_channel) }}
        </el-descriptions-item>
        <el-descriptions-item label="操作模块">{{ detail.module || '—' }}</el-descriptions-item>
        <el-descriptions-item label="商户">{{ detail.merchant_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="操作">
          {{ auditActionLabel(detail.action) }}（{{ detail.action }}）
        </el-descriptions-item>
        <el-descriptions-item label="对象">
          {{ auditTargetTypeLabel(detail.target_type) }} #{{ detail.target_id }}
        </el-descriptions-item>
        <el-descriptions-item label="操作人类型">
          {{ auditActorTypeLabel(detail.actor_type) }}
        </el-descriptions-item>
        <el-descriptions-item label="操作人">
          {{ detail.actor_name || '—' }}
          <span v-if="detail.actor_account" class="muted-code">（{{ detail.actor_account }}）</span>
        </el-descriptions-item>
        <el-descriptions-item label="HTTP">{{ detail.http_method || '—' }}</el-descriptions-item>
        <el-descriptions-item label="路径" :span="2">{{ detail.request_path || '—' }}</el-descriptions-item>
        <el-descriptions-item label="IP">{{ detail.client_ip || '—' }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ detail.duration_ms != null ? `${detail.duration_ms} ms` : '—' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag v-if="detail.status" size="small" :type="statusTagType(detail.status)">
            {{ detail.status }} {{ detail.status_code ?? '' }}
          </el-tag>
          <span v-else>—</span>
        </el-descriptions-item>
        <el-descriptions-item label="User-Agent" :span="2">{{ detail.user_agent || '—' }}</el-descriptions-item>
        <el-descriptions-item label="摘要" :span="2">{{ detail.summary }}</el-descriptions-item>
        <el-descriptions-item v-if="detail.detail_json" label="请求详情" :span="2">
          <pre class="json-box">{{ JSON.stringify(detail.detail_json, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar h3 {
  margin: 0 0 4px;
}
.hint {
  margin: 0 0 16px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.muted-code {
  margin-left: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.json-box {
  margin: 0;
  max-height: 240px;
  overflow: auto;
  padding: 8px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
