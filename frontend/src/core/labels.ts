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
  seller: '销售（挂靠会员）',
  coach: '教练',
  referrer: '推荐会员',
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

/** 操作日志：action 中文 */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  'order.pay_offline': '线下收款',
  'order.pay_online': '线上支付',
  'order.refund': '订单退款',
  'member.register': '会员注册',
  'member.login': '会员登录',
  'member.otp_send': '发送验证码',
  'member.create': '创建会员',
  'member.update': '更新会员',
  'member.delete': '删除会员',
  'member.import': '导入会员',
  'member.avatar': '更新头像',
  'member.avatar_clear': '清除头像',
  'member.password_reset': '重置会员密码',
  'member.link_merchant': '关联商户',
  'member.membership_order': '会员会籍下单',
  'member.pt_order': '会员私教下单',
  'member.pay_online': '会员线上支付',
  'staff.create': '创建员工',
  'staff.update': '更新员工',
  'staff.roles_update': '调整员工角色',
  'staff.password_reset': '重置员工密码',
  'merchant.create': '创建商户',
  'merchant.update': '更新商户',
  'merchant.subsystems_update': '更新商户子系统',
  'merchant_type.create': '创建商户类型',
  'merchant_type.update': '更新商户类型',
  'grant.create': '创建通行授权',
  'grant.revoke': '撤销通行授权',
  upsert: '同步门禁',
  revoke: '撤销门禁',
  'visit.create': '创建访客',
  'visit.update': '更新访客',
  'visit.delete': '删除访客',
  'visit.revoke': '撤销访客',
  'rbac.role_create': '创建角色',
  'rbac.role_grants': '调整角色权限',
  'rbac.subsystem_patch': '更新子系统配置',
  'site.profile_update': '更新场地资料',
  'payment_settings.update': '更新支付配置',
  'payment_settings.import_env': '导入支付环境',
  'sms_settings.update': '更新短信配置',
  'sms_template.create': '创建短信模板',
  'agreement.create': '创建协议',
  'agreement.update': '更新协议',
  'promotion.settings_update': '更新推广设置',
  'promotion.member_config': '更新会员推广配置',
  'rebate.adjust': '调整返点',
  'payout.request': '申请提现',
  'payout.approve': '审核通过提现',
  'payout.reject': '驳回提现',
  'payout.paid': '登记打款',
  'reconcile.close_intent': '关闭支付意图',
  'reconcile.force_fulfill': '强制履约',
  'reconcile.force_refund_success': '强制退款成功',
  'membership_product.create': '创建会籍产品',
  'membership_product.update': '更新会籍产品',
  'membership.purchase_order': '会籍办卡下单',
  'membership.renew_order': '会籍续费下单',
  'membership.fulfill': '会籍履约',
  'membership.update': '更新会籍',
  'membership.freeze': '冻结会籍',
  'membership.consume': '会籍扣次',
  'membership.void': '作废会籍',
  'coach.create': '创建教练',
  'coach.update': '更新教练',
  'coach.deactivate': '停用教练',
  'group_course.create': '创建团课',
  'group_course.update': '更新团课',
  'group_session.create': '创建团课场次',
  'group_session.update': '更新团课场次',
  'group_session.delete': '删除团课场次',
  'group_session.reassign': '改派团课场次',
  'group.book': '团课预约',
  'group.cancel': '取消团课预约',
  'group.checkin': '团课签到',
  'pt_product.create': '创建私教产品',
  'pt_product.update': '更新私教产品',
  'pt_product.activate': '启用私教产品',
  'pt.purchase_order': '私教下单',
  'pt.fulfill': '私教履约',
  'pt.consume': '私教扣次',
  'pt.update': '更新私教课包',
  'pt.void_on_refund': '退款作废私教',
  'pt_appointment.create': '创建私教预约',
  'pt_appointment.reschedule': '改期私教预约',
  'pt_appointment.cancel': '取消私教预约',
  'pt_appointment.complete': '完成私教预约',
  'pt_appointment.no_show': '私教未到',
  'activity.create': '创建活动',
  'activity.update': '更新活动',
  publish: '发布活动',
  close: '关闭活动',
  cancel: '取消活动',
  'activity.register': '活动报名',
  'activity.registration_confirmed': '确认活动报名',
  'activity.registration_cancel': '取消活动报名',
  'activity.registration_refunded': '活动报名退款',
  'activity.checkin': '活动签到',
  'activity.no_show': '活动未到',
  'retail.sku_create': '创建零售 SKU',
  'retail.order_create': '零售下单',
  'retail.fulfill': '零售履约',
  'retail.restock': '零售补货',
  'retail.stock_in': '零售入库',
  'retail.stock_out': '零售出库',
  'retail.stock_adjust': '零售库存调整',
  'equipment.create': '创建设备',
  'equipment.repair_open': '报修设备',
  'equipment.repair_complete': '完成设备维修',
  'coupon.template_create': '创建优惠券模板',
  'coupon.template_update': '更新优惠券模板',
  'coupon.issue': '发放优惠券',
  'coupon.issue_batch': '批量发放优惠券',
  'coupon.member_update': '更新会员券',
  'coupon.member_deactivate': '停用会员券',
  'coupon.redeem': '核销优惠券',
  'coupon.restore': '恢复优惠券',
  'coupon.claim': '领取优惠券',
  'commission_rule.create': '创建提成规则',
  'commission_rule.update': '更新提成规则',
  'commission_rule.delete': '删除提成规则',
  'commission_record.status': '更新提成状态',
  'commission_record.batch_status': '批量更新提成',
  'commission_settings.update': '更新提成设置',
  'commission_debt.recover': '追回提成欠款',
  'sales_rep.create': '创建销售',
  'sales_rep.update': '更新销售',
  'sales_rep.deactivate': '停用销售',
  'catering.category_create': '创建餐饮分类',
  'catering.category_update': '更新餐饮分类',
  'catering.menu_create': '创建菜品',
  'catering.menu_update': '更新菜品',
  'catering.table_create': '创建餐桌',
  'catering.table_update': '更新餐桌',
  'catering.checkout': '餐饮结账',
  'catering.ready': '餐饮出餐',
  'catering.complete': '餐饮完成',
  'catering.undo': '餐饮撤销',
  'catering.cancel': '餐饮取消',
  'member.dining_checkout': '会员餐饮结账',
}

/** 操作日志：target_type 中文 */
export const AUDIT_TARGET_TYPE_LABELS: Record<string, string> = {
  order: '订单',
  member: '会员',
  staff: '员工',
  merchant: '商户',
  merchant_type: '商户类型',
  access_grant: '通行授权',
  visit_pass: '访客',
  role: '角色',
  subsystem: '子系统',
  site: '场地',
  site_payment_settings: '支付配置',
  site_sms_settings: '短信配置',
  site_promotion_settings: '推广设置',
  site_commission_settings: '提成设置',
  sms_template: '短信模板',
  legal_agreement: '协议',
  promoter_code: '推广码',
  payout: '提现单',
  payment_intent: '支付意图',
  refund_intent: '退款意图',
  membership: '会籍',
  membership_product: '会籍产品',
  coach: '教练',
  group_course: '团课',
  group_session: '团课场次',
  group_booking: '团课预约',
  pt_product: '私教产品',
  pt_package: '私教课包',
  pt_appointment: '私教预约',
  activity: '活动',
  activity_registration: '活动报名',
  retail_sku: '零售 SKU',
  equipment_asset: '设备',
  equipment_repair_ticket: '设备报修',
  coupon_template: '优惠券模板',
  member_coupon: '会员优惠券',
  commission_rule: '提成规则',
  commission_record: '提成记录',
  commission_debt_account: '提成欠款',
  sales_rep: '销售',
  catering_menu_category: '餐饮分类',
  catering_menu_item: '菜品',
  catering_table: '餐桌',
}

export function auditActionLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return AUDIT_ACTION_LABELS[code] || code
}

export function auditTargetTypeLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return AUDIT_TARGET_TYPE_LABELS[code] || code
}

export const AUDIT_SUBSYSTEM_LABELS: Record<string, string> = {
  platform: '综合平台',
  gym: '观野FIT',
  catering: '观野BAR',
  member: '会员端',
  device: '门禁设备',
}

export const AUDIT_CLIENT_CHANNEL_LABELS: Record<string, string> = {
  admin_web: '管理后台',
  member_h5: '会员 H5',
  member_mp: '微信小程序',
  device_pad: '门禁 Pad',
  webhook: '支付回调',
  internal: '系统内部',
  unknown: '未知客户端',
}

export const AUDIT_ACTOR_TYPE_LABELS: Record<string, string> = {
  staff: '员工',
  member: '会员',
  device: '设备',
  system: '系统',
  anonymous: '匿名',
}

export function auditSubsystemLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return AUDIT_SUBSYSTEM_LABELS[code] || code
}

export function auditClientChannelLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return AUDIT_CLIENT_CHANNEL_LABELS[code] || code
}

export function auditActorTypeLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return AUDIT_ACTOR_TYPE_LABELS[code] || code
}

/** 小数比例展示为百分数，0.05 → 5% */
export function percentLabel(rate: string | number | null | undefined): string {
  const n = Number(rate || 0)
  if (!Number.isFinite(n)) return '—'
  return `${(n * 100).toFixed(2).replace(/\.?0+$/, '')}%`
}
