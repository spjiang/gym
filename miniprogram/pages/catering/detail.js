Page({
  data: { order: null, err: '', busy: false },
  onLoad(options) {
    this._id = Number(options && options.id)
  },
  async onShow() {
    await this.load()
  },
  async load() {
    const { request } = require('../../utils/api')
    if (!this._id) {
      this.setData({ err: '订单不存在' })
      return
    }
    try {
      const order = await request({ url: `/member/catering/orders/${this._id}` })
      this.setData({ order, err: '' })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败' })
    }
  },
  async pay() {
    if (this.data.busy) return
    const { payOrder } = require('../../utils/pay')
    this.setData({ busy: true })
    try {
      await payOrder(this._id)
      wx.showToast({ title: '支付成功', icon: 'success' })
      await this.load()
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '支付失败', icon: 'none' })
    } finally {
      this.setData({ busy: false })
    }
  },
})
