App({
  globalData: {
    // 生产联调。本机改回：http://127.0.0.1:18000/api/v1
    apiBase: 'https://api.guanyespace.com/api/v1',
    token: '',
    merchantId: null,
    systemMode: 'gym',
    currentMerchant: null,
    memberMe: null,
    referralCode: '',
  },
  onLaunch(options) {
    const token = wx.getStorageSync('member_token')
    if (token) this.globalData.token = token
    const systemMode = wx.getStorageSync('system_mode')
    if (systemMode) this.globalData.systemMode = systemMode
    const code = this.resolveReferralCode(options && options.query)
    if (code) {
      this.globalData.referralCode = code
      wx.setStorageSync('referral_code', code)
    } else {
      this.globalData.referralCode = wx.getStorageSync('referral_code') || ''
    }
    const query = (options && options.query) || {}
    const storedMerchantId = wx.getStorageSync('merchant_id')
    const merchantId = query.merchant_id ? Number(query.merchant_id) : storedMerchantId
    if (merchantId) {
      this.globalData.merchantId = Number(merchantId)
      wx.setStorageSync('merchant_id', Number(merchantId))
    }
  },
  /** 扫码进入支持 promoter 参数或小程序码 scene */
  resolveReferralCode(query) {
    if (!query) return ''
    const raw = query.promoter || query.referral_code || query.scene || ''
    if (!raw) return ''
    let value = String(raw)
    try {
      value = decodeURIComponent(value)
    } catch (e) {
      // scene 未编码时保持原值
    }
    const matched = /(?:^|[?&])(?:promoter|referral_code)=([A-Za-z0-9]+)/.exec(value)
    const code = matched ? matched[1] : value
    return /^[A-Za-z0-9]{4,32}$/.test(code) ? code.toUpperCase() : ''
  },
})
