/** 平台版权主体，页脚与协议对外展示用全称。 */
export const COPYRIGHT_OWNER = '北京晨曦坤泽科技有限公司'

export function copyrightLine(year = new Date().getFullYear()) {
  return `© ${year} ${COPYRIGHT_OWNER}`
}

export function copyrightNotice() {
  return `本服务由${COPYRIGHT_OWNER}运营。观野SPACE 及相关软件、页面与内容之版权归${COPYRIGHT_OWNER}所有。`
}
