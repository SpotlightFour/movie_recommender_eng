<template>
  <div class="preference-selector">
    <el-card class="selector-card">
      <div slot="header" class="card-header">
        <span>电影类型偏好设置</span>
        <el-tag type="success" v-if="isLoggedIn">
          已登录: {{ user.username }}
        </el-tag>
        <el-tag type="warning" v-else>
          未登录
        </el-tag>
      </div>

      <div class="preference-grid">
        <div class="genre-item" v-for="genre in genres" :key="genre" :class="getGenreCardClass(genre)">
          <div class="genre-header">
            <h3>{{ genre }}</h3>
            <el-tag :type="getPreferenceLevel(preferences[genre])" size="small">
              {{ getPreferenceText(preferences[genre]) }}
            </el-tag>
          </div>

          <el-slider v-model="preferences[genre]" :min="1" :max="5" :step="1" show-stops show-input :marks="sliderMarks"
            @change="handlePreferenceChange(genre)" />

          <div class="score-display">
            <span class="score-label">Current Score:</span>
            <span class="score-value">{{ preferences[genre] }}</span>
          </div>
        </div>
      </div>

      <!-- 推荐变化统计图表 -->
      <el-card class="stats-card" v-if="showRecommendationStats">
        <div slot="header" class="stats-header">
          <span>Recommendation Changes Prediction</span>
          <el-tooltip content="基于您当前的偏好设置预测推荐列表的变化" placement="top">
            <i class="el-icon-info"></i>
          </el-tooltip>
        </div>

        <div class="stats-content">
          <div class="chart-container">
            <div ref="chart" class="chart" style="height: 400px;"></div>
          </div>

          <!-- 电影详情列表 -->
          <div class="movies-detail" v-if="hasMovieData">
            <div class="movies-category">
              <div class="category-title new">
                <i class="el-icon-circle-plus"></i>
                <span>新增推荐 ({{ stats.changes.new_movies.length }})</span>
              </div>
              <div class="movies-list">
                <div v-for="movie in stats.changes.new_movies" :key="'new-' + movie.id" class="movie-item">
                  <div class="movie-info">
                    <span class="movie-title">{{ movie.title }}</span>
                    <div class="movie-meta">
                      <el-tag size="small" type="success">{{ movie.prediction_score }}分</el-tag>
                      <span class="movie-genres">{{ movie.genres.join('、') }}</span>
                    </div>
                  </div>
                  <div class="movie-reason" v-if="movie.reason">{{ movie.reason }}</div>
                </div>
              </div>
            </div>

            <div class="movies-category">
              <div class="category-title removed">
                <i class="el-icon-remove"></i>
                <span>移除推荐 ({{ stats.changes.removed_movies.length }})</span>
              </div>
              <div class="movies-list">
                <div v-for="movie in stats.changes.removed_movies" :key="'removed-' + movie.id" class="movie-item">
                  <div class="movie-info">
                    <span class="movie-title">{{ movie.title }}</span>
                    <div class="movie-meta">
                      <el-tag size="small" type="danger">{{ movie.prediction_score }}分</el-tag>
                      <span class="movie-genres">{{ movie.genres.join('、') }}</span>
                    </div>
                  </div>
                  <div class="movie-reason" v-if="movie.reason">{{ movie.reason }}</div>
                </div>
              </div>
            </div>

            <div class="movies-category">
              <div class="category-title unchanged">
                <i class="el-icon-document"></i>
                <span>保持不变 ({{ stats.changes.unchanged_movies.length }})</span>
              </div>
              <div class="movies-list">
                <div v-for="movie in stats.changes.unchanged_movies" :key="'unchanged-' + movie.id" class="movie-item">
                  <div class="movie-info">
                    <span class="movie-title">{{ movie.title }}</span>
                    <div class="movie-meta">
                      <el-tag size="small" type="info">{{ movie.prediction_score }}分</el-tag>
                      <span class="movie-genres">{{ movie.genres.join('、') }}</span>
                    </div>
                  </div>
                  <div class="movie-reason" v-if="movie.reason">{{ movie.reason }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="stats-footer">
          <el-alert title="提示" type="info" show-icon :closable="false" description="此预测基于您当前的偏好设置，实际推荐结果可能有所不同" />
        </div>
      </el-card>

      <div class="action-section">
        <div class="action-buttons">
          <el-button type="primary" icon="el-icon-check" @click="submitPreferences" :loading="submitting"
            :disabled="!isLoggedIn" size="default">
            {{ submitting ? '保存中...' : '保存偏好' }}
          </el-button>

          <el-button icon="el-icon-refresh" @click="resetPreferences" :disabled="submitting" size="default">
            重置为默认
          </el-button>

          <el-button icon="el-icon-back" @click="$router.go(-1)" size="default">
            返回
          </el-button>
        </div>

        <div v-if="!isLoggedIn" class="login-prompt">
          <el-alert title="登录提示" type="warning" show-icon :closable="false">
            请先<router-link to="/login" class="login-link">登录</router-link>以保存偏好设置
          </el-alert>
        </div>
      </div>
    </el-card>

    <!-- 操作反馈 -->
    <transition name="el-fade-in">
      <div v-if="message" :class="['message-feedback', messageType]">
        <i :class="getMessageIcon(messageType)"></i>
        {{ message }}
      </div>
    </transition>
  </div>
</template>

<script>
import { mapState, mapGetters } from 'vuex'
import axios from 'axios'
import * as echarts from 'echarts'

export default {
  name: 'PreferenceSelector',
  data() {
    return {
      genres: [
        'Action', 'Adventure', 'Animation', 'Comedy', 'Crime',
        'Documentary', 'Drama', 'Fantasy', 'Horror', 'Musical',
        'Mystery', 'Romance', 'Sci-Fi', 'Thriller', 'War', 'Western',
        'IMAX','Children'
      ],
      preferences: {},
      submitting: false,
      message: '',
      messageType: 'success',
      sliderMarks: {  // 调整为1-5分的标记
        1: 'Poor',
        2: 'Dislike',
        3: 'Neutral',
        4: 'Like',
        5: 'Recommend'
      },
      // 图表相关数据
      chart: null,
      stats: {
        newRecommendations: 0,
        removedRecommendations: 0,
        unchangedRecommendations: 0,
        changes: {
          new_movies: [],
          removed_movies: [],
          unchanged_movies: []
        }
      },
      showRecommendationStats: false,
      debounceTimer: null,
      chartInitialized: false,
      resizeHandler: null
    }
  },
  computed: {
    ...mapState(['user']),
    ...mapGetters(['isLoggedIn']),
    // 检查是否有电影数据
    hasMovieData() {
      return this.stats.changes && (
        this.stats.changes.new_movies.length > 0 ||
        this.stats.changes.removed_movies.length > 0 ||
        this.stats.changes.unchanged_movies.length > 0
      )
    }
  },
  created() {
    this.initializePreferences()
    if (this.isLoggedIn) {
      this.loadUserPreferences()
    }
  },
  mounted() {
    // 延迟初始化图表，确保DOM已渲染
    this.$nextTick(() => {
      setTimeout(() => {
        this.initChart()
      }, 100)
    })
  },
  beforeDestroy() {
    if (this.chart) {
      this.chart.dispose()
      this.chart = null
    }
    if (this.resizeHandler) {
      window.removeEventListener('resize', this.resizeHandler)
    }
  },
  methods: {
    initializePreferences() {
      const initialPrefs = {}
      // 默认值设为0
      this.genres.forEach(genre => {
        initialPrefs[genre] = 0
      })
      this.preferences = { ...initialPrefs }
    },

    async loadUserPreferences() {
      try {
        const response = await axios.get(`/preferences/${this.user.id}`)
        if (response.data) {
          this.preferences = { ...this.preferences, ...response.data }
          this.showMessage('已加载您的偏好设置', 'success')
          // 加载偏好后立即计算推荐变化
          this.calculateRecommendationChanges()
        }
      } catch (error) {
        console.log('暂无保存的偏好设置')
      }
    },

    handlePreferenceChange(genre) {
      console.log(`🎬 ${genre} 偏好更新为: ${this.preferences[genre]}`)

      // 添加防抖，避免频繁调用接口
      clearTimeout(this.debounceTimer)
      this.debounceTimer = setTimeout(() => {
        this.calculateRecommendationChanges()
      }, 500)
    },

    // calculateRecommendationChanges 方法
    async calculateRecommendationChanges() {
      try {
        if (!this.isLoggedIn) {
          this.showRecommendationStats = false
          return
        }

        console.log('🎯 开始计算推荐变化预测...')

        // 调用后端预测接口
        const response = await this.$http.post('/recommendations/predict', {
          user_id: this.user.id,
          preferences: this.preferences
        })

        console.log('📊 推荐变化预测响应:', response.data)

        // 更新完整的统计数据，包括详细电影信息
        this.stats = {
          newRecommendations: response.data.stats.new_recommendations,
          removedRecommendations: response.data.stats.removed_recommendations,
          unchangedRecommendations: response.data.stats.unchanged_recommendations,
          changes: response.data.changes || {
            new_movies: [],
            removed_movies: [],
            unchanged_movies: []
          }
        }

        this.updateChart()
        this.showRecommendationStats = true

        console.log('✅ 推荐变化计算完成:', this.stats)

      } catch (error) {
        console.error('❌ 计算推荐变化失败:', error)
        // 如果后端接口不可用，使用前端模拟作为降级方案
        this.simulateMovieDetails()
      }
    },

    // 初始化图表
    initChart() {
      if (!this.$refs.chart) {
        console.warn('图表容器未找到，延迟初始化')
        setTimeout(() => {
          this.initChart()
        }, 100)
        return
      }

      try {
        // 如果图表已存在，先销毁
        if (this.chart) {
          this.chart.dispose()
        }

        this.chart = echarts.init(this.$refs.chart)
        this.chartInitialized = true

        // 设置初始图表
        this.updateChart()

        // 响应式调整
        this.resizeHandler = () => {
          if (this.chart) {
            this.chart.resize()
          }
        }

        window.addEventListener('resize', this.resizeHandler)

        console.log('✅ 图表初始化完成')
      } catch (error) {
        console.error('❌ 图表初始化失败:', error)
        this.chartInitialized = false
      }
    },

    // 更新图表数据
    updateChart() {
      if (!this.chart || !this.chartInitialized) {
        console.log('图表未初始化，跳过更新')
        if (!this.chartInitialized) {
          this.initChart()
        }
        return
      }

      try {
        const option = this.getChartOption()
        this.chart.setOption(option, true)
        console.log('✅ 图表更新完成')
      } catch (error) {
        console.error('❌ 图表更新失败:', error)
      }
    },

    // 获取图表配置 - 改为纵向条形图
    getChartOption() {
      // 从stats.changes中获取电影数据
      const newMovies = this.stats.changes?.new_movies || []
      const removedMovies = this.stats.changes?.removed_movies || []
      const unchangedMovies = this.stats.changes?.unchanged_movies || []

      // 合并所有电影数据，并添加类型标识
      const allMovies = [
        ...newMovies.map(movie => ({ ...movie, type: 'new', typeText: '新增推荐' })),
        ...removedMovies.map(movie => ({ ...movie, type: 'removed', typeText: '移除推荐' })),
        ...unchangedMovies.map(movie => ({ ...movie, type: 'unchanged', typeText: '保持不变' }))
      ]

      // 按预测评分降序排列
      allMovies.sort((a, b) => b.prediction_score - a.prediction_score)

      // 如果数据为空，显示空状态
      if (allMovies.length === 0) {
        return {
          title: {
            text: '暂无推荐变化数据',
            left: 'center',
            top: 'center',
            textStyle: {
              color: '#909399',
              fontSize: 16,
              fontWeight: 'normal'
            }
          },
          xAxis: { show: false },
          yAxis: { show: false },
          series: []
        }
      }

      return {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          },
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          borderColor: '#ddd',
          borderWidth: 1,
          textStyle: {
            color: '#303133'
          },
          formatter: (params) => {
            const movie = params[0].data
            return `
              <div style="max-width: 300px;">
                <div style="font-weight: bold; color: #303133; margin-bottom: 8px; font-size: 14px;">
                  ${movie.name}
                </div>
                <div style="color: #606266; margin-bottom: 4px;">
                  <span style="color: #409eff;">Predicted Rating: ${movie.value}分</span>
                </div>
                <div style="color: #606266; margin-bottom: 4px;">
                  类型: ${movie.genres?.join('、') || '未知'}
                </div>
                <div style="color: #606266; margin-bottom: 4px;">
                  状态: <span style="color: ${movie.type === 'new' ? '#67c23a' :
                movie.type === 'removed' ? '#f56c6c' : '#409eff'
              };">${movie.typeText}</span>
                </div>
                ${movie.reason ? `
                <div style="color: #909399; font-size: 12px; margin-top: 6px; padding-top: 6px; border-top: 1px dashed #eee;">
                  ${movie.reason}
                </div>` : ''}
              </div>
            `
          }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '15%',
          top: '10%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: allMovies.map(movie => {
            // 电影名称过长时截断显示
            const title = movie.title
            return title.length > 15 ? title.substring(0, 15) + '...' : title
          }),
          axisLine: {
            lineStyle: {
              color: '#909399'
            }
          },
          axisLabel: {
            color: '#606266',
            fontSize: 12,
            interval: 0,
            rotate: 30 // 标签旋转30度，避免重叠
          },
          axisTick: {
            show: true,
            alignWithLabel: true
          }
        },
        yAxis: {
          type: 'value',
          name: 'Predicted Rating',
          min: 0,
          max: 5,
          axisLine: {
            lineStyle: {
              color: '#909399'
            }
          },
          axisLabel: {
            color: '#606266',
            formatter: '{value}'
          },
          splitLine: {
            lineStyle: {
              color: '#f0f0f0',
              type: 'dashed'
            }
          }
        },
        series: [
          {
            name: 'Predicted Rating',
            type: 'bar',
            data: allMovies.map(movie => ({
              value: movie.prediction_score,
              name: movie.title,
              type: movie.type,
              typeText: movie.typeText,
              genres: movie.genres,
              reason: movie.reason,
              itemStyle: {
                color: movie.type === 'new' ?
                  new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: '#67c23a' },
                    { offset: 1, color: '#85ce61' }
                  ]) :
                  movie.type === 'removed' ?
                    new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                      { offset: 0, color: '#f56c6c' },
                      { offset: 1, color: '#f78989' }
                    ]) :
                    new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                      { offset: 0, color: '#409eff' },
                      { offset: 1, color: '#79bbff' }
                    ]),
                borderRadius: [4, 4, 0, 0]
              }
            })),
            label: {
              show: true,
              position: 'top',
              formatter: '{c}',
              color: '#303133',
              fontWeight: 'bold',
              fontSize: 11
            },
            barWidth: '60%',
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)'
              }
            }
          }
        ],
        legend: {
          data: ['新增推荐', '移除推荐', '保持不变'],
          top: 'bottom',
          textStyle: {
            color: '#606266'
          }
        }
      }
    },

    // 调整为1-5分的阈值
    getPreferenceLevel(score) {
      if (score == 1) return 'danger'    // 1: 很差
      if (score == 2) return 'info'     // 2: 不喜欢
      if (score == 3) return 'warning'    // 3: 一般
      if (score == 4) return 'primary'     // 4: 喜欢
      return 'success'                      // 5: 力荐
    },

    // 调整为1-5分的文本
    getPreferenceText(score) {
      if (score == 1) return 'Poor'    // 1: 很差
      if (score == 2) return 'Dislike'     // 2: 不喜欢
      if (score == 3) return 'Neutral'    // 3: 一般
      if (score == 4) return 'Like'     // 4: 喜欢
      return 'Recommend'                      // 5: 力荐
    },

    // 调整为1-5分的卡片类
    getGenreCardClass(genre) {
      const score = this.preferences[genre]
      if (score === 1) return 'genre-strong-dislike'  // 很差
      if (score === 2) return 'genre-dislike'         // 不喜欢
      if (score === 3) return 'genre-neutral'         // 一般
      if (score === 4) return 'genre-like'            // 喜欢
      return 'genre-strong-like'                      // 力荐
    },

    getMessageIcon(type) {
      const icons = {
        success: 'el-icon-success',
        error: 'el-icon-error',
        warning: 'el-icon-warning',
        info: 'el-icon-info'
      }
      return icons[type] || 'el-icon-info'
    },

    async submitPreferences() {
      if (!this.isLoggedIn) {
        this.showMessage('请先登录以保存偏好设置', 'error')
        return
      }

      this.submitting = true

      try {
        console.log('🚀 开始保存偏好设置...')

        const response = await axios.post('/preferences', {
          user_id: this.user.id,
          preferences: this.preferences
        })

        console.log('✅ 保存成功!')
        console.log('📊 响应数据:', response.data)

        this.showMessage('偏好设置保存成功！', 'success')

        // 更新用户画像
        await this.updateUserProfile()

      } catch (error) {
        console.error('❌ 保存失败:', error)
        const errorMsg = error.response?.data?.error || '保存失败，请重试'
        this.showMessage(errorMsg, 'error')
      } finally {
        this.submitting = false
      }
    },

    async updateUserProfile() {
      try {
        await axios.post(`/profile/update/${this.user.id}`)
        console.log('👤 用户画像已更新')
      } catch (error) {
        console.error('更新用户画像失败:', error)
      }
    },

    resetPreferences() {
      this.$confirm('确定要重置所有偏好设置为默认值吗？', '重置确认', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.initializePreferences()
        this.showMessage('偏好设置已重置为默认值', 'info')
        // 重置后重新计算推荐变化
        this.calculateRecommendationChanges()
        this.$emit('preferences-reset')
      })
    },

    showMessage(msg, type = 'success') {
      this.message = msg
      this.messageType = type

      setTimeout(() => {
        this.message = ''
      }, 3000)
    }
  },

  watch: {
    isLoggedIn(newVal) {
      if (newVal) {
        this.loadUserPreferences()
      }
    }
  }
}
</script>

<style scoped>
.preference-selector {
  padding: 20px 0;
}

.selector-card {
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 18px;
  font-weight: 600;
}

.preference-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
  margin: 20px 0;
}

.genre-item {
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  transition: all 0.3s ease;
}

.genre-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.genre-strong-dislike {
  border-left: 4px solid #f56c6c; /* danger - 红色，对应1分 */
  background: linear-gradient(135deg, #fef0f0 0%, #ffffff 100%);
}

.genre-dislike {
  border-left: 4px solid #9fc8f1; /* info - 蓝色，对应2分 */
  background: linear-gradient(135deg, #f0f9ff 0%, #ffffff 100%);
}

.genre-neutral {
  border-left: 4px solid #e6a23c; /* warning - 橙色，对应3分 */
  background: linear-gradient(135deg, #fdf6ec 0%, #ffffff 100%);
}

.genre-like {
  border-left: 4px solid #3375e0; /* primary - 深蓝色，对应4分 */
  background: linear-gradient(135deg, #c0d8f4 0%, #ffffff 100%);
}

.genre-strong-like {
  border-left: 4px solid #67c23a; /* success - 绿色，对应5分 */
  background: linear-gradient(135deg, #f0f9eb 0%, #ffffff 100%);
}
.genre-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.genre-header h3 {
  margin: 0;
  color: #303133;
  font-size: 16px;
}

.score-display {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e4e7ed;
}

.score-label {
  color: #909399;
  font-size: 14px;
}

.score-value {
  color: #409eff;
  font-weight: 600;
  font-size: 16px;
}

/* 统计图表样式 */
.stats-card {
  margin-top: 30px;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
}

.stats-header .el-icon-info {
  color: #409eff;
  cursor: pointer;
}

.stats-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chart-container {
  width: 100%;
  height: 400px;
  min-height: 400px;
}

.chart {
  width: 100%;
  height: 100%;
}

/* 电影详情列表样式 */
.movies-detail {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.movies-category {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.category-title {
  padding: 12px 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #e4e7ed;
}

.category-title.new {
  background: linear-gradient(135deg, #f0f9eb, #e1f3d8);
  color: #67c23a;
}

.category-title.removed {
  background: linear-gradient(135deg, #fef0f0, #fde2e2);
  color: #f56c6c;
}

.category-title.unchanged {
  background: linear-gradient(135deg, #f0f9ff, #d9ecff);
  color: #409eff;
}

.movies-list {
  padding: 10px;
}

.movie-item {
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.3s;
}

.movie-item:hover {
  background-color: #f8f9fa;
}

.movie-item:last-child {
  border-bottom: none;
}

.movie-info {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.movie-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  flex: 1;
  margin-right: 10px;
  line-height: 1.4;
}

.movie-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.movie-genres {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.movie-reason {
  font-size: 12px;
  color: #606266;
  padding: 6px 8px;
  background: #f5f7fa;
  border-radius: 4px;
  line-height: 1.4;
}

.stats-footer {
  margin-top: 20px;
}

.action-section {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid #e4e7ed;
}

.action-buttons {
  text-align: center;
  margin-bottom: 20px;
}

.action-buttons .el-button {
  margin: 0 8px;
  min-width: 120px;
}

.login-prompt {
  margin-top: 20px;
}

.login-link {
  color: #409eff;
  text-decoration: none;
  margin-left: 5px;
}

.login-link:hover {
  text-decoration: underline;
}

.message-feedback {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 12px 20px;
  border-radius: 4px;
  z-index: 2000;
  display: flex;
  align-items: center;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.message-feedback.success {
  background-color: #f0f9ff;
  color: #67c23a;
  border: 1px solid #e1f3d8;
}

.message-feedback.error {
  background-color: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fde2e2;
}

.message-feedback.info {
  background-color: #f4f4f5;
  color: #909399;
  border: 1px solid #e9e9eb;
}

.message-feedback i {
  margin-right: 8px;
  font-size: 16px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .preference-grid {
    grid-template-columns: 1fr;
  }

  .movies-detail {
    grid-template-columns: 1fr;
  }

  .movie-info {
    flex-direction: column;
    align-items: flex-start;
  }

  .movie-meta {
    flex-direction: row;
    align-items: center;
    margin-top: 5px;
  }

  .chart-container {
    height: 500px;
  }

  .action-buttons .el-button {
    display: block;
    width: 100%;
    margin: 8px 0;
  }
}

@media (max-width: 480px) {
  .movie-title {
    font-size: 13px;
  }

  .chart-container {
    height: 600px;
  }
}
</style>