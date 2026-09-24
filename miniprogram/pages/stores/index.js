Page({
  data: {
    loading: true,
    err: '',
    siteName: '观野SPACE',
    siteTagline: '选择门店，进入对应业态',
    memberName: '',
    phoneMasked: '',
    slides: [],
    slide: 0,
    facts: [],
    sections: [],
    aboutText: '',
    gallery: [],
  },
  _timer: null,
  async onShow() {
    const { requireLogin, refreshMemberSession } = require('../../utils/session')
    const { systemOf } = require('../../utils/merchant')
    const { request, fileUrl } = require('../../utils/api')
    if (!requireLogin()) return
    this.setData({ loading: true, err: '' })
    try {
      const me = await refreshMemberSession()
      let site = null
      try {
        site = await request({ url: '/member/site' })
      } catch (e) {
        site = null
      }
      const buckets = { gym: [], catering: [], other: [] }
      ;(me.merchants || []).forEach((m) => {
        const sys = systemOf(m)
        const item = {
          id: m.id,
          name: m.name,
          tagline: m.tagline,
          cover_image_url: m.cover_image_url,
          subsystem_codes: m.subsystem_codes,
          primary_system: m.primary_system,
          coverUrl: fileUrl(m.cover_image_url),
          badge: sys === 'catering' ? '观野BAR' : sys === 'gym' ? '观野FIT' : '其它门店',
          mark: sys === 'catering' ? 'BAR' : sys === 'gym' ? 'FIT' : 'STORE',
          hint:
            m.tagline ||
            (sys === 'gym' ? '训练即生活' : sys === 'catering' ? '夜色刚刚开始' : '进入查看可用服务'),
          sectionKey: sys === 'catering' || sys === 'gym' ? sys : 'other',
        }
        if (sys === 'gym') buckets.gym.push(item)
        else if (sys === 'catering') buckets.catering.push(item)
        else buckets.other.push(item)
      })
      const sections = []
      if (buckets.gym.length) {
        sections.push({
          key: 'gym',
          title: '观野FIT',
          subtitle: '会籍 · 团课 · 商城 · 通行',
          items: buckets.gym,
        })
      }
      if (buckets.catering.length) {
        sections.push({
          key: 'catering',
          title: '观野BAR',
          subtitle: '点餐 · 取餐号 · 订单',
          items: buckets.catering,
        })
      }
      if (buckets.other.length) {
        sections.push({
          key: 'other',
          title: '其它门店',
          subtitle: '进入查看可用服务',
          items: buckets.other,
        })
      }
      const banners = (site && site.banner_image_urls) || []
      const slides = banners.length
        ? banners.map((u) => fileUrl(u))
        : site && site.cover_image_url
          ? [fileUrl(site.cover_image_url)]
          : []
      const facts = []
      if (site && site.service_phone) {
        facts.push({ key: '客服', value: site.service_phone, phone: site.service_phone })
      }
      if (site && site.business_hours) {
        facts.push({ key: '营业', value: site.business_hours })
      }
      if (site && site.address) {
        facts.push({ key: '地址', value: site.address, wide: true })
      }
      facts.push({ key: '会员', value: this.maskPhone(me.phone) })
      this.setData({
        loading: false,
        memberName: me.name || '',
        phoneMasked: this.maskPhone(me.phone),
        siteName: (site && site.name) || '观野SPACE',
        siteTagline: (site && site.tagline) || '选择门店，进入对应业态',
        slides,
        slide: 0,
        facts,
        sections,
        aboutText: (site && site.description) || '',
        gallery: ((site && site.gallery_image_urls) || []).map((u) => fileUrl(u)),
      })
      this.startSlide()
    } catch (e) {
      this.setData({ loading: false, err: (e && e.message) || '加载失败' })
    }
  },
  onHide() {
    this.stopSlide()
  },
  onUnload() {
    this.stopSlide()
  },
  maskPhone(phone) {
    if (!phone || phone.length < 7) return phone || ''
    return `${phone.slice(0, 3)}****${phone.slice(-4)}`
  },
  startSlide() {
    this.stopSlide()
    if ((this.data.slides || []).length < 2) return
    this._timer = setInterval(() => {
      const n = (this.data.slides || []).length
      if (n < 2) return
      this.setData({ slide: (this.data.slide + 1) % n })
    }, 5000)
  },
  stopSlide() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  },
  pickSlide(e) {
    this.setData({ slide: Number(e.currentTarget.dataset.index) })
  },
  callPhone(e) {
    const phone = e.currentTarget.dataset.phone
    if (!phone) return
    wx.makePhoneCall({ phoneNumber: String(phone) })
  },
  goMe() {
    wx.reLaunch({ url: '/pages/me/index' })
  },
  enter(e) {
    const id = Number(e.currentTarget.dataset.id)
    if (!id) return
    let item = null
    for (const section of this.data.sections || []) {
      item = (section.items || []).find((x) => x.id === id)
      if (item) break
    }
    if (!item) return
    const { enterMerchant } = require('../../utils/merchant')
    enterMerchant(item)
  },
  previewGallery(e) {
    const current = e.currentTarget.dataset.url
    wx.previewImage({ current, urls: this.data.gallery })
  },
})
