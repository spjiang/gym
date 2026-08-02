/** 统一请求封装 */
function request({ url, method = 'GET', data }) {
  const app = getApp()
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.apiBase}${url}`,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        Authorization: app.globalData.token ? `Bearer ${app.globalData.token}` : '',
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data)
        else reject(res.data || { message: '请求失败' })
      },
      fail: reject,
    })
  })
}

module.exports = { request }
