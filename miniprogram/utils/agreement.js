/** 拉取当前启用的购买协议。 */
async function fetchAgreement(merchantId, scene) {
  const { request } = require('./api')
  return request({
    url: `/member/agreements?merchant_id=${merchantId}&scene=${encodeURIComponent(scene)}`,
  })
}

async function openAgreement(page, { merchantId, scene, summary }) {
  page.setData({
    agreeShow: true,
    agreeLoading: true,
    agreeError: '',
    agreeSummary: summary || '',
    agreeTitle: '',
    agreeContent: '',
  })
  try {
    const row = await fetchAgreement(merchantId, scene)
    page.setData({
      agreeLoading: false,
      agreeTitle: row.title,
      agreeContent: row.content,
    })
    return true
  } catch (e) {
    page.setData({ agreeShow: false, agreeLoading: false })
    wx.showToast({
      title: (e && e.message) || '该门店尚未配置购买协议，请联系门店',
      icon: 'none',
    })
    return false
  }
}

module.exports = { fetchAgreement, openAgreement }
