/** 点餐结算：支付成功后再清空购物车。 */
Page({
  data: {
    lines: [],
    note: '',
    tableNo: '',
    tableLocked: false,
    payable: '0.00',
    err: '',
    busy: false,
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
    try {
      if (this._tableCode && !cart.tableLockedOf(mid)) {
        try {
          const table = await request({
            url: `/member/catering/table?merchant_id=${mid}&code=${encodeURIComponent(this._tableCode)}`,
          })
          cart.lockTable(mid, table.name)
        } catch (e) {
          /* 手填桌号 */
        }
      }
      const items = (await request({ url: `/member/catering/menu?merchant_id=${mid}` })) || []
      const lines = cart.linesOf(mid, items)
      if (!lines.length) {
        wx.navigateBack()
        return
      }
      const subtotal = lines.reduce((sum, i) => sum + Number(i.price) * i.quantity, 0)
      this.setData({
        lines,
        note: cart.noteOf(mid),
        tableNo: cart.tableNoOf(mid),
        tableLocked: cart.tableLockedOf(mid),
        payable: subtotal.toFixed(2),
      })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败' })
    }
  },
  onNote(e) {
    const cart = require('../../utils/cateringCart')
    cart.setNote(getApp().globalData.merchantId, e.detail.value)
    this.setData({ note: e.detail.value })
  },
  onTable(e) {
    const cart = require('../../utils/cateringCart')
    cart.setTableNo(getApp().globalData.merchantId, e.detail.value)
    this.setData({ tableNo: e.detail.value, tableLocked: false })
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
