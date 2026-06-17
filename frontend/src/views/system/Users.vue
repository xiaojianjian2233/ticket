<script setup>
import { onMounted, ref } from 'vue'
import { userApi } from '@/api'
import { ElMessage } from 'element-plus'
const rows = ref([])
const load = async () => { const d = await userApi.list({ page_no: 1, page_size: 100 }); rows.value = d.items }
const save = async (u) => { await userApi.update(u.id, { role: u.role, is_active: u.isActive }); ElMessage.success('已保存') }
onMounted(load)
</script>
<template>
  <el-card header="用户管理">
    <el-table :data="rows" stripe>
      <el-table-column prop="name" label="姓名" width="140"/>
      <el-table-column prop="email" label="邮箱"/>
      <el-table-column label="角色" width="160"><template #default="{row}">
        <el-select v-model="row.role" size="small" @change="save(row)"><el-option label="访客" value="visitor"/><el-option label="处理人" value="handler"/><el-option label="管理员" value="admin"/></el-select>
      </template></el-table-column>
      <el-table-column label="启用" width="100"><template #default="{row}"><el-switch v-model="row.isActive" @change="save(row)"/></template></el-table-column>
      <el-table-column prop="lastLoginAt" label="最后登录" width="180"/>
    </el-table>
  </el-card>
</template>
