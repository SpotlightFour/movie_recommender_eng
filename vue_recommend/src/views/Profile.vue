<template>
  <div class="user-profile">
    <h2>My Profile</h2>

    <!-- Add global explanation area -->
    <el-alert 
      title="Preference Score Explanation" 
      type="info" 
      :closable="false"
      class="explanation-alert"
    >
      <div class="explanation-content">
        <p>Preference scores reflect your preference level for different movie genres, directors, and actors:</p>
        <ul>
          <li><el-tag type="success">Very High (80%-100%)</el-tag>: You have a strong liking for this element</li>
          <li><el-tag type="primary">High (60%-80%)</el-tag>: You have a high interest in this element</li>
          <li><el-tag type="warning">Medium (40%-60%)</el-tag>: You have moderate interest in this element</li>
          <li><el-tag type="info">Low (20%-40%)</el-tag>: You have low interest in this element</li>
          <li><el-tag type="danger">Very Low (0%-20%)</el-tag>: You have very low interest in this element</li>
        </ul>
        <p>Scores are calculated based on your historical ratings, viewing behavior, and preference settings.</p>
      </div>
    </el-alert>

    <el-card class="profile-card" v-loading="loading">
      <h3>Preference Analysis</h3>

      <div class="preference-section">
        <h4>Favorite Genres</h4>
        <div class="genres" v-if="Object.keys(profile.favorite_genres).length">
          <el-tooltip 
            v-for="(score, genre) in profile.favorite_genres" 
            :key="genre" 
            effect="light" 
            placement="top"
          >
            <template #content>
              <div class="tooltip-content">
                <p>Your preference for <span class="highlight">{{ genre }}</span> is <span class="highlight">{{ (score * 20).toFixed(0) }}%</span></p>
                <p v-if="score > 4">You have a strong liking for this genre, the system will prioritize recommending related movies</p>
                <p v-else-if="score > 3">You have high interest in this genre</p>
                <p v-else-if="score > 2">You have moderate interest in this genre</p>
                <p v-else-if="score > 1">You have low interest in this genre</p>
                <p v-else>You have very low interest in this genre</p>
              </div>
            </template>
            <el-tag :type="getTagType(score)">
              {{ genre }} ({{ (score * 20).toFixed(0) }}%)
            </el-tag>
          </el-tooltip>
        </div>
        <p v-else class="no-data">No data</p>
      </div>

      <div class="preference-section">
        <h4>Favorite Directors</h4>
        <div class="directors" v-if="Object.keys(profile.preferred_directors).length">
          <el-tooltip 
            v-for="(score, director) in profile.preferred_directors" 
            :key="director" 
            effect="light" 
            placement="top"
          >
            <template #content>
              <div class="tooltip-content">
                <p>Your preference for director <span class="highlight">{{ director }}</span> is <span class="highlight">{{ (score * 20).toFixed(0) }}%</span></p>
                <p v-if="score > 4">You have a strong liking for this director's works</p>
                <p v-else-if="score > 3">You have high interest in this director's works</p>
                <p v-else-if="score > 2">You have moderate interest in this director's works</p>
                <p v-else-if="score > 1">You have low interest in this director's works</p>
                <p v-else>You have very low interest in this director's works</p>
              </div>
            </template>
            <el-tag :type="getTagType(score)">
              {{ director }} ({{ (score * 20).toFixed(0) }}%)
            </el-tag>
          </el-tooltip>
        </div>
        <p v-else class="no-data">No data</p>
      </div>

      <div class="preference-section">
        <h4>Favorite Actors</h4>
        <div class="actors" v-if="Object.keys(profile.preferred_actors).length">
          <el-tooltip 
            v-for="(score, actor) in profile.preferred_actors" 
            :key="actor" 
            effect="light" 
            placement="top"
          >
            <template #content>
              <div class="tooltip-content">
                <p>Your preference for actor <span class="highlight">{{ actor }}</span> is <span class="highlight">{{ (score * 20).toFixed(0) }}%</span></p>
                <p v-if="score > 4">You have a strong liking for movies starring this actor</p>
                <p v-else-if="score > 3">You have high interest in movies starring this actor</p>
                <p v-else-if="score > 2">You have moderate interest in movies starring this actor</p>
                <p v-else-if="score > 1">You have low interest in movies starring this actor</p>
                <p v-else>You have very low interest in movies starring this actor</p>
              </div>
            </template>
            <el-tag :type="getTagType(score)">
              {{ actor }} ({{ (score * 20).toFixed(0) }}%)
            </el-tag>
          </el-tooltip>
        </div>
        <p v-else class="no-data">No data</p>
      </div>

      <div class="preference-section">
        <h4>Viewing Time Pattern</h4>
        <el-tooltip effect="light" placement="top">
          <template #content>
            <p>Your preferred viewing time pattern analyzed from your viewing history</p>
          </template>
          <p>{{ profile.watch_time_pattern ? watchTimeLabels[profile.watch_time_pattern] : 'No data' }}</p>
        </el-tooltip>
      </div>

      <div class="preference-section">
        <h4>Preferred Decades</h4>
        <el-tooltip effect="light" placement="top">
          <template #content>
            <p>Your preferred decades analyzed from the movies you rated</p>
          </template>
          <p>{{ profile.preferred_decade || 'No data' }}</p>
        </el-tooltip>
      </div>
    </el-card>

    <el-button type="primary" @click="updateProfile" :loading="updating">
      {{ updating ? 'Updating...' : 'Update Profile' }}
    </el-button>
    
    <!-- Add update explanation -->
    <el-alert 
      v-if="updating" 
      title="Update Explanation" 
      type="info" 
      :closable="false"
      class="update-explanation"
    >
      <p>Updating the user profile may take some time. The system will re-analyze your:</p>
      <ul>
        <li>Preference settings</li>
        <li>Rating history</li>
        <li>Viewing behavior</li>
      </ul>
      <p>The latest preference analysis results will be displayed upon completion</p>
    </el-alert>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import { ElMessage } from 'element-plus'

export default {
  data() {
    return {
      profile: {
        favorite_genres: {},
        preferred_directors: {},
        preferred_actors: {},
        watch_time_pattern: '',
        preferred_decade: ''
      },
      watchTimeLabels: {
        'weekday_evening': 'Weekday Evenings',
        'weekday_afternoon': 'Weekday Afternoons',
        'weekday_morning': 'Weekday Mornings',
        'weekend_evening': 'Weekend Evenings',
        'weekend_afternoon': 'Weekend Afternoons',
        'weekend_morning': 'Weekend Mornings'
      },
      loading: false,
      updating: false
    }
  },
  computed: {
    ...mapState(['user'])
  },
  async mounted() {
    await this.fetchProfile()
  },
  methods: {
    async fetchProfile() {
      this.loading = true
      try {
        const response = await this.$http.get(`/profile/${this.user.id}`)
        this.profile = response.data
      } catch (error) {
        ElMessage.error('Failed to get user profile')
        console.error('Failed to get profile:', error)
      } finally {
        this.loading = false
      }
    },
    async updateProfile() {
      this.updating = true
      try {
        await this.$http.post(`/profile/update/${this.user.id}`)
        ElMessage.success('User profile updated successfully')
        await this.fetchProfile() // Refresh data
      } catch (error) {
        ElMessage.error('Failed to update user profile')
        console.error('Failed to update profile:', error)
      } finally {
        this.updating = false
      }
    },
    getTagType(score) {
      if (score > 4) return 'success'      // 80%-100%: Very High
      if (score > 3) return 'primary'     // 60%-80%: High
      if (score > 2) return 'warning'     // 40%-60%: Medium
      if (score > 1) return 'info'        // 20%-40%: Low
      return 'danger'                      // 0%-20%: Very Low
    }
  }
}
</script>

<style scoped>
.user-profile {
  padding: 20px;
}

.explanation-alert {
  margin-bottom: 20px;
  text-align: left;
}

.explanation-content {
  padding: 10px;
}

.explanation-content ul {
  padding-left: 20px;
  margin: 10px 0;
}

.explanation-content li {
  margin-bottom: 5px;
}

.profile-card {
  margin: 20px 0;
  padding: 20px;
}

.preference-section {
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #f0f0f0;
}

.preference-section:last-child {
  border-bottom: none;
}

.genres,
.directors,
.actors {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.no-data {
  color: #999;
  font-style: italic;
}

/* Tooltip content style */
.tooltip-content {
  text-align: center;
  padding: 5px;
}

.highlight {
  color: #409EFF;
  font-weight: bold;
  margin: 0 3px;
}

.update-explanation {
  margin-top: 20px;
}
</style>