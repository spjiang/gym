<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Merchant = { id: number; name: string }
type Template = {
  id: number
  name: string
  discount_type: string
  threshold_amount: string
  fixed_amount: string | null
  percent_off: number | null
  applicable_to: string
  starts_at: string
  ends_at: string
  total_limit: number | null
  issued_count: number
  claimable: boolean
  per_member_limit: number
  is_active: boolean
}
type MemberCoupon = {
  id: number
  member_id: number
  template_id: number
  status: string
  starts_at: string
  ends_at: string
  used_order_id: number | null
}

const merchants = ref<Merchant[]>([])
const templates = ref<Template[]>([])
const memberCoupons = ref<MemberCoupon[]>([])
const merchantId = ref<number | undefined>()
const filterMemberId = ref<number | undefined>()

const form = reactive({
  name: '满100减20',
  discount_type: 'fixed',
  threshold_amount: '100',
  fixed_amount: '20',
  percent_off: 10,
  applicable_to: 'both',
  days: 30,
  total_limit: undefined as number | undefined,
  claimable: false,
  per_member_limit: 1,
})
const issueForm = reactive({
  template_id: undefined as number | undefined,
  member_id: undefined as number | undefined,
})

function templateLabel(id: number) {
  return templates.value.find((t) => t.id === id)?.name ?? `#${id}`
}

async function refresh() {
  const { data: m } = await http.get('/merchants')
  merchants.value = m
  if (!merchantId.value && m[0]) merchantId.value = m[0].id
  if (!merchantId.value) return
  const [t, c] = await Promise.all([
    http.get('/coupons/templates', { params: { merchant_id: merchantId.value } }),
    http.get('/coupons/member-coupons', {
      params: {
        merchant_id: merchantId.value,
        member_id: filterMemberId.value || undefined,
      },
    }),
  ])
  templates.value = t.data
  memberCoupons.value = c.data
}

async function createTemplate() {
  const starts = new Date()
  const ends = new Date()
  ends.setDate(ends.getDate() + form.days)
  await http.post('/coupons/templates', {
    merchant_id: merchantId.value,
    name: form.name,
    discount_type: form.discount_type,
    threshold_amount: form.threshold_amount,
    fixed_amount: form.discount_type === 'fixed' ? form.fixed_amount : null,
    percent_off: form.discount_type === 'percent' ? form.percent_off : null,
    applicable_to: form.applicable_to,
    starts_at: starts.toISOString(),
    ends_at: ends.toISOString(),
    total_limit: form.total_limit ?? null,
    claimable: form.claimable,
    per_member_limit: form.per_member_limit,
  })
  ElMessage.success('模板已创建')
  await refresh()
}

async function issueCoupon() {
  await http.post('/coupons/issue', {
    merchant_id: merchantId.value,
    template_id: issueForm.template_id,
    member_id: issueForm.member_id,
  })
  ElMessage.success('已发券')
  await refresh()
}

async function deactivate(id: number) {
  await http.post(`/coupons/templates/${id}/deactivate`)
  ElMessage.success('已停用')
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div>
    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-card header="新建券模板" style="margin-bottom: 12px">
      <el-form inline>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.discount_type" style="width: 110px">
            <el-option label="满减" value="fixed" />
            <el-option label="折扣" value="percent" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.discount_type === 'fixed'" label="减免">
          <el-input v-model="form.fixed_amount" style="width: 100px" />
        </el-form-item>
        <el-form-item v-else label="折扣%">
          <el-input-number v-model="form.percent_off" :min="1" :max="99" />
        </el-form-item>
        <el-form-item label="门槛">
          <el-input v-model="form.threshold_amount" style="width: 100px" />
        </el-form-item>
        <el-form-item label="适用">
          <el-select v-model="form.applicable_to" style="width: 130px">
            <el-option label="办卡+零售" value="both" />
            <el-option label="仅零售" value="retail" />
            <el-option label="仅办卡" value="membership" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效天">
          <el-input-number v-model="form.days" :min="1" />
        </el-form-item>
        <el-form-item label="总库存">
          <el-input-number v-model="form.total_limit" :min="1" clearable />
        </el-form-item>
        <el-form-item label="可领">
          <el-switch v-model="form.claimable" />
        </el-form-item>
        <el-form-item label="每人限">
          <el-input-number v-model="form.per_member_limit" :min="1" :max="100" />
        </el-form-item>
        <el-button type="primary" @click="createTemplate">创建</el-button>
      </el-form>
    </el-card>

    <el-card header="券模板" style="margin-bottom: 12px">
      <el-table :data="templates" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="discount_type" label="类型" width="80" />
        <el-table-column label="面额" width="100">
          <template #default="{ row }">
            {{ row.discount_type === 'fixed' ? row.fixed_amount : `${row.percent_off}%` }}
          </template>
        </el-table-column>
        <el-table-column prop="threshold_amount" label="门槛" width="90" />
        <el-table-column prop="applicable_to" label="适用" width="110" />
        <el-table-column label="已发/库存" width="110">
          <template #default="{ row }">
            {{ row.issued_count }} / {{ row.total_limit ?? '∞' }}
          </template>
        </el-table-column>
        <el-table-column label="可领/限" width="90">
          <template #default="{ row }">
            {{ row.claimable ? `是/${row.per_member_limit}` : '否' }}
          </template>
        </el-table-column>
        <el-table-column label="启用" width="70">
          <template #default="{ row }">{{ row.is_active ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button v-if="row.is_active" link type="danger" @click="deactivate(row.id)">停用</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card header="发券给会员" style="margin-bottom: 12px">
      <el-form inline>
        <el-select
          v-model="issueForm.template_id"
          placeholder="模板"
          filterable
          style="width: 220px; margin-right: 8px"
        >
          <el-option
            v-for="t in templates.filter((x) => x.is_active)"
            :key="t.id"
            :label="`#${t.id} ${t.name}`"
            :value="t.id"
          />
        </el-select>
        <el-input-number v-model="issueForm.member_id" :min="1" placeholder="会员ID" />
        <el-button type="primary" style="margin-left: 8px" @click="issueCoupon">发券</el-button>
      </el-form>
    </el-card>

    <el-card header="会员持券">
      <el-form inline style="margin-bottom: 8px">
        <el-input-number v-model="filterMemberId" :min="1" placeholder="会员ID" />
        <el-button style="margin-left: 8px" @click="refresh">筛选</el-button>
      </el-form>
      <el-table :data="memberCoupons" stripe>
        <el-table-column prop="id" label="券ID" width="80" />
        <el-table-column prop="member_id" label="会员" width="90" />
        <el-table-column label="模板">
          <template #default="{ row }">{{ templateLabel(row.template_id) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column label="有效至" width="120">
          <template #default="{ row }">{{ row.ends_at?.slice(0, 10) }}</template>
        </el-table-column>
        <el-table-column prop="used_order_id" label="核销订单" width="100" />
      </el-table>
    </el-card>
  </div>
</template>
