/** 观野品牌：SPACE / FIT / BAR */

export type BrandVariant = 'space' | 'fit' | 'bar'

export const BRAND = {
  cn: '观野',
  space: 'SPACE',
  fit: 'FIT',
  bar: 'BAR',
  platformName: '观野SPACE 综合管理平台',
  logo: '观野SPACE',
  gym: '观野FIT',
  barName: '观野BAR',
  tagline: {
    space: 'SPORTS · EVENTS · COMMUNITY',
    fit: 'TRAIN · RECOVER · BELONG',
    bar: 'NIGHTS · MUSIC · COMMUNITY',
  },
} as const

export function brandVariantForSystem(code: string | undefined | null): BrandVariant {
  if (code === 'gym') return 'fit'
  if (code === 'catering') return 'bar'
  return 'space'
}

export function brandLabelForSystem(code: string | undefined | null): string {
  if (code === 'gym') return BRAND.gym
  if (code === 'catering') return BRAND.barName
  return BRAND.logo
}
