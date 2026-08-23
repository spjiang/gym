/** 页面跳转：模拟 Tab 用 reLaunch，子页用 navigateTo（与 H5 router 行为一致）。 */
const { GYM_TABS, CATERING_TABS } = require('./merchant')

const GYM_TAB_PAGES = new Set(GYM_TABS.map((t) => t.path))
const CATERING_TAB_PAGES = new Set(CATERING_TABS.map((t) => t.path))

function tabPagesForMode(mode) {
  return mode === 'catering' ? CATERING_TAB_PAGES : GYM_TAB_PAGES
}

function go(url) {
  const base = String(url || '').split('?')[0]
  const mode = getApp().globalData.systemMode || 'gym'
  const tabs = tabPagesForMode(mode)
  if (tabs.has(base)) {
    wx.reLaunch({ url: base })
    return
  }
  wx.navigateTo({ url })
}

function tabIndex(path, mode) {
  const list = mode === 'catering' ? CATERING_TABS : GYM_TABS
  const base = String(path || '').split('?')[0]
  const idx = list.findIndex((t) => t.path === base)
  return idx >= 0 ? idx : 0
}

module.exports = {
  go,
  tabIndex,
  GYM_TAB_PAGES,
  CATERING_TAB_PAGES,
  tabPagesForMode,
}
