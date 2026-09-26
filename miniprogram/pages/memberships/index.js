/** 会籍与课包列表，与 H5 MembershipsView 对齐。 */
const {
  membershipStatusLabel,
  membershipStatusClass,
  membershipTypeLabel,
  fmtDate,
} = require('../../utils/labels')

Page({
  data: {
    loading: true,
    err: '',
    memberships: [],
    packages: [],
  },
  daysLeft(iso) {
    if (!iso) return null
    const end = new Date(iso)
    if (Number.isNaN(end.getTime())) return null
    return Math.ceil((end.getTime() - Date.now()) / 86400000)
  },
  money(raw) {
    if (raw == null || raw === '') return ''
    const n = Number(raw)
    if (Number.isNaN(n)) return String(raw)
    return Number.isInteger(n) ? String(n) : n.toFixed(2)
  },
  specOf(item) {
    if (item.remaining_sessions != null) return { num: String(item.remaining_sessions), unit: '次' }
    const amount = this.money(item.balance)
    if (amount) return { num: amount, unit: '元' }
    const days = this.daysLeft(item.ends_at)
    if (days != null) return { num: String(Math.max(days, 0)), unit: '天' }
    return { num: '会籍', unit: '' }
  },
  mapMembership(m) {
    return {
      id: m.id,
      title: m.product_name || `会籍 #${m.id}`,
      ...this.specOf(m),
      typeText: membershipTypeLabel(m.product_type),
      until: fmtDate(m.ends_at),
      statusText: membershipStatusLabel(m.status),
      statusClass: membershipStatusClass(m.status),
      dim: m.status !== 'active',
    }
  },
  mapPackage(p) {
    return {
      id: p.id,
      title: p.product_name || `课包 #${p.id}`,
      num: String(p.remaining_sessions),
      unit: '次',
      typeText: '私教课包',
      until: fmtDate(p.ends_at),
      statusText: membershipStatusLabel(p.status),
      statusClass: membershipStatusClass(p.status),
      dim: p.status !== 'active',
    }
  },
  async onShow() {
    const { requireLogin, refreshMemberSession } = require('../../utils/session')
    const { goStores } = require('../../utils/merchant')
    if (!requireLogin()) return
    if (!getApp().globalData.merchantId) {
      goStores()
      return
    }
    await refreshMemberSession()
    const { request } = require('../../utils/api')
    const mid = getApp().globalData.merchantId
    this.setData({ loading: true, err: '' })
    try {
      const [memberships, packages] = await Promise.all([
        request({ url: `/member/memberships?merchant_id=${mid}` }),
        request({ url: `/member/pt-packages?merchant_id=${mid}` }),
      ])
      this.setData({
        loading: false,
        memberships: (memberships || []).map((m) => this.mapMembership(m)),
        packages: (packages || []).map((p) => this.mapPackage(p)),
      })
    } catch (e) {
      this.setData({
        loading: false,
        err: (e && e.message) || '加载失败',
      })
    }
  },
  goMembership(e) {
    const id = e.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: `/pages/memberships/detail?id=${id}` })
  },
  goPackage(e) {
    const id = e.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: `/pages/pt-packages/detail?id=${id}` })
  },
})
