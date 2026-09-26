Page({
  data: { title: '优惠卡券', claimable: [], mine: [], msg: '', err: '' },
  async onShow() {
    const { requireLogin, refreshMemberSession } = require('../../utils/session')
    const { goStores } = require('../../utils/merchant')
    if (!requireLogin()) return
    if (!getApp().globalData.merchantId) {
      goStores()
      return
    }
    await refreshMemberSession()
    await this.load()
  },
  async load() {
    const { request } = require('../../utils/api')
    const app = getApp()
    const mid = app.globalData.merchantId
    if (!mid) {
      this.setData({ err: '请先选择门店', claimable: [], mine: [] })
      return
    }
    try {
      const [claimable, mine] = await Promise.all([
        request({ url: `/member/coupons/claimable?merchant_id=${mid}` }),
        request({ url: `/member/coupons?merchant_id=${mid}` }),
      ])
      this.setData({
        claimable: (claimable || []).map((item) => this.present(item, item.name)),
        mine: (mine || []).map((item) => this.present(item, item.template_name || `券 #${item.id}`)),
        err: '',
      })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败' })
    }
  },
  money(raw) {
    if (raw == null || raw === '') return ''
    const n = Number(raw)
    if (Number.isNaN(n)) return String(raw)
    return Number.isInteger(n) ? String(n) : n.toFixed(2)
  },
  present(item, name) {
    const { couponStatusLabel, fmtDate } = require('../../utils/labels')
    const face = this.faceOf(item)
    const threshold = Number(item.threshold_amount)
    const scope = {
      membership: '仅办卡',
      retail: '仅零售',
      both: '办卡与零售',
      gym: '办卡与零售',
      dining: '酒吧消费',
    }[item.applicable_to]
    return {
      ...item,
      title: name,
      ...face,
      rule: threshold > 0 ? `满 ¥${this.money(item.threshold_amount)} 可用` : '无门槛',
      scope: scope || '',
      until: item.ends_at ? `至 ${fmtDate(item.ends_at)}` : '',
      statusText: item.status ? couponStatusLabel(item.status) : '',
      statusClass: item.status === 'unused' ? 'ok' : item.status === 'used' ? 'used' : 'off',
    }
  },
  faceOf(item) {
    if (item.discount_type === 'percent' && item.percent_off) {
      const zhe = (100 - Number(item.percent_off)) / 10
      return {
        num: Number.isInteger(zhe) ? String(zhe) : zhe.toFixed(1),
        unit: '折',
        kind: '折扣',
      }
    }
    const amount = this.money(item.fixed_amount)
    return { num: amount || '券', unit: amount ? '元' : '', kind: '满减' }
  },
  async claim(e) {
    const { request } = require('../../utils/api')
    const app = getApp()
    const id = e.currentTarget.dataset.id
    try {
      await request({
        url: '/member/coupons/claim',
        method: 'POST',
        data: { merchant_id: app.globalData.merchantId, template_id: id },
      })
      wx.showToast({ title: '领取成功', icon: 'success' })
      await this.load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '领取失败', icon: 'none' })
    }
  },
})
