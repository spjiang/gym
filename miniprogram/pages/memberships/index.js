/** 会籍与课包列表，与 H5 MembershipsView 对齐。 */
const {
  membershipStatusLabel,
  membershipStatusClass,
  fmtDate,
} = require('../../utils/labels')

Page({
  data: {
    loading: true,
    err: '',
    memberships: [],
    packages: [],
  },
  mapMembership(m) {
    return {
      id: m.id,
      title: m.product_name || `会籍 #${m.id}`,
      meta: `到期 ${fmtDate(m.ends_at)} · 剩余次 ${m.remaining_sessions != null ? m.remaining_sessions : '—'}`,
      status: m.status,
      statusText: membershipStatusLabel(m.status),
      statusClass: membershipStatusClass(m.status),
    }
  },
  mapPackage(p) {
    return {
      id: p.id,
      title: p.product_name || `课包 #${p.id}`,
      meta: `剩余课时 ${p.remaining_sessions} · 到期 ${fmtDate(p.ends_at)}`,
      status: p.status,
      statusText: membershipStatusLabel(p.status),
      statusClass: membershipStatusClass(p.status),
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
