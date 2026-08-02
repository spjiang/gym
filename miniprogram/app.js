App({
  globalData: {
    // 开发时改为本机或网关地址，如 http://127.0.0.1:18000/api/v1
    apiBase: 'http://127.0.0.1:18000/api/v1',
    token: '',
    merchantId: null,
  },
  onLaunch() {
    const token = wx.getStorageSync('member_token')
    if (token) this.globalData.token = token
  },
})
