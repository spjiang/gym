/** 点餐结算：询价、选券、选桌；支付成功后再清空购物车。 */
Page({
  data: {
    lines: [],
    note: '',
    tableNo: '',
    tableLocked: false,
    tables: [],
    tableNames: ['散客 / 未选桌'],
    tableIndex: 0,
    quote: null,
    payable: '0.00',
    promoOff: '0.00',
    couponOff: '0.00',
    coupons: [],
    couponId: null,
    hasPromo: false,
    hasCouponOff: false,
    err: '',
    busy: false,
    agreed: false,
    agreeTitle: '',
    agreeContent: '',
    agreeHtml: '',
    agreeErr: '',
    agreeFull: false,
  },
  onLoad(options) {
    this._tableCode = (options && options.table) || ''
  },
  async onShow() {
    const { request } = require('../../utils/api')
    const cart = require('../../utils/cateringCart')
    const app = getApp()
    const mid = app.globalData.merchantId
    if (!mid) {
      wx.showToast({ title: '请先选店', icon: 'none' })
      return
    }
    if (!app.globalData.token) {
      this.goLogin()
      return
    }
    try {
      if (this._tableCode && !cart.tableLockedOf(mid)) {
        try {
          const table = await request({
            url: `/member/catering/table?merchant_id=${mid}&code=${encodeURIComponent(this._tableCode)}`,
          })
          cart.lockTable(mid, table.name)
        } catch (e) {
          /* 手选桌号 */
        }
      }
      const [items, tables] = await Promise.all([
        request({ url: `/member/catering/menu?merchant_id=${mid}` }),
        request({ url: `/member/catering/tables?merchant_id=${mid}` }),
      ])
      const lines = cart.linesOf(mid, items || [])
      if (!lines.length) {
        wx.navigateBack()
        return
      }
      const names = ['散客 / 未选桌'].concat((tables || []).map((t) => t.name))
      const current = cart.tableNoOf(mid)
      const idx = current ? Math.max(names.indexOf(current), 0) : 0
      this.setData({
        lines,
        note: cart.noteOf(mid),
        tableNo: current,
        tableLocked: cart.tableLockedOf(mid),
        tables: tables || [],
        tableNames: names,
        tableIndex: idx,
        couponId: cart.couponOf(mid),
      })
      await this.loadAgreement(mid)
      await this.refreshQuote()
    } catch (e) {
      if (this.needLogin(e)) {
        this.goLogin()
        return
      }
      this.setData({ err: (e && e.message) || '加载失败' })
    }
  },
  needLogin(e) {
    const status = e && (e.status_code || e.statusCode)
    return status === 401
  },
  goLogin() {
    const app = getApp()
    const mid = app.globalData.merchantId || ''
    const table = this._tableCode || ''
    const redirect = encodeURIComponent(
      `/pages/catering/checkout${table ? `?table=${encodeURIComponent(table)}` : ''}`,
    )
    wx.redirectTo({
      url: `/pages/login/index?merchant_id=${mid}&table=${encodeURIComponent(table)}&redirect=${redirect}`,
    })
  },
  async loadAgreement(mid) {
    const { fetchAgreement } = require('../../utils/agreement')
    try {
      const row = await fetchAgreement(mid, 'dining')
      const text = row.content || ''
      const html = /<[a-z][\s\S]*>/i.test(text) ? text : text.replace(/\n/g, '<br/>')
      this.setData({
        agreeTitle: row.title,
        agreeContent: text,
        agreeHtml: html,
        agreeErr: '',
      })
    } catch (e) {
      this.setData({
        agreed: false,
        agreeTitle: '',
        agreeContent: '',
        agreeHtml: '',
        agreeErr: (e && e.message) || '该门店尚未配置购买协议，请联系门店',
      })
    }
  },
  toggleAgree() {
    if (!this.data.agreeTitle) return
    this.setData({ agreed: !this.data.agreed })
  },
  openAgreeFull() {
    if (this.data.agreeTitle) this.setData({ agreeFull: true })
  },
  closeAgreeFull() {
    this.setData({ agreeFull: false })
  },
  couponFace(c) {
    return c.discount_type === 'fixed' ? `减¥${c.fixed_amount}` : `${c.percent_off}%折`
  },
  async refreshQuote() {
    const { request } = require('../../utils/api')
    const cart = require('../../utils/cateringCart')
    const app = getApp()
    const mid = app.globalData.merchantId
    if (!this.data.lines.length) {
      this.setData({ quote: null, payable: '0.00' })
      return
    }
    try {
      const quote = await request({
        url: '/member/catering/quote',
        method: 'POST',
        data: {
          merchant_id: mid,
          items: this.data.lines.map((i) => ({ menu_item_id: i.id, quantity: i.quantity })),
          member_coupon_id: this.data.couponId || null,
        },
      })
      const selected = (quote.coupons || []).find((c) => c.id === this.data.couponId)
      if (this.data.couponId && selected && !selected.eligible) {
        cart.setCoupon(mid, null)
        this.setData({ couponId: null })
        return this.refreshQuote()
      }
      this.setData({
        quote,
        payable: Number(quote.payable).toFixed(2),
        promoOff: Number(quote.promotion_discount_amount || 0).toFixed(2),
        couponOff: Number(quote.coupon_discount_amount || 0).toFixed(2),
        hasPromo: Number(quote.promotion_discount_amount || 0) > 0,
        hasCouponOff: Number(quote.coupon_discount_amount || 0) > 0,
        coupons: (quote.coupons || []).map((c) => ({ ...c, face: this.couponFace(c) })),
      })
    } catch (e) {
      const subtotal = this.data.lines.reduce((sum, i) => sum + Number(i.price) * i.quantity, 0)
      this.setData({ payable: subtotal.toFixed(2) })
    }
  },
  pickCoupon(e) {
    const cart = require('../../utils/cateringCart')
    const raw = e.currentTarget.dataset.id
    if (raw === '' || raw == null) {
      cart.setCoupon(getApp().globalData.merchantId, null)
      this.setData({ couponId: null })
      this.refreshQuote()
      return
    }
    const coupon = (this.data.coupons || []).find((c) => c.id === Number(raw))
    if (coupon && !coupon.eligible) return
    const couponId = Number(raw)
    cart.setCoupon(getApp().globalData.merchantId, couponId)
    this.setData({ couponId })
    this.refreshQuote()
  },
  onNote(e) {
    const cart = require('../../utils/cateringCart')
    cart.setNote(getApp().globalData.merchantId, e.detail.value)
    this.setData({ note: e.detail.value })
  },
  onTablePick(e) {
    const cart = require('../../utils/cateringCart')
    const index = Number(e.detail.value)
    const name = index <= 0 ? '' : this.data.tableNames[index]
    cart.setTableNo(getApp().globalData.merchantId, name)
    this.setData({ tableNo: name, tableIndex: index, tableLocked: false })
  },
  add(e) {
    const cart = require('../../utils/cateringCart')
    cart.add(getApp().globalData.merchantId, e.currentTarget.dataset.id)
    this.onShow()
  },
  sub(e) {
    const cart = require('../../utils/cateringCart')
    cart.sub(getApp().globalData.merchantId, e.currentTarget.dataset.id)
    this.onShow()
  },
  async submit() {
    if (this.data.busy || !this.data.lines.length) return
    if (!this.data.agreeTitle || !this.data.agreed) {
      this.setData({ err: this.data.agreeErr || '请先阅读并同意点餐协议' })
      return
    }
    const { request } = require('../../utils/api')
    const { payOrder } = require('../../utils/pay')
    const cart = require('../../utils/cateringCart')
    const app = getApp()
    const mid = app.globalData.merchantId
    this.setData({ busy: true, err: '' })
    try {
      const order = await request({
        url: '/member/catering/checkout',
        method: 'POST',
        data: {
          merchant_id: mid,
          items: this.data.lines.map((i) => ({ menu_item_id: i.id, quantity: i.quantity })),
          note: this.data.note || null,
          table_no: this.data.tableNo || null,
          member_coupon_id: this.data.couponId || null,
        },
      })
      let paid = false
      try {
        await payOrder(order.id)
        paid = true
      } catch (e) {
        this.setData({ err: ((e && e.message) || '支付未完成') + '，可在订单中继续支付' })
      }
      if (paid) cart.clear(mid)
      wx.redirectTo({ url: `/pages/catering/detail?id=${order.id}` })
    } catch (e) {
      this.setData({ err: (e && e.message) || '下单失败', busy: false })
    }
  },
})
