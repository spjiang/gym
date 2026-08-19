Component({
  properties: {
    show: { type: Boolean, value: false },
    summary: { type: String, value: '' },
    title: { type: String, value: '' },
    content: { type: String, value: '' },
    error: { type: String, value: '' },
    loading: { type: Boolean, value: false },
    confirmLabel: { type: String, value: '确认支付' },
  },
  data: {
    checked: false,
    fullOpen: false,
    contentHtml: '',
  },
  observers: {
    show(v) {
      if (v) this.setData({ checked: false, fullOpen: false })
    },
    content(v) {
      const text = String(v || '')
      const html = /<[a-z][\s\S]*>/i.test(text) ? text : text.replace(/\n/g, '<br/>')
      this.setData({ contentHtml: html })
    },
  },
  methods: {
    onClose() {
      this.triggerEvent('close')
    },
    onToggle() {
      this.setData({ checked: !this.data.checked })
    },
    onOpenFull() {
      if (this.data.title) this.setData({ fullOpen: true })
    },
    onCloseFull() {
      this.setData({ fullOpen: false })
    },
    noop() {},
    onConfirm() {
      if (this.data.loading || this.data.error) return
      if (!this.data.checked) {
        wx.showToast({ title: '请先阅读并同意协议', icon: 'none' })
        return
      }
      this.triggerEvent('confirm')
    },
  },
})
