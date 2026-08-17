import { computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useOpsStore } from './ops'

/** 经营管理：商户可空表示全部；与顶栏筛选同步。 */
export function useOpsMerchant(onChange?: () => void) {
  const ops = useOpsStore()
  const merchantId = computed({
    get: () => ops.merchantId ?? undefined,
    set: (v: number | undefined) => ops.setMerchantId(v ?? null),
  })
  if (onChange) {
    watch(() => [ops.subsystem, ops.merchantId], () => onChange())
  }

  /** 写操作必须指定商户；列表检索可为空。 */
  function requireMerchant(message = '请先选择商户后再新建或收款') {
    if (ops.merchantId == null) {
      ElMessage.warning(message)
      return undefined
    }
    return ops.merchantId
  }

  return { ops, merchantId, requireMerchant }
}
