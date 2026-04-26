<template>
  <el-card class="movie-card" @click="recordView">
    <img :src="movie.poster_url" class="movie-poster" />
    <div class="movie-info">
      <h3>{{ movie.title }}</h3>
      <p>{{ movie.release_year }} · {{ movie.director }}</p>
      <div class="genres">
        <el-tag v-for="genre in movie.genres" :key="genre" size="small">{{ genre }}</el-tag>
      </div>
      <p class="description">{{ truncateDescription(movie.description) }}</p>

      <!-- 新增：真实的评分信息区域 -->
      <div class="rating-section" v-if="hasRatingInfo">
        <div class="rating-item" v-if="hasUserRating">
          <span class="rating-label">我的评分：</span>
          <div class="user-rating">
            <el-rate v-model="movie.user_rating" disabled :max="5" :colors="['#99A9BF', '#F7BA2A', '#FF9900']"
              show-score text-color="#ff9900" score-template="{value}" />
          </div>
        </div>
        <div class="rating-item" v-else>
          <span class="rating-label">我的评分：</span>
          <span class="not-rated">暂未评分</span>
        </div>

        <div class="rating-item">
          <span class="rating-label">平均分：</span>
          <div class="average-rating">
            <span class="average-score">{{ formattedAverageRating }}</span>
            <span class="rating-count">（{{ movie.rating_count || 0 }}人评分）</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <action-buttons :movie="movie" @rate="$emit('rate', movie)" />
  </el-card>
</template>

<script>
import ActionButtons from './ActionButtons.vue'
import axios from 'axios'

export default {
  components: {
    ActionButtons
  },
  props: {
    movie: {
      type: Object,
      required: true
    }
  },
  computed: {
    user() {
      return this.$store.state.user
    },
    // 是否有评分信息
    hasRatingInfo() {
      return this.movie.average_rating !== undefined || this.movie.user_rating !== undefined
    },
    // 用户是否已评分
    hasUserRating() {
      return this.movie.user_rating !== null && this.movie.user_rating !== undefined
    },
    // 格式化平均分
    formattedAverageRating() {
      if (!this.movie.average_rating) return '0.0'
      return typeof this.movie.average_rating === 'number'
        ? this.movie.average_rating.toFixed(1)
        : parseFloat(this.movie.average_rating).toFixed(1)
    }
  },
  methods: {
    truncateDescription(desc) {
      if (!desc) return ''
      return desc.length > 100 ? desc.substring(0, 100) + '...' : desc
    },

    async recordView() {
      if (this.user) {
        try {
          await axios.post('/action', {
            user_id: this.user.id,
            action_type: 'VIEW',
            movie_id: this.movie.id
          })
        } catch (error) {
          console.error('记录浏览行为失败:', error)
        }
      }
    }
  }
}
</script>

<style scoped>
.movie-card {
  margin-bottom: 20px;
  cursor: pointer;
  transition: transform 0.3s, box-shadow 0.3s;
  position: relative;
}

.movie-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.1);
}

.movie-poster {
  width: 100%;
  height: 300px;
  object-fit: cover;
  border-radius: 4px 4px 0 0;
}

.movie-info {
  padding: 15px;
}

.genres {
  margin: 10px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.description {
  color: #666;
  font-size: 14px;
  line-height: 1.5;
  margin-top: 10px;
  margin-bottom: 15px;
}

/* 新增：评分信息样式 */
.rating-section {
  border-top: 1px solid #f0f0f0;
  padding-top: 15px;
  margin-top: 15px;
}

.rating-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  min-height: 32px;
}

.rating-item:last-child {
  margin-bottom: 0;
}

.rating-label {
  font-size: 14px;
  color: #606266;
  min-width: 70px;
}

.user-rating {
  flex: 1;
  display: flex;
  justify-content: flex-end;
}

.average-rating {
  display: flex;
  align-items: center;
  gap: 8px;
}

.average-score {
  font-size: 16px;
  font-weight: bold;
  color: #f56c6c;
}

.rating-count {
  font-size: 12px;
  color: #909399;
}

.not-rated {
  font-size: 14px;
  color: #c0c4cc;
  font-style: italic;
}

/* 调整星星评分组件的样式 */
:deep(.el-rate) {
  display: inline-flex;
  align-items: center;
}

:deep(.el-rate__icon) {
  font-size: 16px;
  margin-right: 2px;
}

:deep(.el-rate__text) {
  margin-left: 8px;
  font-size: 14px;
  font-weight: bold;
  color: #f56c6c;
}
</style>