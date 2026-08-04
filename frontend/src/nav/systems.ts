/** 子系统与菜单导航配置（中文注释）——产品级业态隔离 */

export type SystemId = 'platform' | 'gym' | 'catering'

export type MenuItem = {
  path: string
  label: string
  anyOf: string[]
  system: SystemId
}

export type Subsystem = {
  id: SystemId
  name: string
  shortName: string
  description: string
  entryPath: string
  anyOf: string[]
  /** 是否为可挂到商户上的业态子系统 */
  isBusiness: boolean
}

/** 综合经营：场地级组织、权限、主档与跨业态数据 */
export const platformMenus: MenuItem[] = [
  { path: '/merchants', label: '商户组织', anyOf: ['org:read', '*'], system: 'platform' },
  { path: '/staff', label: '员工与权限', anyOf: ['staff:manage', '*'], system: 'platform' },
  { path: '/members', label: '会员主档', anyOf: ['member:read', '*'], system: 'platform' },
  { path: '/access', label: '门禁设备', anyOf: ['access:read', '*'], system: 'platform' },
  { path: '/visits', label: '临访登记', anyOf: ['access:manage', 'access:read', '*'], system: 'platform' },
  { path: '/orders', label: '订单收款', anyOf: ['order:read', '*'], system: 'platform' },
  { path: '/reports', label: '经营报表', anyOf: ['report:read', '*'], system: 'platform' },
  { path: '/notifications', label: '站内通知', anyOf: ['order:read', 'member:read', 'access:read', '*'], system: 'platform' },
]

/** 健身管理平台 */
export const gymMenus: MenuItem[] = [
  { path: '/products', label: '会籍卡种', anyOf: ['membership:manage', 'membership:sell', '*'], system: 'gym' },
  { path: '/memberships', label: '办卡会籍', anyOf: ['membership:manage', 'membership:sell', '*'], system: 'gym' },
  { path: '/coaches', label: '教练档案', anyOf: ['coach:manage', '*'], system: 'gym' },
  { path: '/pt-packages', label: '私教课包', anyOf: ['pt:sell', 'course:manage', '*'], system: 'gym' },
  { path: '/group-courses', label: '团课排课', anyOf: ['course:manage', 'course:book', '*'], system: 'gym' },
  { path: '/coach-desk', label: '教练工作台', anyOf: ['course:checkin', 'course:manage', '*'], system: 'gym' },
  { path: '/retail', label: '零售库存', anyOf: ['retail:read', 'retail:sell', 'retail:manage', '*'], system: 'gym' },
  { path: '/coupons', label: '优惠券', anyOf: ['coupon:read', 'coupon:manage', '*'], system: 'gym' },
  { path: '/equipment', label: '器材台账', anyOf: ['equipment:read', 'equipment:manage', 'equipment:repair', '*'], system: 'gym' },
]

/** 餐饮管理系统（清吧等） */
export const cateringMenus: MenuItem[] = [
  { path: '/catering/menu', label: '餐饮菜单', anyOf: ['catering:menu', 'order:write', '*'], system: 'catering' },
  { path: '/catering/orders', label: '点单收款', anyOf: ['catering:order', 'order:read', 'order:write', '*'], system: 'catering' },
]

export const allMenus: MenuItem[] = [...platformMenus, ...gymMenus, ...cateringMenus]

export const subsystems: Subsystem[] = [
  {
    id: 'platform',
    name: '综合经营管理系统',
    shortName: '综合经营',
    description: '商户与权限配置、会员主档、门禁通行、跨业态订单与经营数据。',
    entryPath: '/merchants',
    anyOf: ['system:platform', 'org:read', '*'],
    isBusiness: false,
  },
  {
    id: 'gym',
    name: '健身管理平台',
    shortName: '健身管理',
    description: '会籍办卡、教练课程、健身零售、营销与器材运维。',
    entryPath: '/products',
    anyOf: ['system:gym', '*'],
    isBusiness: true,
  },
  {
    id: 'catering',
    name: '餐饮管理系统',
    shortName: '餐饮管理',
    description: '清吧/餐饮菜单维护、点单下单与收款退款闭环。',
    entryPath: '/catering/menu',
    anyOf: ['system:catering', 'catering:menu', 'catering:order', '*'],
    isBusiness: true,
  },
]

export const BUSINESS_SYSTEM_OPTIONS = [
  { value: 'gym', label: '健身管理' },
  { value: 'catering', label: '餐饮管理' },
]

export function canAny(mine: string[], need: string[]) {
  if (mine.includes('*')) return true
  return need.some((p) => p === '*' || mine.includes(p))
}

export function menusForSystem(system: SystemId, permissions: string[]) {
  const source =
    system === 'platform' ? platformMenus : system === 'gym' ? gymMenus : cateringMenus
  return source.filter((m) => canAny(permissions, m.anyOf))
}

/**
 * 门户可见子系统：
 * - 场地超管（*）：全部
 * - 商户员工：权限命中，且（非业态系统 或 本商户已关联该业态）
 */
export function visibleSubsystems(
  permissions: string[],
  merchantSubsystemCodes?: string[] | null,
) {
  return subsystems.filter((s) => {
    if (!canAny(permissions, s.anyOf)) return false
    if (!s.isBusiness) return true
    if (permissions.includes('*')) return true
    if (!merchantSubsystemCodes || merchantSubsystemCodes.length === 0) {
      // 未取到商户关联时，仍按权限展示（超管以外尽量保守：有 system 权限才显示）
      return canAny(permissions, [s.anyOf[0]])
    }
    return merchantSubsystemCodes.includes(s.id)
  })
}

export function findMenu(path: string) {
  return allMenus.find((m) => m.path === path || path.startsWith(m.path + '/'))
}

export function firstAllowedPath(permissions: string[], preferredSystem?: SystemId) {
  if (preferredSystem) {
    const hit = menusForSystem(preferredSystem, permissions)[0]
    if (hit) return hit.path
  }
  for (const s of visibleSubsystems(permissions)) {
    const hit = menusForSystem(s.id, permissions)[0]
    if (hit) return hit.path
  }
  return '/portal'
}

/** 默认业态：按商户类型编码 */
export function defaultSubsystemsForTypeCode(code: string): string[] {
  if (code === 'bar') return ['catering']
  if (code === 'gym') return ['gym']
  return ['gym']
}

export type MerchantLike = { id: number; name: string; subsystem_codes?: string[] }

/** 按业态子系统过滤商户下拉（健身页不出现清吧等） */
export function merchantsWithSystem<T extends MerchantLike>(list: T[], system: string): T[] {
  return list.filter((m) => (m.subsystem_codes || []).includes(system))
}
