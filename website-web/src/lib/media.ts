/** 公开图改走官网同域 /media/，不依赖 file. 证书。 */
export function mediaSrc(url: string | null | undefined): string {
  if (!url) return ''
  const match = url.match(/\/public\/([^/?#]+)/)
  return match ? `/media/${match[1]}` : url
}
