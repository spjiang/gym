/** 统一请求封装 */
function apiOrigin() {
  const app = getApp()
  return String(app.globalData.apiBase || '').replace(/\/api\/v1\/?$/, '')
}

function fileUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//.test(path)) return path
  const origin = apiOrigin()
  return path.startsWith('/') ? `${origin}${path}` : `${origin}/${path}`
}

function request({ url, method = 'GET', data }) {
  const app = getApp()
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.apiBase}${url}`,
      method,
      data,
      timeout: 20000,
      // 真机 Cronet 对 ALB 的 HTTP/2、QUIC 常被 RST（errcode -101）；浏览器不受影响
      enableHttp2: false,
      enableQuic: false,
      header: {
        'Content-Type': 'application/json',
        'X-Client-Channel': 'member_mp',
        Authorization: app.globalData.token ? `Bearer ${app.globalData.token}` : '',
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data)
        else reject({ ...(res.data || {}), statusCode: res.statusCode, message: (res.data && res.data.message) || '请求失败' })
      },
      fail(err) {
        const msg = (err && (err.errMsg || err.message)) || '网络失败'
        reject({ ...(err || {}), message: msg })
      },
    })
  })
}

function upload({ url, filePath, name = 'file' }) {
  const app = getApp()
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${app.globalData.apiBase}${url}`,
      filePath,
      name,
      timeout: 30000,
      enableHttp2: false,
      enableQuic: false,
      header: {
        'X-Client-Channel': 'member_mp',
        Authorization: app.globalData.token ? `Bearer ${app.globalData.token}` : '',
      },
      success(res) {
        let data = res.data
        try {
          data = JSON.parse(res.data)
        } catch (e) {
          // 保持原文
        }
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(data)
        else reject(data || { message: '上传失败' })
      },
      fail: reject,
    })
  })
}

module.exports = { request, upload, fileUrl }
