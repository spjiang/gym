/** 导航辅助：菜单权威源改为 /me/navigation；此处保留类型与通用工具 */

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
  isBusiness: boolean
}

export const BUSINESS_SYSTEM_OPTIONS = [
  { value: 'gym', label: '健身管理' },
  { value: 'catering', label: '餐饮管理' },
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
  return menus.find((m) => m.path === path || path.startsWith(m.path + '/'))
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
