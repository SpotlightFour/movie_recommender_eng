<template>
  <div class="movie-actions">
    <!-- 功能说明区域 -->
    <div class="action-labels" v-if="showLabels">
      <span class="action-label" :class="{ active: isLiked }">点赞</span>
      <span class="action-label" :class="{ active: isBookmarked }">收藏</span>
      <span class="action-label">评分</span>
    </div>

    <!-- 按钮区域 -->
    <div class="action-buttons">
      <!-- 点赞按钮 -->
      <div class="button-container">
        <el-tooltip :content="isLiked ? '取消点赞' : '点赞'" placement="top">
          <el-button :type="isLiked ? 'danger' : 'default'" :icon="isLiked ? 'el-icon-star-on' : 'el-icon-star-off'"
            circle size="small" @click.stop="toggleLike" class="action-button like-button">
          </el-button>
        </el-tooltip>
        <span class="button-text">{{ isLiked ? '已点赞' : '点赞' }}</span>
      </div>

      <!-- 收藏按钮 -->
      <div class="button-container">
        <el-tooltip :content="isBookmarked ? '取消收藏' : '收藏'" placement="top">
          <el-button :type="isBookmarked ? 'warning' : 'default'"
            :icon="isBookmarked ? 'el-icon-collection-tag' : 'el-icon-collection'" circle size="small"
            @click.stop="toggleBookmark" class="action-button bookmark-button">
          </el-button>
        </el-tooltip>
        <span class="button-text">{{ isBookmarked ? '已收藏' : '收藏' }}</span>
      </div>

      <!-- 评分按钮 -->
      <div class="button-container">
        <el-tooltip content="给电影评分" placement="top">
          <el-button type="primary" icon="el-icon-edit" circle size="small" @click.stop="$emit('rate')"
            class="action-button rate-button">
          </el-button>
        </el-tooltip>
        <span class="button-text">评分</span>
      </div>
    </div>

    <!-- 状态指示器（类似图片中的滑动指示符） -->
    <div class="action-indicator">
      <div class="indicator-dot" :class="{ active: currentAction === 'like' }"></div>
      <div class="indicator-dot" :class="{ active: currentAction === 'bookmark' }"></div>
      <div class="indicator-dot" :class="{ active: currentAction === 'rate' }"></div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage } from 'element-plus';

export default {
  name: 'MovieActions',
  props: {
    movie: Object,
    showLabels: {
      type: Boolean,
      default: true
    }
  },
  data() {
    return {
      isLiked: false,
      isBookmarked: false,
      currentAction: 'rate' // 当前激活的动作
    }
  },
  computed: {
    user() {
      return this.$store.state.user
    }
  },
  created() {
    this.initButtonStates()
  },
  methods: {
    initButtonStates() {
      if (!this.movie) return

      // 从电影数据中初始化状态
      this.isLiked = this.movie.user_liked || false
      this.isBookmarked = this.movie.user_bookmarked || false
    },

    async toggleLike() {
      if (!this.user) {
        ElMessage.warning('请先登录后再进行点赞')
        this.$emit('require-login')
        return
      }

      this.currentAction = 'like'

      try {
        const actionType = this.isLiked ? 'UNLIKE' : 'LIKE'
        const response = await axios.post('/action', {
          user_id: this.user.id,
          action_type: actionType,
          movie_id: this.movie.id
        })

        this.isLiked = !this.isLiked
        this.$emit('action-updated', {
          type: 'like',
          value: this.isLiked,
          movie: this.movie
        })

        ElMessage.success(this.isLiked ? '点赞成功！' : '已取消点赞')

      } catch (error) {
        console.error('点赞操作失败:', error)
        ElMessage.error('操作失败，请重试')
      }
    },

    async toggleBookmark() {
      if (!this.user) {
        ElMessage.warning('请先登录后再进行收藏')
        this.$emit('require-login')
        return
      }

      this.currentAction = 'bookmark'

      try {
        const actionType = this.isBookmarked ? 'UNBOOKMARK' : 'BOOKMARK'
        const response = await axios.post('/action', {
          user_id: this.user.id,
          action_type: actionType,
          movie_id: this.movie.id
        })

        this.isBookmarked = !this.isBookmarked
        this.$emit('action-updated', {
          type: 'bookmark',
          value: this.isBookmarked,
          movie: this.movie
        })

        ElMessage.success(this.isBookmarked ? '收藏成功！' : '已取消收藏')

      } catch (error) {
        console.error('收藏操作失败:', error)
        ElMessage.error('操作失败，请重试')
      }
    }
  },
  watch: {
    movie(newMovie) {
      if (newMovie) {
        this.initButtonStates()
      }
    }
  }
}
</script>

<style scoped>
.movie-actions {
  padding: 15px 0;
  border-top: 1px solid #f0f0f0;
  background: linear-gradient(135deg, #fafafa 0%, #ffffff 100%);
  border-radius: 0 0 8px 8px;
}

.action-labels {
  display: flex;
  justify-content: space-around;
  margin-bottom: 10px;
  padding: 0 20px;
}

.action-label {
  font-size: 12px;
  color: #909399;
  padding: 4px 8px;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.action-label.active {
  color: #409eff;
  background-color: #ecf5ff;
  font-weight: 500;
}

.action-buttons {
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 0 15px;
}

.button-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.action-button {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.action-button:hover {
  transform: scale(1.1);
}

.like-button:hover {
  background-color: #fef0f0;
  border-color: #f56c6c;
}

.bookmark-button:hover {
  background-color: #fdf6ec;
  border-color: #e6a23c;
}

.rate-button:hover {
  background-color: #ecf5ff;
  border-color: #409eff;
}

.button-text {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
}

.action-indicator {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-top: 12px;
  padding: 0 20px;
}

.indicator-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #dcdfe6;
  transition: all 0.3s ease;
}

.indicator-dot.active {
  background-color: #409eff;
  transform: scale(1.2);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .action-labels {
    padding: 0 10px;
  }

  .action-buttons {
    padding: 0 5px;
  }

  .action-button {
    width: 32px;
    height: 32px;
  }

  .button-text {
    font-size: 11px;
  }
}

/* 动画效果 */
@keyframes pulse {
  0% {
    transform: scale(1);
  }

  50% {
    transform: scale(1.05);
  }

  100% {
    transform: scale(1);
  }
}

.action-button:active {
  animation: pulse 0.3s ease;
}
</style>