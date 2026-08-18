<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import { percentLabel } from '../../../core/labels'

type Account = {
  balance: string
  frozen_amount: string
  debt_amount: string
  total_earned: string
  total_withdrawn: string
  held_amount?: string
  available_balance?: string
}

type MemberPromotion = {
  member_id: number
  member_name: string
  code: string | null
  is_active: boolean
  rebate_rate: string
  downline_discount_rate: string
  rebate_rate_override: string | null
  downline_discount_rate_override: string | null
  link: string | null
  visit_count: number
  downline_count: number
  upline_member_name: string | null
  account: Account
}

type Downline = {
  member_id: number
  name: string
  phone: string
  joined_at: string
  order_count: number
  paid_amount: string
  rebate_amount: string
}

type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const route = useRoute()
const loading = ref(false)
const rows = ref<MemberPromotion[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ q: '', has_downline: undefined as boolean | undefined })

const dialog = ref(false)
const current = ref<MemberPromotion | null>(null)
const configForm = reactive({
  rebate_rate: '',
  downline_discount_rate: '',
  is_active: true,
})
const qrDataUrl = ref('')
const downlines = ref<Downline[]>([])
const downlineTotal = ref(0)
const submitting = ref(false)

async function refreshMembers() {
  loading.value = true
  try {
    const { data } = await http.get<Page<MemberPromotion>>('/member-promotions', {
      params: {
        q: query.q.trim() || undefined,
        has_downline: query.has_downline,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    rows.value = data.items
    total.value = data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void refreshMembers()
}

function resetSearch() {
  query.q = ''
  query.has_downline = undefined
  page.value = 1
  void refreshMembers()
}

async function renderQr(link: string | null | undefined) {
  qrDataUrl.value = ''
  if (!link) return
  try {
    const QRCode = (await import('qrcode')).default
    qrDataUrl.value = await QRCode.toDataURL(link, { width: 200, margin: 2 })
  } catch {
    qrDataUrl.value = ''
  }
}

async function openConfig(row: MemberPromotion) {
  current.value = row
  configForm.rebate_rate = row.rebate_rate_override ?? ''
  configForm.downline_discount_rate = row.downline_discount_rate_override ?? ''
  configForm.is_active = row.is_active || !row.code
  qrDataUrl.value = ''
  dialog.value = true
  try {
    // 打开即补发卡：历史会员建档时可能还没有推广码
    const { data } = await http.get<MemberPromotion>(`/members/${row.member_id}/promotion`)
    current.value = data
    configForm.rebate_rate = data.rebate_rate_override ?? ''
    configForm.downline_discount_rate = data.downline_discount_rate_override ?? ''
    configForm.is_active = data.is_active
    await renderQr(data.link)
    await refreshMembers()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载推广配置失败')
  }
  try {
    const { data } = await http.get<Page<Downline>>(`/members/${row.member_id}/downline`, {
      params: { page: 1, page_size: 20 },
    })
    downlines.value = data.items
    downlineTotal.value = data.total
  } catch {
    downlines.value = []
    downlineTotal.value = 0
  }
}

async function copyLink() {
  const url = current.value?.link
  if (!url) return
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('链接已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择链接')
  }
}

async function saveMemberConfig() {
  if (!current.value) return
  submitting.value = true
  try {
    const { data } = await http.patch<MemberPromotion>(`/members/${current.value.member_id}/promotion`, {
      rebate_rate: configForm.rebate_rate === '' ? null : configForm.rebate_rate,
      downline_discount_rate:
        configForm.downline_discount_rate === '' ? null : configForm.downline_discount_rate,
      is_active: configForm.is_active,
    })
    current.value = data
    ElMessage.success('会员推广配置已保存')
    dialog.value = false
    await refreshMembers()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const memberId = Number(route.query.member_id)
  await refreshMembers()
  if (!memberId) return
  const row = rows.value.find((item) => item.member_id === memberId)
  if (row) {
    await openConfig(row)
    return
  }
  try {
    const { data } = await http.get<MemberPromotion>(`/members/${memberId}/promotion`)
    await openConfig(data)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '未找到该会员的推广配置')
  }
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>推广方案</h3>
        <p class="lead">
          每个会员独立推广码、链接与二维码。扫码注册只挂一级下级；场地默认比例请到「推广配置」。
        </p>
      </div>
      <el-button @click="$router.push('/platform/promotion-config')">推广配置</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="姓名 / 手机 / 推广码" style="width: 200px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="下级">
        <el-select v-model="query.has_downline" clearable placeholder="全部" style="width: 120px">
          <el-option label="有下级" :value="true" />
          <el-option label="无下级" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="member_name" label="会员" min-width="120" />
      <el-table-column label="推广码" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.code" size="small" effect="plain">{{ row.code }}</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="返点" width="110">
        <template #default="{ row }">
          {{ percentLabel(row.rebate_rate) }}
          <span v-if="row.rebate_rate_override == null" class="sub">默认</span>
        </template>
      </el-table-column>
      <el-table-column label="下级折扣" width="110">
        <template #default="{ row }">
          {{ percentLabel(row.downline_discount_rate) }}
          <span v-if="row.downline_discount_rate_override == null" class="sub">默认</span>
        </template>
      </el-table-column>
      <el-table-column label="下级 / 访问" width="120">
        <template #default="{ row }">{{ row.downline_count }} 人 · {{ row.visit_count }} 次</template>
      </el-table-column>
      <el-table-column label="可提现余额" width="120">
        <template #default="{ row }">¥{{ row.account.available_balance ?? row.account.balance }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openConfig(row)">配置</el-button>
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
        @current-change="refreshMembers"
        @size-change="
          () => {
            page = 1
            refreshMembers()
          }
        "
      />
    </div>

    <el-dialog v-model="dialog" :title="`会员推广 · ${current?.member_name ?? ''}`" width="640px" destroy-on-close>
      <div class="config-grid">
        <div>
          <el-form label-width="120px">
            <el-form-item label="推广码">{{ current?.code || '正在发卡…' }}</el-form-item>
            <el-form-item label="返点比例">
              <el-input v-model="configForm.rebate_rate" placeholder="留空使用场地默认" />
            </el-form-item>
            <el-form-item label="下级折扣">
              <el-input v-model="configForm.downline_discount_rate" placeholder="留空使用场地默认" />
            </el-form-item>
            <el-form-item label="启用">
              <el-switch v-model="configForm.is_active" />
            </el-form-item>
            <el-form-item label="链接">
              <el-input :model-value="current?.link || ''" readonly>
                <template #append>
                  <el-button @click="copyLink">复制</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-form>
        </div>
        <div class="qr-box">
          <img v-if="qrDataUrl" :src="qrDataUrl" alt="推广二维码" />
          <p v-else-if="current?.link" class="hint">二维码生成中</p>
          <p v-else class="hint">正在发卡…</p>
        </div>
      </div>
      <h4 class="section-title">一级下级（{{ downlineTotal }}）</h4>
      <el-table :data="downlines" size="small" max-height="240" empty-text="暂无下级">
        <el-table-column prop="name" label="会员" />
        <el-table-column prop="phone" label="手机" width="130" />
        <el-table-column label="成交" width="90">
          <template #default="{ row }">{{ row.order_count }} 单</template>
        </el-table-column>
        <el-table-column label="实付" width="110">
          <template #default="{ row }">¥{{ row.paid_amount }}</template>
        </el-table-column>
        <el-table-column label="贡献返点" width="110">
          <template #default="{ row }">¥{{ row.rebate_amount }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveMemberConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.toolbar h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}
.lead {
  margin: 0 0 16px;
  max-width: 760px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.panel {
  margin-bottom: 20px;
}
.hint {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.section-title {
  margin: 8px 0 12px;
  font-size: 0.95rem;
}
.filters {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.sub {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.config-grid {
  display: grid;
  grid-template-columns: 1fr 200px;
  gap: 16px;
}
.qr-box {
  text-align: center;
}
.qr-box img {
  width: 200px;
  height: 200px;
}
</style>
