/** 会员端教练公开资料。 */
Page({
  data: {
    item: null,
    err: '',
    avatarUrl: '',
    intro: [],
    initial: '教',
    genderText: '—',
    yearsText: '—',
    rateText: '—',
  },
  onLoad(query) {
    this.coachId = Number(query.id)
    this.load()
  },
  genderTextOf(code) {
    return { male: '男', female: '女', other: '其他' }[code] || code || '—'
  },
  async load() {
    const { request, fileUrl } = require('../../utils/api')
    try {
      const item = await request({ url: `/member/coaches/${this.coachId}` })
      this.setData({
        err: '',
        item,
        avatarUrl: fileUrl(item.avatar_url),
        intro: (item.intro_image_urls || []).map((u) => fileUrl(u)),
        initial: (item.display_name || '教').slice(0, 1),
        genderText: this.genderTextOf(item.gender),
        yearsText: item.years_experience != null ? `${item.years_experience} 年` : '—',
        rateText: item.hourly_rate ? `¥${item.hourly_rate}` : '—',
      })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败', item: null })
    }
  },
})
