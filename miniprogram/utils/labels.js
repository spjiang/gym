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

module.exports = {
  orderStatusLabel,
  diningStatusLabel,
  diningOrderLabel,
}
