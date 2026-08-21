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
  activity: '活动报名',
}

export const PAYMENT_CHANNEL_LABELS: Record<string, string> = {
  online: '线上支付',
  wechat_original: '微信原路退',
  jdpay_original: '微信原路退',
  offline_cash: '现金',
  offline_transfer: '转账',
}

export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: '待支付',
  paid: '已收款',
  refunded: '已退款',
  cancelled: '已取消',
}

export const DINING_STATUS_LABELS: Record<string, string> = {
  preparing: '制作中',
  ready: '待取餐',
  completed: '已完成',
}

export const PAYMENT_MODE_LABELS: Record<string, string> = {
  unconfigured: '未配置',
  mock: '模拟支付',
  wechat: '微信支付',
  jdpay: '微信支付',
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
  void: '已停用',
}

export const COUPON_APPLICABLE_LABELS: Record<string, string> = {
  both: '观野FIT·办卡+零售',
  gym: '观野FIT·办卡+零售',
  retail: '观野FIT·仅零售',
  membership: '观野FIT·仅办卡',
  dining: '观野BAR消费',
  catering: '观野BAR消费',
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

export function diningStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return DINING_STATUS_LABELS[code] || code
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

export const PT_PACKAGE_STATUS_LABELS: Record<string, string> = {
  active: '使用中',
  exhausted: '已用尽',
  expired: '已过期',
  void: '已作废',
}

export function ptPackageStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return PT_PACKAGE_STATUS_LABELS[code] || code
}

export const ACTIVITY_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  published: '报名中',
  closed: '已停止报名',
  cancelled: '已取消',
}

export const REGISTRATION_STATUS_LABELS: Record<string, string> = {
  pending: '待付款',
  confirmed: '已确认',
  attended: '已签到',
  cancelled: '已取消',
  no_show: '未到场',
}

export const PT_APPOINTMENT_STATUS_LABELS: Record<string, string> = {
  booked: '待上课',
  completed: '已完成',
  cancelled: '已取消',
  no_show: '未到场',
}

export const COMMISSION_SCOPE_LABELS: Record<string, string> = {
  membership_sale: '会籍销售',
  pt_sale: '私教课包销售',
  retail_sale: '零售销售',
  activity_sale: '活动报名',
  group_session: '团课课时',
  pt_session: '私教课时',
  referral: '推荐成交',
}

export const COMMISSION_BENEFICIARY_LABELS: Record<string, string> = {
  seller: '销售员工',
  coach: '教练',
  referrer: '推荐人',
}

export const COMMISSION_BASIS_LABELS: Record<string, string> = {
  percent: '按金额比例',
  fixed: '按笔固定',
  per_head: '按出席人头',
  per_session: '按课时',
}

export const COMMISSION_CATEGORY_LABELS: Record<string, string> = {
  sale: '销售提成',
  session: '课时提成',
  referral: '推荐提成',
}

export const COMMISSION_STATUS_LABELS: Record<string, string> = {
  pending: '待确认',
  confirmed: '已确认',
  paid: '已结算',
  void: '已作废',
}

export const BENEFICIARY_TYPE_LABELS: Record<string, string> = {
  staff: '员工',
  coach: '教练',
  member: '会员',
}

export const REBATE_LEDGER_KIND_LABELS: Record<string, string> = {
  earn: '下级消费入账',
  reverse: '退款冲回',
  withdraw_freeze: '提现冻结',
  withdraw_paid: '提现打款',
  withdraw_revert: '提现退回',
  adjust: '人工调整',
}

export const PAYOUT_STATUS_LABELS: Record<string, string> = {
  requested: '待审核',
  approved: '已通过待打款',
  paid: '已打款',
  rejected: '已驳回',
}

export const PAYOUT_SOURCE_LABELS: Record<string, string> = {
  commission: '教练佣金',
  rebate: '会员返点',
}

export const PAYOUT_METHOD_LABELS: Record<string, string> = {
  offline_cash: '现金',
  offline_transfer: '转账',
  other: '其他',
}

export function activityStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return ACTIVITY_STATUS_LABELS[code] || code
}

export function registrationStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return REGISTRATION_STATUS_LABELS[code] || code
}

export function ptAppointmentStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return PT_APPOINTMENT_STATUS_LABELS[code] || code
}

export function commissionScopeLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return COMMISSION_SCOPE_LABELS[code] || code
}

export function commissionBeneficiaryLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return COMMISSION_BENEFICIARY_LABELS[code] || code
}

export function commissionBasisLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return COMMISSION_BASIS_LABELS[code] || code
}

export function commissionCategoryLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return COMMISSION_CATEGORY_LABELS[code] || code
}

export function commissionStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return COMMISSION_STATUS_LABELS[code] || code
}

export function beneficiaryTypeLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return BENEFICIARY_TYPE_LABELS[code] || code
}

export function rebateLedgerKindLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return REBATE_LEDGER_KIND_LABELS[code] || code
}

export function payoutStatusLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return PAYOUT_STATUS_LABELS[code] || code
}

export function payoutSourceLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return PAYOUT_SOURCE_LABELS[code] || code
}

export function payoutMethodLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return PAYOUT_METHOD_LABELS[code] || code
}

/** 小数比例展示为百分数，0.05 → 5% */
export function percentLabel(rate: string | number | null | undefined): string {
  const n = Number(rate || 0)
  if (!Number.isFinite(n)) return '—'
  return `${(n * 100).toFixed(2).replace(/\.?0+$/, '')}%`
}
