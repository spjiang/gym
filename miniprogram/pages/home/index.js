/** 健身房首页：场馆介绍、教练与会籍展示。 */
Page({
  data: {
    name: '',
    err: '',
    msg: '',
    loading: true,
    merchant: null,
    coverUrl: '',
    gallery: [],
    coaches: [],
    memberships: [],
    pts: [],
    sessions: [],
    activities: [],
    agreeShow: false,
    agreeLoading: false,
    agreeError: '',
    agreeSummary: '',
    agreeTitle: '',
    agreeContent: '',
  },
  async onShow() {
    const { request, fileUrl } = require('../../utils/api')
    const app = getApp()
    this.setData({ loading: true, err: '' })
    try {
      const me = await request({ url: '/member/me' })
      this.setData({ name: me.name || '' })
      let mid = app.globalData.merchantId
      const merchants = me.merchants || []
      if (!mid && merchants.length) {
        mid = merchants[0].id
        app.globalData.merchantId = mid
        wx.setStorageSync('merchant_id', mid)
      }
      if (!mid) {
        this.setData({ loading: false, err: '请先选择门店' })
        return
      }
      const home = await request({ url: `/member/home?merchant_id=${mid}` })
      const merchant = home.merchant || {}
      this.setData({
        loading: false,
        merchant,
        coverUrl: fileUrl(merchant.cover_image_url),
        gallery: (merchant.gallery_image_urls || []).map((u) => fileUrl(u)),
        coaches: (home.coaches || []).map((c) => ({
          ...c,
          avatarUrl: fileUrl(c.avatar_url),
          initial: (c.display_name || '教').slice(0, 1),
          sub: c.title || c.specialties || '教练',
        })),
        memberships: (home.memberships || []).map((p) => ({
          ...p,
          priceText: this.money(p.effective_price || p.price),
          meta: p.duration_days ? `${p.duration_days} 天` : p.session_count ? `${p.session_count} 次` : '会籍',
        })),
        pts: (home.pt_packages || []).map((p) => ({
          ...p,
          priceText: this.money(p.effective_price || p.price),
          meta: `${p.session_count} 次 · ${p.valid_days} 天`,
        })),
        sessions: (home.sessions || []).map((s) => ({
          ...s,
          timeText: this.fmt(s.starts_at),
        })),
        activities: (home.activities || []).map((a) => ({
          ...a,
          coverUrl: fileUrl(a.cover_url),
          timeText: this.fmt(a.starts_at),
          remainText:
            a.capacity > 0 && a.remaining_capacity != null ? `余 ${a.remaining_capacity}` : '报名',
        })),
      })
    } catch (e) {
      if (!this.data.name) {
        wx.reLaunch({ url: '/pages/login/index' })
        return
      }
      this.setData({ loading: false, err: (e && e.message) || '加载失败' })
    }
  },
  money(raw) {
    if (raw == null || raw === '') return '—'
    const n = Number(raw)
    if (Number.isNaN(n)) return String(raw)
    return Number.isInteger(n) ? String(n) : n.toFixed(2)
  },
  fmt(iso) {
    if (!iso) return '—'
    return String(iso).slice(0, 16).replace('T', ' ')
  },
  go(e) {
    wx.navigateTo({ url: e.currentTarget.dataset.url })
  },
  goCoach(e) {
    const id = e.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: `/pages/coaches/detail?id=${id}` })
  },
  goSession(e) {
    const id = e.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: `/pages/classes/detail?id=${id}` })
  },
  goActivity(e) {
    const id = e.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: `/pages/activities/detail?id=${id}` })
  },
  preview(e) {
    const current = e.currentTarget.dataset.url
    wx.previewImage({ current, urls: this.data.gallery })
  },
  async buyCard(e) {
    const { id, name, price } = e.currentTarget.dataset
    this._agreeNext = () => this.buy('/member/orders/membership', id)
    const { openAgreement } = require('../../utils/agreement')
    const ok = await openAgreement(this, {
      merchantId: getApp().globalData.merchantId,
      scene: 'membership',
      summary: `${name || ''}  ¥${price || ''}`,
    })
    if (!ok) this._agreeNext = null
  },
  async buyPt(e) {
    const { id, name, price } = e.currentTarget.dataset
    this._agreeNext = () => this.buy('/member/orders/pt-package', id)
    const { openAgreement } = require('../../utils/agreement')
    const ok = await openAgreement(this, {
      merchantId: getApp().globalData.merchantId,
      scene: 'pt_package',
      summary: `${name || ''}  ¥${price || ''}`,
    })
    if (!ok) this._agreeNext = null
  },
  onAgreeClose() {
    this._agreeNext = null
    this.setData({ agreeShow: false })
  },
  async onAgreeConfirm() {
    const next = this._agreeNext
    this._agreeNext = null
    this.setData({ agreeShow: false })
    if (next) await next()
  },
  async buy(path, productId) {
    const { request } = require('../../utils/api')
    const { payOrder } = require('../../utils/pay')
    const app = getApp()
    wx.showLoading({ title: '支付中' })
    try {
      const order = await request({
        url: path,
        method: 'POST',
        data: { merchant_id: app.globalData.merchantId, product_id: productId },
      })
      await payOrder(order.id)
      wx.showToast({ title: '支付成功', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '支付失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },
})
