<template>
  <div class="preferences-page">
    <div class="page-header">
      <h1>偏好设置</h1>
      <p>个性化您的电影推荐体验</p>
    </div>
    
    <preference-selector 
      @preferences-saved="handlePreferencesSaved"
      @preferences-reset="handlePreferencesReset"
    />
  </div>
</template>

<script>
import PreferenceSelector from '@/components/PreferenceSelector.vue'
import { ElMessage } from 'element-plus';

export default {
  name: 'PreferencesPage',
  components: {
    PreferenceSelector
  },
  methods: {
    handlePreferencesSaved(preferences) {
      ElMessage.success('偏好设置已保存，将影响您的推荐结果')
      // 可以在这里触发推荐更新等操作
    },
    handlePreferencesReset() {
      ElMessage.info('偏好设置已重置为默认值')
    }
  }
}
</script>

<style scoped>
.preferences-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  text-align: center;
  margin-bottom: 30px;
}

.page-header h1 {
  color: #303133;
  margin-bottom: 10px;
}

.page-header p {
  color: #606266;
  font-size: 16px;
}
</style>