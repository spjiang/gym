/** 会员端枚举中文标签 */

export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: '待支付',
  paid: '已支付',
  refunded: '已退款',
  cancelled: '已取消',
}

export const BOOKING_STATUS_LABELS: Record<string, string> = {
  booked: '已预约',
  cancelled: '已取消',
  attended: '已出勤',
  no_show: '未到',
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

export function bookingStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return BOOKING_STATUS_LABELS[code] || code
}

export function couponStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return COUPON_STATUS_LABELS[code] || code
}
