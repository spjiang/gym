<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'

type Settings = {
  site_id: number
  auto_create_member_code: boolean
  default_rebate_rate: string
  default_downline_discount_rate: string
  min_withdraw_amount: string
  withdraw_hold_days: number
  configured: boolean
}

const loading = ref(false)
const saving = ref(false)
const settings = ref<Settings | null>(null)
const form = reactive({
  auto_create_member_code: true,
  default_rebate_rate: '0',
  default_downline_discount_rate: '0',
  min_withdraw_amount: '1.00',
  withdraw_hold_days: 0,
})

function toRateInput(value: string | number | null | undefined) {
  const n = Number(value || 0)
  if (!Number.isFinite(n)) return '0'
  return String(n)
}

async function loadSettings() {
  loading.value = true
  try {
    const { data } = await http.get<Settings>('/promotion-settings')
    settings.value = data
    form.auto_create_member_code = data.auto_create_member_code
    form.default_rebate_rate = toRateInput(data.default_rebate_rate)
    form.default_downline_discount_rate = toRateInput(data.default_downline_discount_rate)
    form.min_withdraw_amount = data.min_withdraw_amount
    form.withdraw_hold_days = Number(data.withdraw_hold_days || 0)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载推广配置失败')
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const { data } = await http.put<Settings>('/promotion-settings', {
      auto_create_member_code: form.auto_create_member_code,
      default_rebate_rate: form.default_rebate_rate,
      default_downline_discount_rate: form.default_downline_discount_rate,
      min_withdraw_amount: form.min_withdraw_amount,
      withdraw_hold_days: Number(form.withdraw_hold_days || 0),
    })
    settings.value = data
    ElMessage.success('推广配置已保存')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadSettings()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>推广配置</h3>
        <p class="lead">
          场地默认返点、下级折扣与提现规则。会员码未单独覆盖时使用此处比例。返点进入会员余额，只能提现，不能抵消费。
        </p>
      </div>
    </div>

    <el-card v-loading="loading" shadow="never" class="panel">
      <el-form :model="form" label-width="180px" style="max-width: 720px">
        <el-form-item label="自动生成会员推广码">
          <el-switch v-model="form.auto_create_member_code" />
          <span class="hint">建档或首次打开「我的推广」时发卡</span>
        </el-form-item>
        <el-form-item label="默认返点比例">
          <el-input v-model="form.default_rebate_rate" style="width: 160px" placeholder="0.05 表示 5%" />
          <span class="hint">下级实付金额 × 该比例计入上级返点余额</span>
        </el-form-item>
        <el-form-item label="默认下级折扣">
          <el-input
            v-model="form.default_downline_discount_rate"
            style="width: 160px"
            placeholder="0.1 表示 9 折"
          />
          <span class="hint">下级消费减免比例，最大 0.9</span>
        </el-form-item>
        <el-form-item label="最低提现金额">
          <el-input v-model="form.min_withdraw_amount" style="width: 160px" />
        </el-form-item>
        <el-form-item label="返点后多少天可提现">
          <el-input-number v-model="form.withdraw_hold_days" :min="0" :max="365" :step="1" />
          <span class="hint">0 表示即时可提。建议 7 天，降低先提现再退款产生欠额</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="saveSettings">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
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
</style>
