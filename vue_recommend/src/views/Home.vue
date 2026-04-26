<template>
  <div class="home">
    <h2>电影推荐系统</h2>

    <!-- 用户未登录时的显示 -->
    <div v-if="!isLoggedIn" class="welcome-section">
      <el-alert title="欢迎使用电影推荐系统" type="info" show-icon>
        请先登录或注册以获取个性化推荐
      </el-alert>
      <div class="action-buttons">
        <el-button type="primary" @click="goToLogin">登录</el-button>
        <el-button type="success" @click="goToRegister">注册</el-button>
      </div>
    </div>

    <!-- 用户已登录时的显示 -->
    <div v-else>
      <!-- 热门电影展示 -->
      <div class="section">
        <h3>热门电影</h3>
        <el-row :gutter="20">
          <el-col :span="6" v-for="movie in popularMovies" :key="movie.id">
            <movie-card :movie="movie" @rate="handleRateMovie" @rating-submitted="handleRatingSubmitted" />
          </el-col>
        </el-row>
      </div>

      <!-- 快速操作 -->
      <div class="quick-actions">
        <el-button type="primary" @click="goToPreferences">
          <i class="el-icon-setting"></i> 设置偏好
        </el-button>
        <el-button type="success" @click="goToRecommendations">
          <i class="el-icon-star"></i> 查看推荐
        </el-button>
        <el-button type="info" @click="goToProfile">
          <i class="el-icon-user"></i> 我的画像
        </el-button>
      </div>

      <!-- 添加 RatingDialog 组件 -->
      <rating-dialog v-if="showRatingDialog" v-model="showRatingDialog" :movie="currentMovie"
        @close="showRatingDialog = false" @submit="handleRatingSubmit" />
    </div>
  </div>
</template>

<script>
import { mapState, mapGetters } from 'vuex'
import MovieCard from '@/components/MovieCard.vue'
import RatingDialog from '@/components/RatingDialog.vue' // 引入 RatingDialog 组件
import { ElMessage } from 'element-plus'

export default {
  name: 'Home',
  components: {
    MovieCard,
    RatingDialog // 注册 RatingDialog 组件
  },
  data() {
    return {
      popularMovies: [],
      loading: false,
      showRatingDialog: false, // 控制评分对话框显示
      currentMovie: null       // 当前评分的电影
    }
  },
  computed: {
    ...mapState(['user']),
    ...mapGetters(['isLoggedIn'])
  },
  async created() {
    await this.loadPopularMovies()
  },
  methods: {
    async loadPopularMovies() {
      this.loading = true
      try {
        const params = { limit: 8 }
        if (this.user) {
          params.user_id = this.user.id
        }
        const response = await this.$http.get('/movies', { params })
        this.popularMovies = response.data.map(movie => ({
          ...movie,
          user_rating: movie.user_rating,
          average_rating: movie.average_rating || 0,
          rating_count: movie.rating_count || 0
        }))
      } catch (error) {
        console.error('加载热门电影失败:', error)
        ElMessage.error('加载电影数据失败')
      } finally {
        this.loading = false
      }
    },

    handleRateMovie(movie) {
      if (!this.isLoggedIn) {
        ElMessage.warning('请先登录后再进行评分')
        this.$router.push('/login')
        return
      }

      // 设置当前电影并打开评分对话框
      this.currentMovie = movie
      this.showRatingDialog = true
    },

    // 处理评分提交
    async handleRatingSubmit(ratingValue) {
      try {
        this.loading = true;
        // 提交评分到后端
        const response = await this.$http.post('/rate', {
          user_id: this.user.id,
          movie_id: this.currentMovie.id,
          rating: ratingValue
        });

        // 使用后端返回的完整电影数据更新本地数据
        if (response.data.movie) {
          this.updateMovieRating(this.currentMovie.id, response.data.movie);
        } else {
          // 如果后端没有返回电影数据，手动更新
          this.updateMovieRating(this.currentMovie.id, {
            user_rating: ratingValue,
            average_rating: this.calculateNewAverage(this.currentMovie, ratingValue),
            rating_count: this.currentMovie.rating_count + 1
          });
        }

        ElMessage.success('评分成功！')
      } catch (error) {
        console.error('评分失败:', error);
        ElMessage.error('评分失败，请重试')
      } finally {
        this.loading = false;
        this.showRatingDialog = false;
      }
    },

    handleRatingSubmitted({ movieId, rating }) {
      this.updateMovieRating(movieId, rating)
    },

    goToLogin() {
      this.$router.push('/login')
    },

    goToRegister() {
      this.$router.push('/register')
    },

    goToPreferences() {
      this.$router.push('/preferences')
    },

    goToRecommendations() {
      this.$router.push('/recommendations')
    },

    goToProfile() {
      this.$router.push('/profile')
    },

    updateMovieRating(movieId, updatedMovie) {
      this.popularMovies = this.popularMovies.map(movie =>
        movie.id === movieId ? {
          ...movie,
          user_rating: updatedMovie.user_rating || updatedMovie.userRating,
          average_rating: updatedMovie.average_rating,
          rating_count: updatedMovie.rating_count
        } : movie
      )
    },

    calculateNewAverage(movie, newRating) {
      const currentRating = movie.average_rating || 0
      const currentCount = movie.rating_count || 0

      const currentTotal = currentRating * currentCount
      const newTotal = currentTotal + newRating
      const newCount = currentCount + 1

      return Math.round((newTotal / newCount) * 10) / 10
    }
  }
}
</script>

<style scoped>
.home {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-section {
  text-align: center;
  padding: 40px 20px;
}

.action-buttons {
  margin-top: 20px;
}

.action-buttons .el-button {
  margin: 0 10px;
}

.section {
  margin: 30px 0;
}

.section h3 {
  margin-bottom: 20px;
  color: #303133;
  border-left: 4px solid #409EFF;
  padding-left: 10px;
}

.quick-actions {
  margin-top: 30px;
  text-align: center;
}

.quick-actions .el-button {
  margin: 0 10px;
  padding: 12px 24px;
}
</style>