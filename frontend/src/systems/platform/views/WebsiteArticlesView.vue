<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type UploadRequestOptions, type UploadUserFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import http from '../../../core/api/http'

type Channel = 'news' | 'jobs' | 'partners'
type Article = {
  id: number
  channel: Channel
  title: string
  summary: string | null
  cover_image_url: string | null
  body: string
  contact_hint: string | null
  status: 'draft' | 'published' | 'archived'
  published_at: string | null
  sort_order: number
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const LABELS: Record<Channel, { title: string; hint: string }> = {
  news: { title: '新闻动态', hint: '官网 /news 展示已发布内容。' },
  jobs: { title: '招聘信息', hint: '文末可填联系方式，官网不收简历。' },
  partners: { title: '招商入驻', hint: '文末可填联系方式，官网不收集意向表。' },
}

const route = useRoute()
const channel = computed(() => (route.meta.channel as Channel) || 'news')
const loading = ref(false)
const rows = ref<Article[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const statusFilter = ref('')
const keyword = ref('')
const dialogVisible = ref(false)
const submitting = ref(false)
const uploading = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  title: '',
  summary: '',
  cover_image_url: '',
  body: '',
  contact_hint: '',
  sort_order: 0,
})
const coverList = computed<UploadUserFile[]>(() =>
  form.cover_image_url ? [{ name: '封面', url: form.cover_image_url, uid: 1 }] : [],
)

function statusText(s: Article['status']) {
  if (s === 'published') return '已发布'
  if (s === 'archived') return '已下架'
  return '草稿'
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await http.get<Page<Article>>('/website/articles', {
      params: {
        channel: channel.value,
        status: statusFilter.value || undefined,
        q: keyword.value.trim() || undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    rows.value = data.items
    total.value = data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void loadList()
}

function openCreate() {
  editingId.value = null
  form.title = ''
  form.summary = ''
  form.cover_image_url = ''
  form.body = ''
  form.contact_hint = ''
  form.sort_order = 0
  dialogVisible.value = true
}

function openEdit(row: Article) {
  editingId.value = row.id
  form.title = row.title
  form.summary = row.summary || ''
  form.cover_image_url = row.cover_image_url || ''
  form.body = row.body || ''
  form.contact_hint = row.contact_hint || ''
  form.sort_order = row.sort_order || 0
  dialogVisible.value = true
}

async function uploadCover(opt: UploadRequestOptions) {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', opt.file as File)
    const { data } = await http.post<{ url: string }>('/uploads', fd, { timeout: 30000 })
    form.cover_image_url = data.url
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '封面上传失败')
  } finally {
    uploading.value = false
  }
}

async function save() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  submitting.value = true
  try {
    const payload = {
      title: form.title.trim(),
      summary: form.summary.trim() || null,
      cover_image_url: form.cover_image_url || null,
      body: form.body,
      contact_hint: form.contact_hint.trim() || null,
      sort_order: Number(form.sort_order || 0),
    }
    if (editingId.value) {
      await http.patch(`/website/articles/${editingId.value}`, payload)
      ElMessage.success('已保存')
    } else {
      await http.post('/website/articles', { channel: channel.value, ...payload })
      ElMessage.success('已创建为草稿')
    }
    dialogVisible.value = false
    await loadList()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function publish(row: Article) {
  try {
    await http.post(`/website/articles/${row.id}/publish`)
    ElMessage.success('已发布')
    await loadList()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '发布失败')
  }
}

async function archive(row: Article) {
  try {
    await http.post(`/website/articles/${row.id}/archive`)
    ElMessage.success('已下架')
    await loadList()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '下架失败')
  }
}

async function remove(row: Article) {
  try {
    await ElMessageBox.confirm(`删除「${row.title}」？官网将立即不可见。`, '删除文章', { type: 'warning' })
    await http.delete(`/website/articles/${row.id}`)
    ElMessage.success('已删除')
    await loadList()
  } catch (e: unknown) {
    if (e === 'cancel') return
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

watch(channel, () => {
  page.value = 1
  statusFilter.value = ''
  keyword.value = ''
  void loadList()
})

onMounted(loadList)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>{{ LABELS[channel].title }}</h3>
        <p class="hint">{{ LABELS[channel].hint }}</p>
      </div>
      <el-button type="primary" @click="openCreate">新建</el-button>
    </div>

    <div class="filters">
      <el-input v-model="keyword" placeholder="搜索标题" clearable style="width: 220px" @keyup.enter="search" />
      <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 140px" @change="search">
        <el-option label="草稿" value="draft" />
        <el-option label="已发布" value="published" />
        <el-option label="已下架" value="archived" />
      </el-select>
      <el-button @click="search">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">{{ statusText(row.status) }}</template>
      </el-table-column>
      <el-table-column prop="published_at" label="发布时间" width="180" />
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.status !== 'published'" link type="primary" @click="publish(row)">发布</el-button>
          <el-button v-if="row.status === 'published'" link @click="archive(row)">下架</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadList"
        @size-change="loadList"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑文章' : '新建文章'" width="720px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="160" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" maxlength="255" />
        </el-form-item>
        <el-form-item label="封面">
          <el-upload
            list-type="picture-card"
            accept=".jpg,.jpeg,.png,.webp"
            :limit="1"
            :file-list="coverList"
            :http-request="uploadCover"
            :on-remove="() => (form.cover_image_url = '')"
            :disabled="uploading"
            :class="{ 'hide-uploader': !!form.cover_image_url }"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="form.body" type="textarea" :rows="10" placeholder="Markdown" />
        </el-form-item>
        <el-form-item v-if="channel !== 'news'" label="联系提示">
          <el-input v-model="form.contact_hint" maxlength="255" placeholder="电话 / 微信等，展示在详情页" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :step="1" />
          <span class="hint" style="margin-left: 8px">越大越靠前</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0;
}
.hint {
  margin: 4px 0 0;
  color: var(--admin-ink-muted);
  font-size: 13px;
}
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.hide-uploader :deep(.el-upload--picture-card) {
  display: none;
}
</style>
