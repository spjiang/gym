export const GYM_APPLICABLE = new Set(['retail', 'membership', 'both', 'gym'])
export const CATERING_APPLICABLE = new Set(['dining', 'catering'])

export type CouponTemplate = {
  id: number
  merchant_id: number
  name: string
  discount_type: string
  threshold_amount: string
  fixed_amount: string | null
  percent_off: number | null
  applicable_to: string
  starts_at: string
  ends_at: string
  total_limit: number | null
  issued_count: number
  claimable: boolean
  per_member_limit: number
  is_active: boolean
}

export type MemberCoupon = {
  id: number
  merchant_id: number
  member_id: number
  template_id: number
  status: string
  starts_at: string
  ends_at: string
  used_order_id: number | null
  member?: { name: string; phone: string } | null
  template_name?: string | null
  discount_type?: string | null
  threshold_amount?: string | null
  fixed_amount?: string | null
  percent_off?: number | null
  applicable_to?: string | null
}

const APPLICABLE_SHORT: Record<string, string> = {
  both: '办卡+零售',
  gym: '办卡+零售',
  retail: '仅零售',
  membership: '仅办卡',
  dining: '餐饮',
  catering: '餐饮',
}

export function discountLabel(t: Pick<CouponTemplate, 'discount_type' | 'fixed_amount' | 'percent_off'>) {
  return t.discount_type === 'fixed' ? `减 ¥${t.fixed_amount}` : `${t.percent_off}% 折扣`
}

export function dateOnly(value?: string | null) {
  return value ? value.slice(0, 10) : '—'
}

export function discountRuleLabel(
  t: Pick<MemberCoupon, 'discount_type' | 'threshold_amount' | 'fixed_amount' | 'percent_off'>,
) {
  if (!t.discount_type) return ''
  const off = discountLabel({
    discount_type: t.discount_type,
    fixed_amount: t.fixed_amount ?? null,
    percent_off: t.percent_off ?? null,
  })
  const threshold = Number(t.threshold_amount ?? 0)
  return threshold > 0 ? `满 ¥${t.threshold_amount} ${off}` : off
}

export function memberCouponName(c: Pick<MemberCoupon, 'id' | 'template_name'>) {
  return c.template_name || `券#${c.id}`
}

export function memberCouponMeta(c: MemberCoupon) {
  const until = dateOnly(c.ends_at)
  return [
    discountRuleLabel(c),
    c.applicable_to ? APPLICABLE_SHORT[c.applicable_to] || c.applicable_to : '',
    until !== '—' ? `至 ${until}` : '',
  ]
    .filter(Boolean)
    .join(' · ')
}

export function memberCouponLabel(c: MemberCoupon) {
  const meta = memberCouponMeta(c)
  return meta ? `${memberCouponName(c)} · ${meta}` : memberCouponName(c)
}

const MIN_PAYABLE = 0.01

export type CouponQuote = {
  original: number
  discount: number
  payable: number
  usable: boolean
  reason: string
}

export function money(value: number | string | null | undefined) {
  const n = Number(value ?? 0)
  return Number.isFinite(n) ? n.toFixed(2) : '0.00'
}

export function moneyLabel(value: number | string | null | undefined) {
  return `¥${money(value)}`
}

function roundMoney(value: number) {
  return Number(value.toFixed(2))
}

function couponAppliesTo(applicableTo: string | null | undefined, orderType: 'membership' | 'retail') {
  if (!applicableTo) return true
  if (applicableTo === 'both' || applicableTo === 'gym') return true
  if (applicableTo === 'dining' || applicableTo === 'catering') return false
  return applicableTo === orderType
}

/** 与后端 compute_payable 对齐，用于收银预览。 */
export function quoteCoupon(
  original: number | string | null | undefined,
  coupon: MemberCoupon | null | undefined,
  orderType: 'membership' | 'retail' = 'membership',
): CouponQuote {
  const amount = Number(original ?? 0)
  const base = Number.isFinite(amount) && amount > 0 ? roundMoney(amount) : 0
  if (!coupon) {
    return { original: base, discount: 0, payable: base, usable: true, reason: '' }
  }
  if (!couponAppliesTo(coupon.applicable_to, orderType)) {
    return { original: base, discount: 0, payable: base, usable: false, reason: '该券不适用于本次消费' }
  }
  const threshold = Number(coupon.threshold_amount ?? 0)
  if (base < threshold) {
    return {
      original: base,
      discount: 0,
      payable: base,
      usable: false,
      reason: `未满 ${moneyLabel(threshold)}，暂不可用`,
    }
  }
  let discount = 0
  if (coupon.discount_type === 'fixed') {
    discount = Math.min(Number(coupon.fixed_amount ?? 0), base)
  } else if (coupon.discount_type === 'percent') {
    discount = roundMoney((base * Number(coupon.percent_off ?? 0)) / 100)
  }
  if (!(discount > 0)) {
    return { original: base, discount: 0, payable: base, usable: false, reason: '优惠金额无效' }
  }
  let payable = roundMoney(base - discount)
  if (payable < MIN_PAYABLE) {
    payable = MIN_PAYABLE
    discount = roundMoney(base - payable)
  }
  return { original: base, discount, payable, usable: true, reason: '' }
}
