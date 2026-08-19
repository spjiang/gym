Page({
  data: { order: null, statusText: '', err: '', busy: false },
  onLoad(options) {
    this._id = Number(options && options.id)
  },
  onShow() {
    this.load()
    this.startPoll()
  },
  onHide() {
    this.stopPoll()
  },
  onUnload() {
    this.stopPoll()
  },
  startPoll() {
    this.stopPoll()
    this._timer = setInterval(() => {
      const order = this.data.order
      if (!order) return
      const kitchen = order.dining_status || 'preparing'
      if (order.status === 'pending' || (order.status === 'paid' && (kitchen === 'preparing' || kitchen === 'ready'))) {
        this.load()
      }
    }, 8000)
  },
  stopPoll() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  },
  async load() {
    const { request } = require('../../utils/api')
    const { diningOrderLabel } = require('../../utils/labels')
    if (!this._id) {
      this.setData({ err: '订单不存在' })
      return
    }
    try {
      const order = await request({ url: `/member/catering/orders/${this._id}` })
      this.setData({ order, statusText: diningOrderLabel(order), err: '' })
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
  async cancel() {
    if (this.data.busy || !this.data.order) return
    const { request } = require('../../utils/api')
    this.setData({ busy: true, err: '' })
    try {
      const order = await request({
        url: `/member/catering/orders/${this._id}/cancel`,
        method: 'POST',
      })
      const { diningOrderLabel } = require('../../utils/labels')
      this.setData({ order, statusText: diningOrderLabel(order) })
      wx.showToast({ title: '已取消', icon: 'success' })
    } catch (e) {
      this.setData({ err: (e && e.message) || '取消失败' })
    } finally {
      this.setData({ busy: false })
    }
  },
})
