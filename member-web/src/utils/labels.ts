/** 会员端枚举中文标签 */

export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: '待支付',
  paid: '已支付',
  refunded: '已退款',
  cancelled: '已取消',
}

export const DINING_STATUS_LABELS: Record<string, string> = {
  preparing: '制作中',
  ready: '待取餐',
  completed: '已完成',
}

export const BOOKING_STATUS_LABELS: Record<string, string> = {
  booked: '已预约',
  cancelled: '已取消',
  attended: '已出勤',
  no_show: '未到',
}

export const ACTIVITY_REG_STATUS_LABELS: Record<string, string> = {
  pending: '待支付',
  confirmed: '已报名',
  cancelled: '已取消',
  attended: '已参加',
  no_show: '未到场',
}

export const COUPON_STATUS_LABELS: Record<string, string> = {
  unused: '未使用',
  used: '已使用',
  expired: '已过期',
}

export function orderStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return ORDER_STATUS_LABELS[code] || code
}

export function diningStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return DINING_STATUS_LABELS[code] || code
}

/** 餐饮订单对会员展示履约进度，未支付/退款仍用支付状态。 */
export function diningOrderLabel(order: { status: string; dining_status?: string | null }): string {
  if (order.status === 'paid') {
    return diningStatusLabel(order.dining_status || 'preparing')
  }
  return orderStatusLabel(order.status)
}

export type DiningBucket = 'all' | 'pending' | 'active' | 'done'

/** 订单列表筛选：待支付 / 进行中（制作或待取） / 已结束。 */
export function diningOrderBucket(order: { status: string; dining_status?: string | null }): DiningBucket {
  if (order.status === 'pending') return 'pending'
  if (order.status === 'paid') {
    const kitchen = order.dining_status || 'preparing'
    if (kitchen === 'preparing' || kitchen === 'ready') return 'active'
  }
  return 'done'
}

/** 会员端状态胶囊样式。 */
export function diningStatusTone(order: { status: string; dining_status?: string | null }): string {
  if (order.status === 'pending') return 'mw-status'
  if (order.status === 'refunded') return 'mw-status mw-status--danger'
  if (order.status === 'cancelled') return 'mw-status mw-status--neutral'
  if (order.status === 'paid' && (order.dining_status || 'preparing') === 'ready') {
    return 'mw-status mw-status--ok'
  }
  if (order.status === 'paid' && order.dining_status === 'completed') {
    return 'mw-status mw-status--ok'
  }
  return 'mw-status'
}

export function bookingStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return BOOKING_STATUS_LABELS[code] || code
}

export function activityRegStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return ACTIVITY_REG_STATUS_LABELS[code] || code
}

export function couponStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return COUPON_STATUS_LABELS[code] || code
}
