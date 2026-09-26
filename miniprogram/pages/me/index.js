/** 会员个人中心：订单、来源标识、头像与推广入口。人脸通行暂时关闭。 */
const SHOW_FACE_ACCESS = false

Page({
  data: {
    name: '',
    phoneMasked: '',
    avatar: '会',
    avatarUrl: '',
    showFaceAccess: SHOW_FACE_ACCESS,
    faceText: '未知',
    faceOk: false,
    sourceText: '综合运营平台',
    orders: [],
    orderMore: false,
    refundCount: 0,
    events: [],
    uploading: false,
    payingId: 0,
    icpBeian: '',
  },
  async onShow() {
    const { requireLogin, refreshMemberSession } = require('../../utils/session')
    if (!requireLogin()) return
    await refreshMemberSession()
    this.setData({ icpBeian: getApp().globalData.icpBeian || '' })
    await this.loadMe()
  },
  async loadMe() {
    const { request, fileUrl } = require('../../utils/api')
    try {
      const me = await request({ url: '/member/me' })
      const { memberOrderView } = require('../../utils/labels')
      let orders = []
      let refundCount = 0
      try {
        const rows = (await request({ url: '/member/orders?limit=6' })) || []
        orders = rows.map((item) => this.mapOrder(item, memberOrderView))
      } catch (err) {
        orders = []
      }
      try {
        const refunds = (await request({ url: '/member/refunds?limit=20' })) || []
        refundCount = refunds.length
      } catch (err) {
        refundCount = 0
      }
      let events = []
      if (SHOW_FACE_ACCESS) {
        try {
          const rows = await request({ url: '/member/access-events' })
          events = (rows || []).slice(0, 8).map((e) => ({
            ...e,
            timeText: this.fmtTime(e.created_at),
          }))
        } catch (err) {
          events = []
        }
      }
      this.setData({
        name: me.name || '—',
        phoneMasked: this.maskPhone(me.phone),
        avatar: (me.name || '会').slice(0, 1),
        avatarUrl: fileUrl(me.avatar_url),
        showFaceAccess: SHOW_FACE_ACCESS,
        faceText: me.face_status === 'enrolled' ? '已录入' : me.face_status === 'not_enrolled' ? '未录入' : me.face_status || '未知',
        faceOk: me.face_status === 'enrolled',
        sourceText: this.sourceText(me),
        orders: orders.slice(0, 5),
        orderMore: orders.length > 5,
        refundCount,
        events,
      })
    } catch (e) {
      wx.reLaunch({ url: '/pages/login/index' })
    }
  },
  maskPhone(phone) {
    if (!phone || phone.length < 7) return phone || ''
    return `${phone.slice(0, 3)}****${phone.slice(-4)}`
  },
  sourceText(me) {
    if (me.acquisition_source === 'merchant') {
      return me.first_merchant_name || (me.first_merchant_id ? `商户 #${me.first_merchant_id}` : '门店')
    }
    return '综合运营平台'
  },
  fmtTime(iso) {
    if (!iso) return '—'
    return String(iso).slice(0, 16).replace('T', ' ')
  },
  fmtDate(iso) {
    if (!iso) return '—'
    return String(iso).slice(0, 10)
  },
  moneyText(amount) {
    const value = Number(amount || 0)
    if (!Number.isFinite(value)) return '0'
    return Number.isInteger(value) ? String(value) : value.toFixed(2)
  },
  mapOrder(item, memberOrderView) {
    const view = memberOrderView(item)
    const refunded = Number(item.refunded_amount || 0)
    return {
      ...item,
      amountText: this.moneyText(item.amount),
      dateText: this.fmtDate(item.created_at),
      thumb: (item.title || '单').slice(0, 1),
      statusText: view.statusText,
      statusTone: view.statusTone,
      refundText: refunded > 0 ? `已退 ¥${this.moneyText(refunded)}` : '',
    }
  },
  pickAvatar() {
    if (this.data.uploading) return
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0]
        if (!file || !file.tempFilePath) return
        this.uploadAvatar(file.tempFilePath)
      },
    })
  },
  async uploadAvatar(filePath) {
    const { upload } = require('../../utils/api')
    this.setData({ uploading: true })
    try {
      await upload({ url: '/member/avatar', filePath })
      wx.showToast({ title: '头像已更新', icon: 'success' })
      await this.loadMe()
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '上传失败', icon: 'none' })
    } finally {
      this.setData({ uploading: false })
    }
  },
  async payOrder(e) {
    if (this.data.payingId) return
    const orderId = Number(e.currentTarget.dataset.id)
    if (!orderId) return
    const { payOrder } = require('../../utils/pay')
    this.setData({ payingId: orderId })
    try {
      await payOrder(orderId)
      wx.showToast({ title: '支付成功', icon: 'success' })
      await this.loadMe()
    } catch (err) {
      const message = (err && (err.errMsg || err.message)) || '支付失败'
      const cancelled = /cancel/i.test(message)
      wx.showToast({ title: cancelled ? '已取消支付' : message, icon: 'none' })
    } finally {
      this.setData({ payingId: 0 })
    }
  },
  goOrders(e) {
    const status = (e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.status) || ''
    const query = status ? `?status=${status}` : ''
    wx.navigateTo({ url: `/pages/orders/index${query}` })
  },
  goRefunds() {
    wx.navigateTo({ url: '/pages/refunds/index' })
  },
  openOrder(e) {
    const orderId = Number(e.currentTarget.dataset.id)
    if (!orderId) return
    wx.navigateTo({ url: `/pages/orders/detail?id=${orderId}` })
  },
  goPromotion() {
    wx.navigateTo({ url: '/pages/promotion/index' })
  },
  parseDiningCode(raw) {
    const text = String(raw || '')
    let merchantId = 0
    let table = ''
    const pathMid = text.match(/\/m\/(\d+)\/catering/i)
    if (pathMid) merchantId = Number(pathMid[1])
    const queryMid = text.match(/[?&]merchant_id=(\d+)/i)
    if (queryMid) merchantId = Number(queryMid[1])
    const queryTable = text.match(/[?&]table=([^&#\s]+)/i)
    if (queryTable) {
      try {
        table = decodeURIComponent(queryTable[1])
      } catch (err) {
        table = queryTable[1]
      }
    }
    return { merchantId, table }
  },
  diningMerchant(preferredId) {
    const { systemOf } = require('../../utils/merchant')
    const list = (getApp().globalData.memberMe && getApp().globalData.memberMe.merchants) || []
    if (preferredId) {
      const hit = list.find((item) => item.id === preferredId)
      if (hit) return hit
      return {
        id: preferredId,
        name: '观野BAR',
        primary_system: 'catering',
        subsystem_codes: ['catering'],
      }
    }
    return list.find((item) => systemOf(item) === 'catering') || null
  },
  goCatering() {
    wx.scanCode({
      onlyFromCamera: false,
      scanType: ['qrCode'],
      success: (res) => {
        const target = this.parseDiningCode(`${res.result || ''}\n${res.path || ''}`)
        const merchant = this.diningMerchant(target.merchantId)
        if (!merchant) {
          wx.showToast({ title: '请扫描观野BAR桌码', icon: 'none' })
          return
        }
        const { setMerchantContext } = require('../../utils/merchant')
        setMerchantContext(merchant)
        const query = [`merchant_id=${merchant.id}`]
        if (target.table) query.push(`table=${encodeURIComponent(target.table)}`)
        wx.reLaunch({ url: `/pages/catering/menu?${query.join('&')}` })
      },
      fail: (err) => {
        if (/cancel/i.test((err && err.errMsg) || '')) return
        wx.showToast({ title: '无法扫码', icon: 'none' })
      },
    })
  },
  logout() {
    const app = getApp()
    app.globalData.token = ''
    app.globalData.merchantId = null
    app.globalData.memberMe = null
    app.globalData.currentMerchant = null
    app.globalData.systemMode = 'gym'
    wx.removeStorageSync('member_token')
    wx.removeStorageSync('merchant_id')
    wx.removeStorageSync('system_mode')
    wx.reLaunch({ url: '/pages/login/index' })
  },
})
