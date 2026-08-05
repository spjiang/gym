/** 管理端通用枚举中文标签（接口仍返回英文 code） */

export const ORDER_TYPE_LABELS: Record<string, string> = {
  membership: '会籍办卡',
  retail: '零售',
  pt: '私教',
  pt_package: '私教课包',
  group: '团课',
  dining: '餐饮消费',
  coupon: '优惠券',
  course_pack: '课程包',
}

export const PAYMENT_CHANNEL_LABELS: Record<string, string> = {
  online: '线上支付',
  wechat_original: '微信原路退',
  offline_cash: '现金',
  offline_transfer: '转账',
}

export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: '待支付',
  paid: '已收款',
  refunded: '已退款',
  cancelled: '已取消',
}

export const PAYMENT_MODE_LABELS: Record<string, string> = {
  unconfigured: '未配置',
  mock: '模拟支付',
  wechat: '微信支付',
}

/** 商户状态 */
export const MERCHANT_STATUS_LABELS: Record<string, string> = {
  preparing: '筹备',
  active: '营业',
  disabled: '停用',
  inactive: '停用',
}

export const VISIT_STATUS_LABELS: Record<string, string> = {
  active: '有效',
  revoked: '已撤销',
  expired: '已过期',
}

export const SESSION_STATUS_LABELS: Record<string, string> = {
  scheduled: '已排期',
  open: '可预约',
  closed: '已关闭',
  cancelled: '已取消',
  completed: '已结束',
}

export const BOOKING_STATUS_LABELS: Record<string, string> = {
  booked: '已预约',
  cancelled: '已取消',
  attended: '已出席',
  no_show: '未出席',
}

export const COUPON_STATUS_LABELS: Record<string, string> = {
  unused: '未使用',
  used: '已使用',
  expired: '已过期',
}

export const COUPON_APPLICABLE_LABELS: Record<string, string> = {
  both: '办卡+零售',
  retail: '仅零售',
  membership: '仅办卡',
}

export function orderTypeLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return ORDER_TYPE_LABELS[code] || code
}

export function paymentChannelLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return PAYMENT_CHANNEL_LABELS[code] || code
}

export function orderStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return ORDER_STATUS_LABELS[code] || code
}

export function paymentModeLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return PAYMENT_MODE_LABELS[code] || code
}

export function merchantStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return MERCHANT_STATUS_LABELS[code] || code
}

export function visitStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return VISIT_STATUS_LABELS[code] || code
}

export function sessionStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return SESSION_STATUS_LABELS[code] || code
}

export function bookingStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return BOOKING_STATUS_LABELS[code] || code
}

export function couponStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return COUPON_STATUS_LABELS[code] || code
}

export function couponApplicableLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return COUPON_APPLICABLE_LABELS[code] || code
}
