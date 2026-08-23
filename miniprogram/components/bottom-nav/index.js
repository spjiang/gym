const { tabsForMode } = require('../../utils/merchant')

Component({
  properties: {
    active: { type: String, value: '' },
  },
  data: {
    tabs: [],
  },
  lifetimes: {
    attached() {
      this.refreshTabs()
    },
  },
  pageLifetimes: {
    show() {
      this.refreshTabs()
    },
  },
  methods: {
    refreshTabs() {
      const mode = getApp().globalData.systemMode || 'gym'
      this.setData({ tabs: tabsForMode(mode) })
    },
    onTap(e) {
      const path = e.currentTarget.dataset.path
      if (!path || path === this.properties.active) return
      wx.reLaunch({ url: path })
    },
  },
})
