/** 会员端枚举中文标签（与 H5 labels.ts 对齐） */

const ORDER_STATUS_LABELS = {
  pending: '待支付',
  paid: '已支付',
  refunded: '已退款',
  cancelled: '已取消',
}

const DINING_STATUS_LABELS = {
  preparing: '制作中',
  ready: '待取餐',
  completed: '已完成',
}

const MEMBERSHIP_STATUS_LABELS = {
  active: '有效',
  frozen: '冻结',
  expired: '已过期',
  void: '作废',
  exhausted: '已用尽',
}

const MEMBERSHIP_TYPE_LABELS = {
  term: '期限卡',
  count: '次卡',
  value: '储值卡',
}

function orderStatusLabel(code) {
  if (!code) return '—'
  return ORDER_STATUS_LABELS[code] || code
}

function refundChannelLabel(channel) {
  return (
    {
      wechat_original: '退回微信',
      offline_cash: '现金',
      offline_transfer: '转账',
      online: '线上',
    }[channel] || channel || ''
  )
}

function refundStatusLabel(status) {
  return (
    {
      succeeded: '退款成功',
      processing: '退款中',
      created: '退款中',
      failed: '退款失败',
    }[status] || '退款'
  )
}

/** 会员订单在列表上的状态：退款中、退款成功、部分退款优先于已支付。 */
function memberOrderView(item) {
  const refunded = Number((item && item.refunded_amount) || 0)
  const amount = Number((item && item.amount) || 0)
  const refundStatus = (item && item.refund_status) || ''
  let statusText = item && item.dining_status ? diningOrderLabel(item) : orderStatusLabel(item && item.status)
  let statusTone = ''
  if (refundStatus === 'processing' || refundStatus === 'created') {
    statusText = '退款中'
    statusTone = 'warn'
  } else if (item && item.status === 'refunded') {
    statusText = '退款成功'
    statusTone = 'refund'
  } else if (refundStatus === 'succeeded' && amount > 0 && refunded >= amount) {
    statusText = '退款成功'
    statusTone = 'refund'
  } else if (refunded > 0 || refundStatus === 'succeeded') {
    statusText = '部分退款'
    statusTone = 'refund'
  } else if (refundStatus === 'failed') {
    statusText = '退款失败'
    statusTone = 'refund'
  }
  return {
    statusText,
    statusTone,
    showRefund: refunded > 0 || refundStatus === 'processing' || refundStatus === 'created' || refundStatus === 'succeeded',
  }
}

function diningStatusLabel(code) {
  if (!code) return '—'
  return DINING_STATUS_LABELS[code] || code
}

function diningOrderLabel(order) {
  if (!order) return '—'
  if (order.status === 'paid') {
    return diningStatusLabel(order.dining_status || 'preparing')
  }
  return orderStatusLabel(order.status)
}

function membershipStatusLabel(code) {
  if (!code) return '—'
  return MEMBERSHIP_STATUS_LABELS[code] || code
}

function membershipTypeLabel(code) {
  if (!code) return '—'
  return MEMBERSHIP_TYPE_LABELS[code] || code
}

function membershipStatusClass(code) {
  if (code === 'active') return 'status-ok'
  if (code === 'expired' || code === 'void' || code === 'exhausted') return 'status-danger'
  return 'status-neutral'
}

const COUPON_STATUS_LABELS = {
  unused: '未使用',
  used: '已使用',
  expired: '已过期',
  void: '已停用',
}

function couponStatusLabel(code) {
  if (!code) return '—'
  return COUPON_STATUS_LABELS[code] || code
}

function fmtDate(iso) {
  if (!iso) return '—'
  return String(iso).slice(0, 10)
}

module.exports = {
  orderStatusLabel,
  diningStatusLabel,
  diningOrderLabel,
  refundChannelLabel,
  refundStatusLabel,
  memberOrderView,
  membershipStatusLabel,
  membershipTypeLabel,
  membershipStatusClass,
  couponStatusLabel,
  fmtDate,
}
