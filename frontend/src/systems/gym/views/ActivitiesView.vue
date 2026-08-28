<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type UploadRequestOptions, type UploadUserFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import http from '../../../core/api/http'
import { previewUploadFile } from '../../../core/imagePreview'
import { activityStatusLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Activity = {
  id: number
  merchant_id: number
  name: string
  category: string | null
  location: string | null
  cover_url: string | null
  description: string | null
  starts_at: string
  ends_at: string
  register_ends_at: string | null
  capacity: number
  price: string
  member_price: string | null
  requires_payment: boolean
  status: string
  registered_count: number
  attended_count: number
  remaining_capacity: number | null
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const rows = ref<Activity[]>([])
const loading = ref(false)
const submitting = ref(false)
const uploading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dialog = ref(false)
const editing = ref<Activity | null>(null)
const formRef = ref<FormInstance>()
const coverList = ref<UploadUserFile[]>([])

const posterVisible = ref(false)
const posterLoading = ref(false)
const posterRow = ref<Activity | null>(null)
const posterUrl = ref('')
const posterLink = ref('')

const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})

const query = reactive({
  q: '',
  status: '' as string,
  category: '',
  range: undefined as [string, string] | undefined,
})

const form = reactive({
  name: '',
  category: '',
  location: '',
  cover_url: '',
  description: '',
  starts_at: '',
  ends_at: '',
  register_ends_at: '',
  capacity: 0,
  price: '0',
  member_price: '' as string,
})

const rules: FormRules = {
  name: [{ required: true, message: '请填写活动名称', trigger: 'blur' }],
  starts_at: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  ends_at: [{ required: true, message: '请选择结束时间', trigger: 'change' }],
}

const dialogTitle = computed(() => (editing.value ? `编辑活动 #${editing.value.id}` : '新建活动'))

function fmtTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function statusTagType(status: string) {
  if (status === 'published') return 'success'
  if (status === 'cancelled') return 'danger'
  if (status === 'closed') return 'warning'
  return 'info'
}

function capacityText(row: Activity) {
  if (!row.capacity) return `${row.registered_count} 人（不限名额）`
  return `${row.registered_count} / ${row.capacity}`
}

function priceText(row: Pick<Activity, 'price' | 'member_price' | 'requires_payment'>) {
  if (!row.requires_payment && Number(row.price) <= 0) return '免费'
  const sell = row.member_price ?? row.price
  return `¥${sell}`
}

function merchantName(id: number) {
  return merchants.value.find((m) => m.id === id)?.name || '观野FIT'
}

function syncCoverList() {
  coverList.value = form.cover_url ? [{ name: '海报', url: form.cover_url, uid: 1 }] : []
}

async function uploadCover(opt: UploadRequestOptions) {
  const fd = new FormData()
  fd.append('file', opt.file as File)
  uploading.value = true
  try {
    const { data } = await http.post<{ url: string }>('/uploads', fd, { timeout: 30000 })
    form.cover_url = data.url
    syncCoverList()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '海报上传失败')
  } finally {
    uploading.value = false
  }
}

function removeCover() {
  form.cover_url = ''
  syncCoverList()
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('图片加载失败'))
    img.src = src
  })
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const chars = [...text]
  const lines: string[] = []
  let current = ''
  for (const ch of chars) {
    const next = current + ch
    if (ctx.measureText(next).width > maxWidth && current) {
      lines.push(current)
      current = ch
    } else {
      current = next
    }
  }
  if (current) lines.push(current)
  return lines.slice(0, 2)
}

async function composePoster(row: Activity, link: string): Promise<string> {
  const W = 750
  const H = 1334
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('无法生成海报')

  ctx.fillStyle = '#14181c'
  ctx.fillRect(0, 0, W, H)

  const coverH = 720
  if (row.cover_url) {
    try {
      const cover = await loadImage(row.cover_url)
      const scale = Math.max(W / cover.width, coverH / cover.height)
      const dw = cover.width * scale
      const dh = cover.height * scale
      ctx.drawImage(cover, (W - dw) / 2, (coverH - dh) / 2, dw, dh)
    } catch {
      ctx.fillStyle = '#3a2a1c'
      ctx.fillRect(0, 0, W, coverH)
    }
  } else {
    const g = ctx.createLinearGradient(0, 0, W, coverH)
    g.addColorStop(0, '#3a2a1c')
    g.addColorStop(1, '#14181c')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, W, coverH)
    ctx.fillStyle = 'rgba(242,230,210,0.12)'
    ctx.font = '800 140px Montserrat, Arial, sans-serif'
    ctx.fillText('FIT', 40, 220)
  }

  const wash = ctx.createLinearGradient(0, coverH - 200, 0, coverH)
  wash.addColorStop(0, 'rgba(20,24,28,0)')
  wash.addColorStop(1, '#14181c')
  ctx.fillStyle = wash
  ctx.fillRect(0, coverH - 200, W, 200)

  ctx.fillStyle = '#f36b21'
  ctx.fillRect(40, 40, 96, 8)
  ctx.fillStyle = '#14b8d4'
  ctx.fillRect(136, 42, 48, 4)

  ctx.fillStyle = '#f36b21'
  ctx.font = '700 26px sans-serif'
  ctx.fillText(row.category || '活动报名', 40, coverH + 20)

  ctx.fillStyle = '#f2e6d2'
  ctx.font = '700 48px sans-serif'
  const names = wrapText(ctx, row.name, W - 80)
  names.forEach((line, i) => ctx.fillText(line, 40, coverH + 84 + i * 58))

  ctx.fillStyle = 'rgba(242,230,210,0.78)'
  ctx.font = '400 28px sans-serif'
  const metaY = coverH + 84 + names.length * 58 + 28
  ctx.fillText(`${fmtTime(row.starts_at)} 开始`, 40, metaY)
  ctx.fillText(row.location ? `地点 ${row.location}` : merchantName(row.merchant_id), 40, metaY + 42)
  ctx.fillStyle = '#f36b21'
  ctx.font = '700 36px sans-serif'
  ctx.fillText(priceText(row), 40, metaY + 98)

  const QRCode = (await import('qrcode')).default
  const qrData = await QRCode.toDataURL(link, { width: 420, margin: 1, color: { dark: '#171b1f', light: '#ffffff' } })
  const qr = await loadImage(qrData)
  const qrSize = 220
  const qrX = W - 40 - qrSize
  const qrY = H - 40 - qrSize - 48
  ctx.fillStyle = '#ffffff'
  ctx.beginPath()
  ctx.roundRect(qrX - 16, qrY - 16, qrSize + 32, qrSize + 32, 18)
  ctx.fill()
  ctx.drawImage(qr, qrX, qrY, qrSize, qrSize)
  ctx.fillStyle = 'rgba(242,230,210,0.72)'
  ctx.font = '400 22px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('微信扫码报名', qrX + qrSize / 2, qrY + qrSize + 42)
  ctx.textAlign = 'left'
  ctx.fillStyle = 'rgba(242,230,210,0.45)'
  ctx.font = '600 22px sans-serif'
  ctx.fillText('观野FIT', 40, H - 48)

  return canvas.toDataURL('image/png')
}

async function openPoster(row: Activity) {
  posterRow.value = row
  posterUrl.value = ''
  posterLink.value = ''
  posterVisible.value = true
  posterLoading.value = true
  try {
    const { data } = await http.get<{ url: string }>(`/activities/${row.id}/share-link`)
    posterLink.value = data.url
    posterUrl.value = await composePoster(row, data.url)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '海报生成失败')
    posterVisible.value = false
  } finally {
    posterLoading.value = false
  }
}

async function copyPosterLink() {
  if (!posterLink.value) return
  try {
    await navigator.clipboard.writeText(posterLink.value)
    ElMessage.success('报名链接已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择链接')
  }
}

function downloadPoster() {
  if (!posterUrl.value || !posterRow.value) return
  const a = document.createElement('a')
  a.href = posterUrl.value
  a.download = `活动海报-${posterRow.value.name}.png`
  a.click()
}

async function refresh() {
  loading.value = true
  try {
    const m = await http.get('/merchants')
    merchants.value = merchantsWithSystem(m.data, 'gym')
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const { data } = await http.get<Page<Activity>>('/activities', {
      params: {
        merchant_id: merchantId.value,
        q: query.q.trim() || undefined,
        status: query.status || undefined,
        category: query.category.trim() || undefined,
        date_from: query.range?.[0] || undefined,
        date_to: query.range?.[1] || undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    rows.value = data.items
    total.value = data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void refresh()
}

function resetSearch() {
  query.q = ''
  query.status = ''
  query.category = ''
  query.range = undefined
  page.value = 1
  void refresh()
}

function openCreate() {
  if (!requireMerchant('请先选择商户后再新建活动')) return
  editing.value = null
  Object.assign(form, {
    name: '',
    category: '',
    location: '',
    cover_url: '',
    description: '',
    starts_at: '',
    ends_at: '',
    register_ends_at: '',
    capacity: 0,
    price: '0',
    member_price: '',
  })
  syncCoverList()
  formRef.value?.clearValidate()
  dialog.value = true
}

function openEdit(row: Activity) {
  editing.value = row
  Object.assign(form, {
    name: row.name,
    category: row.category || '',
    location: row.location || '',
    cover_url: row.cover_url || '',
    description: row.description || '',
    starts_at: row.starts_at,
    ends_at: row.ends_at,
    register_ends_at: row.register_ends_at || '',
    capacity: row.capacity,
    price: row.price,
    member_price: row.member_price ?? '',
  })
  syncCoverList()
  formRef.value?.clearValidate()
  dialog.value = true
}

function payload() {
  return {
    name: form.name.trim(),
    category: form.category.trim() || null,
    location: form.location.trim() || null,
    cover_url: form.cover_url || null,
    description: form.description.trim() || null,
    starts_at: form.starts_at,
    ends_at: form.ends_at,
    register_ends_at: form.register_ends_at || null,
    capacity: form.capacity || 0,
    price: form.price || '0',
    member_price: form.member_price === '' ? null : form.member_price,
  }
}

async function submit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    if (editing.value) {
      await http.patch(`/activities/${editing.value.id}`, payload())
      ElMessage.success('已保存')
    } else {
      const mid = requireMerchant('请先选择商户后再新建活动')
      if (!mid) return
      await http.post('/activities', { merchant_id: mid, ...payload() })
      ElMessage.success('活动已创建，发布后可开始报名')
    }
    dialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function changeStatus(row: Activity, action: 'publish' | 'close' | 'cancel') {
  const tips: Record<string, string> = {
    publish: `确认发布「${row.name}」并开放报名？`,
    close: `确认停止「${row.name}」的报名？`,
    cancel: `取消后已报名会员将全部作废，确认取消「${row.name}」？`,
  }
  try {
    await ElMessageBox.confirm(tips[action], '操作确认', { type: action === 'cancel' ? 'warning' : 'info' })
  } catch {
    return
  }
  try {
    await http.post(`/activities/${row.id}/${action}`)
    ElMessage.success('操作成功')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>活动管理</h3>
        <p class="lead">配置赛事、体验课等活动：上传海报、设置名额与报名费，发布后可生成报名海报给会员扫码。</p>
      </div>
      <el-button type="primary" @click="openCreate">新建活动</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="活动名称 / 场地 / ID" style="width: 200px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 140px">
          <el-option label="草稿" value="draft" />
          <el-option label="报名中" value="published" />
          <el-option label="已停止报名" value="closed" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
      </el-form-item>
      <el-form-item label="分类">
        <el-input v-model="query.category" clearable placeholder="如 赛事" style="width: 140px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="开始时间">
        <el-date-picker
          v-model="query.range"
          type="datetimerange"
          value-format="YYYY-MM-DDTHH:mm:ss"
          start-placeholder="起"
          end-placeholder="止"
          style="width: 320px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="海报" width="78">
        <template #default="{ row }">
          <img v-if="row.cover_url" class="thumb" :src="row.cover_url" alt="" />
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="活动" min-width="160" />
      <el-table-column prop="category" label="分类" width="100">
        <template #default="{ row }">{{ row.category || '—' }}</template>
      </el-table-column>
      <el-table-column label="时间" min-width="300">
        <template #default="{ row }">{{ fmtTime(row.starts_at) }} ~ {{ fmtTime(row.ends_at) }}</template>
      </el-table-column>
      <el-table-column label="报名截止" min-width="160">
        <template #default="{ row }">{{ fmtTime(row.register_ends_at) }}</template>
      </el-table-column>
      <el-table-column label="报名/名额" width="130">
        <template #default="{ row }">{{ capacityText(row) }}</template>
      </el-table-column>
      <el-table-column label="签到" width="80">
        <template #default="{ row }">{{ row.attended_count }}</template>
      </el-table-column>
      <el-table-column label="费用" width="120">
        <template #default="{ row }">
          <span v-if="!row.requires_payment">免费</span>
          <span v-else>¥{{ row.member_price ?? row.price }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTagType(row.status)">{{ activityStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="row.status === 'cancelled'" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="openPoster(row)">海报</el-button>
          <el-button
            v-if="row.status !== 'published'"
            link
            type="primary"
            :disabled="row.status === 'cancelled'"
            @click="changeStatus(row, 'publish')"
          >
            发布
          </el-button>
          <el-button v-else link type="warning" @click="changeStatus(row, 'close')">停止报名</el-button>
          <el-button link type="danger" :disabled="row.status === 'cancelled'" @click="changeStatus(row, 'cancel')">
            取消
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="refresh"
        @size-change="
          () => {
            page = 1
            refresh()
          }
        "
      />
    </div>

    <el-dialog v-model="dialog" :title="dialogTitle" width="680px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="活动名称" prop="name">
          <el-input v-model="form.name" maxlength="128" placeholder="如 夏季体测挑战赛" />
        </el-form-item>
        <el-form-item label="封面海报">
          <el-upload
            list-type="picture-card"
            accept=".jpg,.jpeg,.png,.webp"
            :limit="1"
            :file-list="coverList"
            :http-request="uploadCover"
            :on-preview="previewUploadFile"
            :on-remove="removeCover"
            :disabled="uploading"
            :class="{ 'hide-uploader': !!form.cover_url }"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
          <p class="hint block">会员 H5 / 小程序首页会展示这张图。不超过 8MB，支持 JPG / PNG / WEBP。</p>
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" maxlength="64" placeholder="如 赛事 / 体验课 / 会员日" />
        </el-form-item>
        <el-form-item label="场地">
          <el-input v-model="form.location" maxlength="128" placeholder="如 多功能厅" />
        </el-form-item>
        <el-form-item label="开始时间" prop="starts_at">
          <el-date-picker v-model="form.starts_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束时间" prop="ends_at">
          <el-date-picker v-model="form.ends_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="报名截止">
          <el-date-picker
            v-model="form.register_ends_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="留空则活动开始即截止"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="名额">
          <el-input-number v-model="form.capacity" :min="0" :max="100000" />
          <span class="hint">0 表示不限名额</span>
        </el-form-item>
        <el-form-item label="报名费">
          <el-input v-model="form.price" style="width: 160px" placeholder="0.00" />
          <span class="hint">0 为免费活动</span>
        </el-form-item>
        <el-form-item label="会员价">
          <el-input v-model="form.member_price" style="width: 160px" placeholder="留空则统一按报名费" />
        </el-form-item>
        <el-form-item label="活动说明">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="posterVisible" title="活动海报" width="420px">
      <div v-loading="posterLoading" class="poster-box">
        <img v-if="posterUrl" class="poster-preview" :src="posterUrl" alt="活动海报" />
        <p v-if="posterLink" class="poster-link">{{ posterLink }}</p>
      </div>
      <template #footer>
        <el-button @click="copyPosterLink" :disabled="!posterLink">复制链接</el-button>
        <el-button type="primary" :disabled="!posterUrl" @click="downloadPoster">下载海报</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}

.toolbar h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}

.lead {
  margin: 0;
  max-width: 640px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--el-text-color-secondary);
}

.filters {
  margin-bottom: 8px;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.hint {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.hint.block {
  margin: 8px 0 0;
}

.thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
  display: block;
}

.muted {
  color: var(--el-text-color-secondary);
}

.hide-uploader :deep(.el-upload--picture-card) {
  display: none;
}

.poster-box {
  min-height: 220px;
}

.poster-preview {
  width: 100%;
  border-radius: 8px;
  display: block;
}

.poster-link {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  word-break: break-all;
}
</style>
