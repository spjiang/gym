/** 活动列表：我的报名在上，已发布且未结束的活动可报名。 */
Page({
  data: {
    mine: [],
    activities: [],
    err: '',
    agreeShow: false,
    agreeLoading: false,
    agreeError: '',
    agreeSummary: '',
    agreeTitle: '',
    agreeContent: '',
    agreeConfirmLabel: '立即报名',
  },
  async onShow() {
    await this.load()
  },
  async load() {
    const { request, fileUrl } = require('../../utils/api')
    const app = getApp()
    const mid = app.globalData.merchantId
    if (!mid) {
      this.setData({ err: '请先选择门店', mine: [], activities: [] })
      return
    }
    try {
      const [activities, mine] = await Promise.all([
        request({ url: `/member/activities?merchant_id=${mid}` }),
        request({ url: `/member/activity-registrations?merchant_id=${mid}` }),
      ])
      this.setData({
        err: '',
        activities: (activities || []).map((a) => ({
          ...a,
          coverUrl: fileUrl(a.cover_url),
          timeText: this.fmt(a.starts_at),
          priceText: this.money(a.price),
          seatsText:
            a.capacity > 0 && a.remaining_capacity != null
              ? `剩余 ${a.remaining_capacity}/${a.capacity}`
              : '不限名额',
        })),
        mine: (mine || []).map((r) => ({
          ...r,
          timeText: this.fmt(r.activity_starts_at),
          statusText: this.statusText(r.status),
        })),
      })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败' })
    }
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
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/activities/detail?id=${id}` })
  },
  async join(e) {
    const { openAgreement } = require('../../utils/agreement')
    const id = Number(e.currentTarget.dataset.id)
    const name = e.currentTarget.dataset.name || ''
    const priceText = e.currentTarget.dataset.price || ''
    this._agreeNext = () => this.doJoin(id)
    this.setData({ agreeConfirmLabel: String(priceText).indexOf('¥') >= 0 ? '报名并支付' : '立即报名' })
    const ok = await openAgreement(this, {
      merchantId: getApp().globalData.merchantId,
      scene: 'activity',
      summary: `${name}  ${priceText}`,
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
  async doJoin(id) {
    const { request } = require('../../utils/api')
    const { payOrder } = require('../../utils/pay')
    const mid = getApp().globalData.merchantId
    wx.showLoading({ title: '处理中' })
    try {
      const data = await request({
        url: '/member/activity-registrations',
        method: 'POST',
        data: { merchant_id: mid, activity_id: id },
      })
      if (data.order) {
        await payOrder(data.order.id)
      }
      wx.showToast({ title: '报名成功', icon: 'success' })
      await this.load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '报名失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },
  async payPending(e) {
    const { payOrder } = require('../../utils/pay')
    const orderId = Number(e.currentTarget.dataset.id)
    wx.showLoading({ title: '支付中' })
    try {
      await payOrder(orderId)
      wx.showToast({ title: '报名成功', icon: 'success' })
      await this.load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '支付失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },
  async cancel(e) {
    const { request } = require('../../utils/api')
    const id = Number(e.currentTarget.dataset.id)
    try {
      await request({ url: `/member/activity-registrations/${id}/cancel`, method: 'POST' })
      wx.showToast({ title: '已取消', icon: 'success' })
      await this.load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '取消失败', icon: 'none' })
    }
  },
})
