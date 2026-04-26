<template>
  <div class="recommendation-page">
    <div class="header">
      <h1>为您推荐</h1>
      <p class="subtitle">基于您的观影偏好精心挑选</p>
    </div>

    <div v-if="recommendedMovies.length === 0" class="loading">
      <div class="spinner"></div>
      <p>正在为您精心挑选电影...</p>
    </div>

    <div v-else class="recommendations-container">
      <div v-for="(movie, index) in recommendedMovies" :key="movie.id" class="movie-card">
        <div class="movie-image-container">
          <img :src="movie.poster_url || '/placeholder-movie.jpg'" :alt="movie.title" class="movie-image"
            @error="handleImageError" />
        </div>

        <div class="movie-content">
          <div class="movie-header">
            <h2 class="movie-title">{{ movie.title }}</h2>
            <div class="movie-rating">
              <span class="rating-value">{{ movie.average_rating ? movie.average_rating.toFixed(1) : 'N/A' }}</span>
              <div class="stars">
                <span v-for="n in 5" :key="n" class="star"
                  :class="{ 'filled': n <= Math.floor(movie.average_rating || 0) }">★</span>
              </div>
            </div>
          </div>

          <div class="movie-meta">
            <p class="movie-director"><strong>Director:</strong> {{ movie.director || '未知' }}</p>
            <p class="movie-year"><strong>Release Year:</strong> {{ movie.year || movie.release_year || '未知' }}</p>
            <p class="movie-genre"><strong>Genre:</strong> {{ formatGenres(movie.genres) }}</p>
            <p class="movie-actors" v-if="movie.actors && movie.actors.length > 0">
              <strong>Lead Cast​:</strong> {{ formatActors(movie.actors) }}
            </p>
          </div>


           <!-- 添加预测评分部分 -->
          <div class="predicted-rating-section">
            <div class="predicted-rating-display">
              <span>Predicted Rating:</span>
              <div class="predicted-stars">
                <span v-for="n in 5" :key="n" class="star predicted-star"
                  :class="{ 'filled': n <= Math.floor(movie.predicted_rating || 0) }">★</span>
              </div>
              <span class="predicted-rating-value">{{ movie.predicted_rating ? movie.predicted_rating.toFixed(1) : 'N/A' }}</span>
            </div>
            <div class="prediction-explanation">
              <i class="el-icon-info"></i>
              <span>{{ movie.prediction_reason }}</span>
            </div>
          </div>

          <div class="user-rating-section">
            <div v-if="movie.user_rating" class="user-rating-display">
              <span>Your Rating:</span>
              <div class="user-stars">
                <span v-for="n in 5" :key="n" class="star"
                  :class="{ 'filled': n <= Math.floor(movie.user_rating) }">★</span>
              </div>
              <span class="user-rating-value">{{ movie.user_rating.toFixed(1) }}</span>
            </div>
            <el-button v-else type="primary" size="small" @click="openRatingDialog(movie)" class="rate-button">
              立即评分
            </el-button>
          </div>

          <div class="explanation-section">
            <div class="explanation-tabs">
              <button v-for="n in 3" :key="n" class="explanation-tab" :class="{ 'active': activeTab[index] === n }"
                @click="toggleExplanation(index, n, movie)">
                {{ getTabLabel(n) }}
              </button>
            </div>

            <div class="explanation-content" v-if="activeTab[index]">
              <div v-if="!hasValidExplanation(movie, activeTab[index]) && !loadingExplanation[index]"
                class="explanation-placeholder">
                点击上方按钮查看推荐理由
              </div>
              <div v-else-if="loadingExplanation[index]" class="explanation-loading">
                <div class="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                正在生成解释...
              </div>
              <div v-else class="explanation-display">
                <!-- 解释3显示流程图 -->
                <div v-if="activeTab[index] === 3" class="mermaid-container">
                  <div v-if="movie.flowchartSvg" class="mermaid-chart" v-html="movie.flowchartSvg"></div>
                  <div v-else-if="mermaidError[index]" class="mermaid-error">
                    <div class="error-title">流程图渲染失败，显示文本解释：</div>
                    <pre class="mermaid-text">{{ movie.explanation3 }}</pre>
                  </div>
                  <div v-else class="mermaid-text">
                    {{ movie.explanation3 }}
                  </div>
                </div>
                <!-- 解释1和2显示普通文本 -->
                <div v-else class="explanation-text">
                  {{ movie[`explanation${activeTab[index]}`] }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 评分对话框 -->
    <rating-dialog v-if="selectedMovie && showRatingDialog" v-model="showRatingDialog" :movie="selectedMovie"
      @close="handleRatingDialogClose" @submit="submitRating" />

    <div class="refresh-section" v-if="recommendedMovies.length > 0">
      <el-button type="primary" icon="el-icon-refresh" @click="forceRefresh" :loading="refreshing">
        {{ refreshing ? '刷新中...' : '刷新推荐' }}
      </el-button>
      <p class="refresh-tip">刷新后系统会根据您的最新评分重新生成推荐</p>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import { ElMessage, ElButton } from 'element-plus'
import RatingDialog from '@/components/RatingDialog.vue'
import axios from 'axios'

export default {
  name: 'MovieRecommendations',
  components: {
    RatingDialog,
    ElButton
  },
  setup() {
    const store = useStore()
    const router = useRouter()

    // 响应式数据
    const recommendedMovies = ref([])
    const selectedMovie = ref(null)
    const showRatingDialog = ref(false)
    const refreshing = ref(false)
    const loading = ref(false)

    // 解释相关状态
    const activeTab = ref({})
    const loadingExplanation = ref({})
    const mermaidError = ref({})

    // 解释缓存
    const explanationCache = new Map()

    // 计算属性
    const user = computed(() => store.state.user)
    const isLoggedIn = computed(() => store.getters.isLoggedIn)
    const userId = computed(() => store.getters.userId)

    // 数据格式化函数
    const formatGenres = (genres) => {
      if (!genres) return '未知类型'
      if (Array.isArray(genres)) {
        return genres.join(' / ')
      }
      if (typeof genres === 'string') {
        return genres.split(',').join(' / ')
      }
      return '未知类型'
    }

    const formatActors = (actors) => {
      if (!actors) return '未知'
      if (Array.isArray(actors)) {
        return actors.slice(0, 3).join('、') + (actors.length > 3 ? ' 等' : '')
      }
      if (typeof actors === 'string') {
        const actorList = actors.split(',')
        return actorList.slice(0, 3).join('、') + (actorList.length > 3 ? ' 等' : '')
      }
      return '未知'
    }

    const getTabLabel = (type) => {
      const labels = {
        1: 'Why(abstract)',
        2: 'Why(detailed)',
        3: 'How'
      }
      return labels[type] || `推荐理由 ${type}`
    }

    // 检查是否有有效的解释
    const hasValidExplanation = (movie, type) => {
      const explanation = movie[`explanation${type}`]
      return explanation && explanation !== '无法加载解释内容，请稍后重试。'
    }

    // 主要方法
    const fetchRecommendations = async () => {
      loading.value = true
      try {
        console.log('获取推荐电影，用户ID:', userId.value)

        if (!userId.value) {
          ElMessage.warning('请先登录后再查看推荐')
          router.push('/login')
          return
        }

        const response = await axios.get(`/recommendations/${userId.value}`)
        console.log('推荐接口响应:', response.data)

        // 处理后端返回的数据结构
        recommendedMovies.value = response.data.map(movie => ({
          ...movie,
          // 确保数据类型正确
          user_rating: movie.user_rating !== null && movie.user_rating !== undefined
            ? Number(movie.user_rating)
            : null,
          average_rating: Number(movie.average_rating) || 0,
          rating_count: Number(movie.rating_count) || 0,
          predicted_rating: movie.predicted_rating !== undefined && movie.predicted_rating !== null
            ? Number(movie.predicted_rating)
            : undefined,
          // 处理可能的字段名差异
          year: movie.year || movie.release_year,
          // 确保 genres 和 actors 是数组
          genres: Array.isArray(movie.genres) ? movie.genres :
            (typeof movie.genres === 'string' ? movie.genres.split(',') : []),
          actors: Array.isArray(movie.actors) ? movie.actors :
            (typeof movie.actors === 'string' ? movie.actors.split(',') : [])
        }))

        // 初始化解释状态
        recommendedMovies.value.forEach((_, index) => {
          activeTab.value[index] = 0
          mermaidError.value[index] = false
          loadingExplanation.value[index] = false
        })

      } catch (error) {
        console.error('获取推荐失败:', error)
        const errorMsg = error.response?.data?.error || '获取推荐失败，请稍后重试'
        ElMessage.error(errorMsg)
      } finally {
        loading.value = false
      }
    }

    const toggleExplanation = async (index, type, movie) => {
      // 如果点击的是当前激活的标签，则关闭
      if (activeTab.value[index] === type) {
        activeTab.value[index] = 0
        return
      }

      // 激活新标签
      activeTab.value[index] = type

      // 检查是否已经加载过这个解释
      const hasExplanation = hasValidExplanation(movie, type)

      // 如果解释内容不存在或无效，则加载
      if (!hasExplanation) {
        loadingExplanation.value[index] = true
        try {
          // 调用API获取解释
          const explanation = await getMovieExplanation(type, movie)
          // 存储解释内容
          movie[`explanation${type}`] = explanation

          // 如果是解释3，尝试渲染流程图
          if (type === 3 && explanation) {
            if (isMermaidCode(explanation)) {
              const svg = await renderMermaid(index, explanation)
              if (svg) {
                movie.flowchartSvg = svg
                console.log('✅ 流程图渲染成功')
              } else {
                mermaidError.value[index] = true
              }
            } else {
              movie.flowchartSvg = null
              mermaidError.value[index] = true
            }
          }
        } catch (error) {
          console.error('获取解释失败:', error)
          movie[`explanation${type}`] = '无法加载解释内容，请稍后重试。'
          mermaidError.value[index] = true
        } finally {
          loadingExplanation.value[index] = false
        }
      } else {
        // 如果解释已经存在，但流程图未渲染，则渲染流程图
        if (type === 3 && movie.explanation3 && !movie.flowchartSvg) {
          if (isMermaidCode(movie.explanation3)) {
            loadingExplanation.value[index] = true
            try {
              const svg = await renderMermaid(index, movie.explanation3)
              if (svg) {
                movie.flowchartSvg = svg
                console.log('✅ 延迟渲染流程图成功')
              } else {
                mermaidError.value[index] = true
              }
            } catch (error) {
              console.error('流程图渲染失败:', error)
              mermaidError.value[index] = true
            } finally {
              loadingExplanation.value[index] = false
            }
          }
        }
      }
    }

    // 获取电影解释（带缓存）
    const getMovieExplanation = async (type, movie) => {
      // 创建缓存键
      const cacheKey = `${userId.value}-${movie.id}-${type}`

      // 检查缓存
      if (explanationCache.has(cacheKey)) {
        console.log('📦 从缓存中获取解释')
        return explanationCache.get(cacheKey)
      }

      try {
        const response = await axios.post(`/explanation/${type}`, {
          user_id: userId.value,
          movie_title: movie.title,
          director: movie.director,
          predicted_rating: movie.average_rating
        }, {
          timeout: 120000  // 2分钟超时
        })

        const explanation = response.data.explanation

        // 缓存结果
        explanationCache.set(cacheKey, explanation)
        console.log('💾 解释已缓存')

        return explanation
      } catch (error) {
        console.error('获取解释失败:', error)
      }
    }

    // 简化的Mermaid渲染函数
    const renderMermaid = async (index, mermaidCode) => {
      let tempDiv = null
      try {
        mermaidError.value[index] = false

        console.log('🔄 开始渲染Mermaid图表，索引:', index)
        console.log('原始Mermaid代码:', mermaidCode)

        // 动态导入mermaid库
        const mermaidModule = await import('mermaid')
        const mermaid = mermaidModule.default

        // 初始化mermaid配置
        mermaid.initialize({
          startOnLoad: false,
          theme: 'default',
          securityLevel: 'loose',
          fontFamily: 'Arial, sans-serif'
        })

        // 只做最基本的清理 - 移除HTML标签
        const cleanCode = mermaidCode.replace(/<[^>]*>/g, '').trim()

        const elementId = `mermaid-${index}-${Date.now()}`

        console.log('清理后Mermaid代码:', cleanCode)

        // 创建临时容器
        tempDiv = document.createElement('div')
        tempDiv.id = elementId
        tempDiv.style.display = 'none'
        document.body.appendChild(tempDiv)

        try {
          // 渲染mermaid
          const { svg } = await mermaid.render(elementId, cleanCode)
          console.log('✅ Mermaid渲染成功')
          return svg
        } finally {
          // 清理临时元素
          if (tempDiv && tempDiv.parentNode) {
            document.body.removeChild(tempDiv)
          }
        }
      } catch (error) {
        console.error('❌ Mermaid渲染失败:', error)
        mermaidError.value[index] = true
        return null
      }
    }

    const isMermaidCode = (text) => {
      return text && (
        text.trim().startsWith('graph') ||
        text.trim().startsWith('flowchart') ||
        text.includes('-->') ||
        text.includes('graph TD') ||
        text.includes('graph LR')
      )
    }

    const handleImageError = (event) => {
      event.target.src = '/placeholder-movie.jpg'
    }

    const openRatingDialog = (movie) => {
      if (!isLoggedIn.value) {
        ElMessage.warning('请先登录后再进行评分')
        router.push('/login')
        return
      }

      selectedMovie.value = movie
      showRatingDialog.value = true
    }

    const submitRating = async (ratingValue) => {
      loading.value = true
      try {
        console.log('提交评分:', ratingValue, '电影ID:', selectedMovie.value.id)

        const response = await axios.post('/rate', {
          user_id: userId.value,
          movie_id: selectedMovie.value.id,
          rating: ratingValue
        })

        if (response.data.movie) {
          updateMovieRating(selectedMovie.value.id, response.data.movie)
        }

        // 清除该电影的所有解释缓存
        for (let [key] of explanationCache.entries()) {
          if (key.includes(selectedMovie.value.id)) {
            explanationCache.delete(key)
          }
        }
        console.log('🗑️ 已清除该电影的解释缓存')

        ElMessage.success('评分成功！')
        setTimeout(() => {
          fetchRecommendations()
        }, 1000)

      } catch (error) {
        console.error('评分失败:', error)
        const errorMsg = error.response?.data?.error || '评分失败，请重试'
        ElMessage.error(errorMsg)
      } finally {
        loading.value = false
        showRatingDialog.value = false
      }
    }

    const handleRatingDialogClose = () => {
      showRatingDialog.value = false
      selectedMovie.value = null
    }

    const forceRefresh = async () => {
      refreshing.value = true
      try {
        const timestamp = new Date().getTime()
        const response = await axios.get(`/recommendations/${userId.value}?t=${timestamp}`)

        // 清除解释缓存
        explanationCache.clear()
        console.log('🗑️ 解释缓存已清除')

        recommendedMovies.value = response.data.map(movie => ({
          ...movie,
          user_rating: movie.user_rating !== null && movie.user_rating !== undefined
            ? Number(movie.user_rating)
            : null,
          average_rating: Number(movie.average_rating) || 0,
          rating_count: Number(movie.rating_count) || 0,
          predicted_rating: movie.predicted_rating !== undefined && movie.predicted_rating !== null
            ? Number(movie.predicted_rating)
            : undefined,
          year: movie.year || movie.release_year,
          genres: Array.isArray(movie.genres) ? movie.genres :
            (typeof movie.genres === 'string' ? movie.genres.split(',') : []),
          actors: Array.isArray(movie.actors) ? movie.actors :
            (typeof movie.actors === 'string' ? movie.actors.split(',') : [])
        }))

        // 重置解释状态
        recommendedMovies.value.forEach((_, index) => {
          activeTab.value[index] = 0
          mermaidError.value[index] = false
        })

        ElMessage.success('推荐已刷新')

      } catch (error) {
        console.error('刷新失败:', error)
        const errorMsg = error.response?.data?.error || '刷新失败'
        ElMessage.error(errorMsg)
      } finally {
        refreshing.value = false
      }
    }

    const updateMovieRating = (movieId, updatedMovie) => {
      recommendedMovies.value = recommendedMovies.value.map(movie => {
        if (movie.id === movieId) {
          return {
            ...movie,
            user_rating: updatedMovie.user_rating !== undefined
              ? Number(updatedMovie.user_rating)
              : movie.user_rating,
            average_rating: updatedMovie.average_rating !== undefined
              ? Number(updatedMovie.average_rating)
              : movie.average_rating,
            rating_count: updatedMovie.rating_count !== undefined
              ? Number(updatedMovie.rating_count)
              : movie.rating_count
          }
        }
        return movie
      })
    }

    onMounted(async () => {
      await fetchRecommendations()
    })

    return {
      // 响应式数据
      recommendedMovies,
      selectedMovie,
      showRatingDialog,
      refreshing,
      loading,
      activeTab,
      loadingExplanation,
      mermaidError,

      // 计算属性
      user,
      isLoggedIn,
      userId,

      // 方法
      formatGenres,
      formatActors,
      getTabLabel,
      hasValidExplanation,
      fetchRecommendations,
      toggleExplanation,
      handleImageError,
      openRatingDialog,
      submitRating,
      handleRatingDialogClose,
      forceRefresh
    }
  }
}
</script>

<style scoped>
.recommendation-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background-color: #f8f9fa;
  min-height: 100vh;
}

.header {
  text-align: center;
  margin: 30px 0 40px;
}

.header h1 {
  font-size: 32px;
  font-weight: 700;
  color: #2c3e50;
  margin-bottom: 10px;
}

.subtitle {
  font-size: 16px;
  color: #7f8c8d;
  margin: 0;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: #7f8c8d;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 5px solid #e0e0e0;
  border-top: 5px solid #3498db;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.recommendations-container {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.movie-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
  overflow: hidden;
  display: flex;
  border: 1px solid #eaeaea;
}

.movie-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.12);
}

/* 预测评分样式 */
.predicted-rating-section {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ecf0f1;
}

.predicted-rating-display {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #7f8c8d;
  margin-bottom: 8px;
}

.predicted-stars {
  display: flex;
}

.predicted-star {
  color: #ddd;
  font-size: 16px;
  transition: color 0.2s ease;
}

.predicted-star.filled {
  color: #3498db; /* 使用蓝色区别于用户评分的金色 */
}

.predicted-rating-value {
  font-weight: bold;
  color: #3498db;
  margin-left: 5px;
}

.prediction-explanation {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: #95a5a6;
  background-color: #f8f9fa;
  padding: 8px 10px;
  border-radius: 4px;
  border-left: 3px solid #3498db;
  line-height: 1.4;
}

.prediction-explanation i {
  margin-top: 1px;
  flex-shrink: 0;
}

.movie-image-container {
  flex: 0 0 200px;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f8f9fa;
}

.movie-image {
  width: 160px;
  height: 220px;
  object-fit: cover;
  border-radius: 6px;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease;
}

.movie-card:hover .movie-image {
  transform: scale(1.03);
}

.movie-content {
  flex: 1;
  padding: 25px;
  display: flex;
  flex-direction: column;
}

.movie-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 15px;
}

.movie-title {
  font-size: 22px;
  font-weight: 700;
  color: #2c3e50;
  margin: 0;
  line-height: 1.3;
  flex: 1;
  padding-right: 20px;
}

.movie-rating {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #f8f9fa;
  padding: 8px 12px;
  border-radius: 8px;
  min-width: 80px;
}

.rating-value {
  font-weight: bold;
  color: #e74c3c;
  font-size: 18px;
  margin-bottom: 4px;
}

.stars {
  display: flex;
}

.star {
  color: #ddd;
  font-size: 16px;
}

.star.filled {
  color: #f39c12;
}

.movie-meta {
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ecf0f1;
}

.movie-meta p {
  margin: 5px 0;
  color: #555;
  font-size: 15px;
}

.movie-meta strong {
  color: #7f8c8d;
  font-weight: 600;
}

.user-rating-section {
  margin-bottom: 20px;
}

.user-rating-display {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #7f8c8d;
}

.user-stars {
  display: flex;
}

.user-rating-value {
  font-weight: bold;
  color: #e74c3c;
  margin-left: 5px;
}

.rate-button {
  margin-top: 10px;
}

.explanation-section {
  margin-top: auto;
}

.explanation-tabs {
  display: flex;
  border-radius: 8px;
  background: #f8f9fa;
  padding: 4px;
  margin-bottom: 15px;
}

.explanation-tab {
  flex: 1;
  padding: 10px 12px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
  color: #7f8c8d;
}

.explanation-tab.active {
  background: white;
  color: #3498db;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.explanation-tab:hover:not(.active) {
  background: rgba(52, 152, 219, 0.1);
  color: #2980b9;
}

.explanation-content {
  min-height: 80px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  border-left: 3px solid #3498db;
}

.explanation-placeholder {
  color: #bdc3c7;
  font-style: italic;
  text-align: center;
  padding: 20px 0;
}

.explanation-loading {
  color: #7f8c8d;
  text-align: center;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.loading-dots {
  display: flex;
  margin-bottom: 10px;
}

.loading-dots span {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3498db;
  margin: 0 3px;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {

  0%,
  80%,
  100% {
    transform: scale(0);
  }

  40% {
    transform: scale(1);
  }
}

.explanation-text {
  color: #2c3e50;
  line-height: 1.6;
  font-size: 15px;
}

.mermaid-container {
  width: 100%;
  overflow-x: auto;
  text-align: center;
  background: white;
  border-radius: 6px;
  padding: 10px;
  border: 1px solid #eaeaea;
}

.mermaid-chart {
  display: flex;
  justify-content: center;
  min-height: 200px;
}

.mermaid-chart :deep(svg) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
}

.mermaid-error {
  color: #e74c3c;
  text-align: center;
  padding: 20px;
  background: #fef5f5;
  border-radius: 6px;
  border-left: 3px solid #e74c3c;
}

.error-title {
  font-weight: bold;
  margin-bottom: 10px;
  color: #c0392b;
}

.mermaid-text {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 6px;
  overflow-x: auto;
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.4;
  color: #2c3e50;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Courier New', monospace;
  max-height: 300px;
  overflow-y: auto;
}

.refresh-section {
  text-align: center;
  margin-top: 40px;
  padding: 20px 0;
  border-top: 1px solid #f0f0f0;
}

.refresh-tip {
  margin-top: 10px;
  font-size: 14px;
  color: #909399;
}

@media (max-width: 768px) {
  .movie-card {
    flex-direction: column;
  }

  .movie-image-container {
    flex: 0 0 auto;
    padding: 20px 20px 0;
  }

  .movie-image {
    width: 140px;
    height: 190px;
  }

  .movie-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .movie-rating {
    margin-top: 10px;
    flex-direction: row;
    align-self: flex-start;
    gap: 10px;
  }

  .movie-title {
    padding-right: 0;
  }

  .mermaid-container {
    font-size: 12px;
  }
}

@media (max-width: 480px) {
  .recommendation-page {
    padding: 15px;
  }

  .movie-content {
    padding: 20px;
  }

  .explanation-tabs {
    flex-direction: column;
    gap: 5px;
  }
}
</style>