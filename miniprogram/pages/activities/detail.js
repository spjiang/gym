/** 活动详情：免费直接确认，收费走统一支付。 */
Page({
  data: {
    item: null,
    err: '',
    busy: false,
    timeText: '',
    endText: '',
    regEndText: '',
    seatsText: '',
    priceText: '',
    statusText: '',
    payLabel: '立即报名',
  },
  onLoad(query) {
    this.activityId = Number(query.id)
    this.load()
  },
  fmt(iso) {
    if (!iso) return '—'
    return String(iso).slice(0, 16).replace('T', ' ')
  },
  money(raw) {
    const n = Number(raw)
    if (!raw || Number.isNaN(n) || n <= 0) return '免费'
    return `¥ ${Number.isInteger(n) ? String(n) : n.toFixed(2)}`
  },
  statusText(status) {
    return {
      pending: '待支付',
      confirmed: '已报名',
      cancelled: '已取消',
      attended: '已参加',
      no_show: '未到场',
    }[status] || status
  },
  applyItem(item) {
    const n = Number(item.price)
    this.setData({
      err: '',
      item,
      timeText: this.fmt(item.starts_at),
      endText: this.fmt(item.ends_at),
      regEndText: this.fmt(item.register_ends_at),
      seatsText:
        item.capacity > 0 && item.remaining_capacity != null
          ? `剩余 ${item.remaining_capacity} / ${item.capacity}`
          : '不限名额',
      priceText: this.money(item.price),
      statusText: this.statusText(item.my_registration_status),
      payLabel: n > 0 ? '报名并支付' : '立即报名',
    })
  },
  async load() {
    const { request, fileUrl } = require('../../utils/api')
    try {
      const item = await request({ url: `/member/activities/${this.activityId}` })
      this.applyItem({ ...item, cover_url: fileUrl(item.cover_url) })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败', item: null })
    }
  },
  async join() {
    if (this.data.busy || !this.data.item) return
    const { request } = require('../../utils/api')
    const { payOrder } = require('../../utils/pay')
    const mid = getApp().globalData.merchantId
    this.setData({ busy: true })
    wx.showLoading({ title: '处理中' })
    try {
      const data = await request({
        url: '/member/activity-registrations',
        method: 'POST',
        data: { merchant_id: mid, activity_id: this.data.item.id },
      })
      if (data.order) {
        await payOrder(data.order.id)
      }
      wx.showToast({ title: '报名成功', icon: 'success' })
      await this.load()
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '报名失败', icon: 'none' })
    } finally {
      wx.hideLoading()
      this.setData({ busy: false })
    }
  },
  async payPending() {
    if (this.data.busy || !this.data.item || !this.data.item.my_order_id) return
    const { payOrder } = require('../../utils/pay')
    this.setData({ busy: true })
    wx.showLoading({ title: '支付中' })
    try {
      await payOrder(this.data.item.my_order_id)
      wx.showToast({ title: '报名成功', icon: 'success' })
      await this.load()
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '支付失败', icon: 'none' })
    } finally {
      wx.hideLoading()
      this.setData({ busy: false })
    }
  },
  async cancel() {
    if (this.data.busy || !this.data.item || !this.data.item.my_registration_id) return
    const { request } = require('../../utils/api')
    this.setData({ busy: true })
    try {
      await request({
        url: `/member/activity-registrations/${this.data.item.my_registration_id}/cancel`,
        method: 'POST',
      })
      wx.showToast({ title: '已取消', icon: 'success' })
      await this.load()
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '取消失败', icon: 'none' })
    } finally {
      this.setData({ busy: false })
    }
  },
})
