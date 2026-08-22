/** 导航辅助：菜单权威源改为 /me/navigation；此处保留类型与通用工具 */

export type SystemId = 'platform' | 'gym' | 'catering'

/** 综合经营二级菜单分组；flat 表示独立一级、不套子菜单 */
export const PLATFORM_MENU_GROUPS: { key: string; label: string; paths: string[]; flat?: boolean }[] = [
  {
    key: 'order',
    label: '订单管理',
    paths: ['/orders', '/platform/payment-reconcile'],
  },
  {
    key: 'member',
    label: '会员管理',
    paths: ['/members'],
  },
  {
    key: 'visit',
    label: '访客管理',
    paths: ['/visits'],
  },
  {
    key: 'coupon',
    label: '优惠券管理',
    paths: ['/coupons/templates', '/coupons/issue'],
  },
  {
    key: 'promoter',
    label: '推广管理',
    paths: ['/platform/promotion-config', '/platform/promotion-settings', '/rebates', '/payouts'],
  },
  {
    key: 'devops',
    label: '运维管理',
    paths: ['/platform/audit-logs'],
  },
  {
    key: 'notify',
    label: '站内通知',
    paths: ['/notifications'],
    flat: true,
  },
  {
    key: 'device',
    label: '设备管理',
    paths: ['/access'],
  },
  {
    key: 'merchant',
    label: '商户管理',
    paths: ['/merchants', '/merchant-types'],
  },
  {
    key: 'rbac',
    label: '权限配置',
    paths: ['/platform/roles', '/staff'],
  },
  {
    key: 'base',
    label: '基础配置',
    paths: ['/platform/site-profile', '/platform/subsystems', '/platform/payment-settings', '/platform/sms-settings', '/platform/agreements', '/platform/commission-settings'],
  },
]

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
  isBusiness: boolean
}

/** 观野FIT 二级菜单：按会籍 / 团课 / 私教 / 零售 / 器材业务分组 */
export const GYM_MENU_GROUPS: { key: string; label: string; paths: string[]; flat?: boolean }[] = [
  {
    key: 'membership',
    label: '会籍管理',
    paths: ['/memberships', '/products'],
  },
    {
    key: 'group',
    label: '团课管理',
    paths: ['/group-courses', '/group-bookings', '/coach-desk', '/group-templates'],
  },
  {
    key: 'pt',
    label: '私教课管理',
    paths: ['/pt-packages', '/pt-products', '/pt-appointments'],
  },
  {
    key: 'activity',
    label: '活动管理',
    paths: ['/activities', '/activity-registrations'],
  },
  {
    key: 'coach',
    label: '教练管理',
    paths: ['/coaches'],
  },
  {
    key: 'sales',
    label: '销售管理',
    paths: ['/sales-reps'],
    flat: true,
  },
  {
    key: 'commission',
    label: '分成管理',
    paths: ['/commission-rules', '/commission-records', '/my-commission', '/platform/commission-settings'],
  },
  {
    key: 'retail',
    label: '零售管理',
    paths: ['/retail', '/retail-categories', '/retail-products'],
  },
  {
    key: 'equipment',
    label: '器材管理',
    paths: ['/equipment', '/equipment-repairs'],
  },
]

/** 挂在「经营管理」下，不作为 leftover 平铺 */
export const OPS_EXTRA_PATHS = ['/reports', '/ops']

export const BUSINESS_SYSTEM_OPTIONS = [
  { value: 'gym', label: '观野FIT' },
  { value: 'catering', label: '观野BAR' },
]

export function canAny(mine: string[], need: string[]) {
  if (mine.includes('*')) return true
  return need.some((p) => p === '*' || mine.includes(p))
}

export function defaultSubsystemsForTypeCode(code: string): string[] {
  if (code === 'bar') return ['catering']
  if (code === 'gym') return ['gym']
  return ['gym']
}

export type MerchantLike = { id: number; name: string; subsystem_codes?: string[] }

export function merchantsWithSystem<T extends MerchantLike>(list: T[], system: string): T[] {
  return list.filter((m) => (m.subsystem_codes || []).includes(system))
}

type AuthLike = {
  me: { permissions: string[] } | null
  navigation: {
    subsystems: { code: string; name: string; entry_path: string | null; is_business: boolean }[]
    menus: { path: string; name: string; subsystem_code: string; sort_order: number }[]
  } | null
}

export function menusForSystemFromNav(auth: AuthLike, system: string) {
  const menus = auth.navigation?.menus || []
  return menus
    .filter((m) => m.subsystem_code === system)
    .slice()
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((m) => ({ path: m.path, label: m.name, system: system as SystemId, anyOf: [] as string[] }))
}

export function findMenuFromNav(auth: AuthLike, path: string) {
  const menus = auth.navigation?.menus || []
  return menus.find((m) => m.path === path) || menus.find((m) => path.startsWith(m.path + '/'))
}

export function groupGymMenus(
  menus: { path: string; label: string; system: SystemId; anyOf: string[] }[],
) {
  const used = new Set<string>()
  const groups = GYM_MENU_GROUPS.map((g) => ({
    ...g,
    items: g.paths
      .map((path) => menus.find((m) => m.path === path))
      .filter((m): m is (typeof menus)[number] => {
        if (!m) return false
        used.add(m.path)
        return true
      }),
  })).filter((g) => g.items.length)
  const leftover = menus.filter((m) => !used.has(m.path))
  return { groups, leftover }
}

export function groupPlatformMenus(
  menus: { path: string; label: string; system: SystemId; anyOf: string[] }[],
) {
  const used = new Set<string>()
  const groups = PLATFORM_MENU_GROUPS.map((g) => ({
    ...g,
    items: menus.filter((m) => {
      const hit = g.paths.some((p) => m.path === p || m.path.startsWith(p + '/'))
      if (hit) used.add(m.path)
      return hit
    }),
  })).filter((g) => g.items.length)
  const leftover = menus.filter((m) => !used.has(m.path) && !OPS_EXTRA_PATHS.includes(m.path))
  return { groups, leftover }
}

export function firstAllowedPathFromNav(auth: AuthLike, preferredSystem?: string) {
  const menus = auth.navigation?.menus || []
  if (preferredSystem) {
    const hit = menus.find((m) => m.subsystem_code === preferredSystem)
    if (hit) return hit.path
  }
  if (menus[0]) return menus[0].path
  return '/portal'
}

/** 兼容旧调用名 */
export function firstAllowedPath(permissions: string[], preferredSystem?: SystemId) {
  void permissions
  void preferredSystem
  return '/portal'
}
