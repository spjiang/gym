<script setup lang="ts">
import { ArrowDown } from '@element-plus/icons-vue'

export type RowMoreItem = {
  command: string
  label: string
  disabled?: boolean
  danger?: boolean
  divided?: boolean
}

defineProps<{
  more?: RowMoreItem[]
}>()

const emit = defineEmits<{
  more: [command: string]
}>()
</script>

<template>
  <div class="row-actions">
    <slot />
    <el-dropdown v-if="more?.length" trigger="click" teleported @command="emit('more', String($event))">
      <el-button size="small">
        更多<el-icon class="more-icon"><ArrowDown /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="item in more"
            :key="item.command"
            :command="item.command"
            :disabled="item.disabled"
            :divided="item.divided"
            :class="{ 'is-danger': item.danger }"
          >
            {{ item.label }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<style scoped>
.row-actions {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}
.more-icon {
  margin-left: 2px;
}
:deep(.is-danger) {
  color: #b42318;
}
</style>
