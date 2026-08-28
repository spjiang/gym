export type BrandKey = 'space' | 'fit' | 'bar'
export type ArticleChannel = 'news' | 'jobs' | 'partners'

export type Contact = {
  address: string | null
  service_phone: string | null
  business_hours: string | null
}

export type SiteBlock = {
  display_name: string
  seo_title: string
  seo_description: string | null
  logo_url: string | null
  member_web_url: string | null
  miniprogram_hint: string | null
  footer_note: string | null
  icp_beian: string | null
}

export type HomeBlock = {
  hero_image_url: string | null
  headline: string | null
  subheadline: string | null
  show_space: boolean
  show_fit: boolean
  show_bar: boolean
}

export type BrandBlock = {
  key: BrandKey
  title: string
  cover_image_url: string | null
  body: string | null
  gallery_image_urls: string[]
  cta_label: string | null
  cta_url: string | null
}

export type NewsBrief = {
  id: number
  title: string
  summary: string | null
  cover_image_url: string | null
  published_at: string | null
  channel: ArticleChannel
}

export type PublicWebsite = {
  site: SiteBlock
  home: HomeBlock
  brands: Record<BrandKey, BrandBlock>
  contact: Contact
  latest_news: NewsBrief[]
}

export type ArticleDetail = NewsBrief & {
  body: string
  contact_hint: string | null
  status: string
}

export type Page<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
}
