<script setup lang="ts">
import {
  closeImagePreview,
  imagePreviewIndex,
  imagePreviewUrls,
  imagePreviewVisible,
} from '../imagePreview'
</script>

<template>
  <el-image-viewer
    v-if="imagePreviewVisible"
    :url-list="imagePreviewUrls"
    :initial-index="imagePreviewIndex"
    teleported
    :z-index="4000"
    @close="closeImagePreview"
  />
</template>
