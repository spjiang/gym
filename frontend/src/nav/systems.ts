/** 子系统与菜单导航配置（中文注释） */

export type SystemId = 'platform' | 'gym'

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
}

/** 综合经营：入口侧配置、权限、主档与整体运营数据 */
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

/** 健身管理平台：会籍、课程、零售与器材等业态能力 */
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

export const allMenus: MenuItem[] = [...platformMenus, ...gymMenus]

export const subsystems: Subsystem[] = [
  {
    id: 'platform',
    name: '综合经营管理系统',
    shortName: '综合经营',
    description: '商户与权限配置、会员主档、门禁通行、整体订单与经营数据。',
    entryPath: '/merchants',
    anyOf: platformMenus.flatMap((m) => m.anyOf),
  },
  {
    id: 'gym',
    name: '健身管理平台',
    shortName: '健身管理',
    description: '会籍办卡、教练课程、零售营销与器材运维等健身房业态。',
    entryPath: '/products',
    anyOf: gymMenus.flatMap((m) => m.anyOf),
  },
]

export function canAny(mine: string[], need: string[]) {
  if (mine.includes('*')) return true
  return need.some((p) => p === '*' || mine.includes(p))
}

export function menusForSystem(system: SystemId, permissions: string[]) {
  const source = system === 'platform' ? platformMenus : gymMenus
  return source.filter((m) => canAny(permissions, m.anyOf))
}

export function visibleSubsystems(permissions: string[]) {
  return subsystems.filter((s) => canAny(permissions, s.anyOf))
}

export function findMenu(path: string) {
  return allMenus.find((m) => m.path === path)
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
