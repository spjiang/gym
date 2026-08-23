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

function fmtDate(iso) {
  if (!iso) return '—'
  return String(iso).slice(0, 10)
}

module.exports = {
  orderStatusLabel,
  diningStatusLabel,
  diningOrderLabel,
  membershipStatusLabel,
  membershipTypeLabel,
  membershipStatusClass,
  fmtDate,
}
