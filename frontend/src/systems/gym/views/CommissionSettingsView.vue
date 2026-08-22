<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'

type Settings = {
  site_id: number
  settle_hold_days: number
  remark: string | null
}

type Debt = {
  id: number
  beneficiary_type: string
  beneficiary_id: number
  beneficiary_name: string
  debt_amount: string
}

const loading = ref(false)
const saving = ref(false)
const recoveringId = ref<number | null>(null)
const form = reactive({
  settle_hold_days: 0,
  remark: '',
})
const debts = ref<Debt[]>([])
const recoverForm = reactive({
  amount: '',
  note: '',
})

const typeLabel: Record<string, string> = {
  staff: '员工',
  coach: '教练',
  member: '会员',
}

async function load() {
  loading.value = true
  try {
    const [s, d] = await Promise.all([
      http.get<Settings>('/site/commission-settings'),
      http.get<Debt[]>('/commission-debts'),
    ])
    form.settle_hold_days = Number(s.data.settle_hold_days || 0)
    form.remark = s.data.remark || ''
    debts.value = d.data || []
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    await http.put('/site/commission-settings', {
      settle_hold_days: Number(form.settle_hold_days || 0),
      remark: form.remark.trim() || null,
    })
    ElMessage.success('分成配置已保存')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function recover(row: Debt) {
  const amount = Number(recoverForm.amount)
  if (!Number.isFinite(amount) || amount <= 0) {
    ElMessage.error('请填写追回金额')
    return
  }
  recoveringId.value = row.id
  try {
    await http.post('/commission-debts/recover', {
      beneficiary_type: row.beneficiary_type,
      beneficiary_id: row.beneficiary_id,
      amount: amount.toFixed(2),
      note: recoverForm.note.trim() || null,
    })
    ElMessage.success('已登记现金追回')
    recoverForm.amount = ''
    recoverForm.note = ''
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '追回失败')
  } finally {
    recoveringId.value = null
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar">
      <div>
        <h3>分成配置</h3>
        <p class="lead">
          场地级政策：提成计提后满 N 天才可结算或提现，降低先打款再退款。已打款后退款记欠额，下次结算自动抵扣。
        </p>
      </div>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </div>

    <el-form label-width="160px" style="max-width: 640px">
      <el-form-item label="结算冷却天数">
        <el-input-number v-model="form.settle_hold_days" :min="0" :max="365" :step="1" />
        <span class="hint">0 表示确认后可立即结算。与推广返点冷却相互独立。</span>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" maxlength="255" show-word-limit placeholder="选填" />
      </el-form-item>
    </el-form>

    <h4 class="section">待追回欠额</h4>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
      title="已打款提成对应订单退款后，在此挂账。下次结算或教练提现会优先抵扣；也可登记线下现金追回。"
    />
    <el-table :data="debts" stripe empty-text="当前没有待追回欠额">
      <el-table-column label="受益人" min-width="180">
        <template #default="{ row }">
          <div>{{ row.beneficiary_name || '—' }}</div>
          <div class="sub">{{ typeLabel[row.beneficiary_type] || row.beneficiary_type }} #{{ row.beneficiary_id }}</div>
        </template>
      </el-table-column>
      <el-table-column label="欠额" width="140">
        <template #default="{ row }">¥{{ row.debt_amount }}</template>
      </el-table-column>
      <el-table-column label="登记追回" min-width="280">
        <template #default="{ row }">
          <el-button
            size="small"
            :loading="recoveringId === row.id"
            @click="recover(row)"
          >
            按下方金额追回
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-form inline class="recover" style="margin-top: 12px">
      <el-form-item label="追回金额">
        <el-input v-model="recoverForm.amount" placeholder="0.00" style="width: 140px" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="recoverForm.note" placeholder="现金/转账凭证" style="width: 240px" />
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.toolbar h3,
.section {
  margin: 0 0 6px;
}
.lead,
.hint,
.sub {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.hint {
  margin-left: 12px;
}
.section {
  margin: 28px 0 12px;
}
</style>
