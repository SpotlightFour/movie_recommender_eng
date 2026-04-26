<template>
  <div id="app">
    <el-container class="app-container">
      <!-- 优化后的头部导航 -->
      <el-header class="app-header">
        <div class="header-content">
          <div class="logo">
            <i class="el-icon-film"></i>
            <span>电影推荐系统</span>
          </div>
          <el-menu 
            mode="horizontal" 
            router
            :default-active="$route.path"
            class="nav-menu"
          >
            <el-menu-item index="/">
              <i class="el-icon-s-home"></i>
              <span>首页</span>
            </el-menu-item>
            <el-menu-item index="/preferences" v-if="isLoggedIn">
              <i class="el-icon-setting"></i>
              <span>偏好设置</span>
            </el-menu-item>
            <el-menu-item index="/recommendations" v-if="isLoggedIn">
              <i class="el-icon-star"></i>
              <span>我的推荐</span>
            </el-menu-item>
            <el-menu-item index="/profile" v-if="isLoggedIn">
              <i class="el-icon-user"></i>
              <span>我的画像</span>
            </el-menu-item>
            <el-menu-item index="/login" v-if="!isLoggedIn">
              <i class="el-icon-user"></i>
              <span>登录</span>
            </el-menu-item>
            <el-menu-item index="/register" v-if="!isLoggedIn">
              <i class="el-icon-edit"></i>
              <span>注册</span>
            </el-menu-item>
            <el-menu-item v-if="isLoggedIn" @click="logout" class="logout-btn">
              <i class="el-icon-switch-button"></i>
              <span>退出</span>
            </el-menu-item>
          </el-menu>
          <div class="user-info" v-if="isLoggedIn">
            <el-avatar :size="40" :src="userAvatar" class="user-avatar"></el-avatar>
            <span class="username">{{ user.username }}</span>
          </div>
        </div>
      </el-header>
      
      <!-- 主要内容区域 -->
      <el-main class="app-main">
        <div class="content-container">
          <router-view />
        </div>
      </el-main>
      
      <!-- 新增页脚 -->
      <el-footer class="app-footer">
        <div class="footer-content">
          <div class="footer-links">
            <a href="#">关于我们</a>
            <a href="#">帮助中心</a>
            <a href="#">隐私政策</a>
            <a href="#">联系我们</a>
          </div>
          <div class="copyright">
            © 2025 电影推荐系统 | 基于 Vue.js 和 Flask 开发
          </div>
        </div>
      </el-footer>
    </el-container>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import { ElMessage } from 'element-plus';

export default {
  computed: {
    ...mapState(['user']),
    isLoggedIn() {
      return this.user !== null
    },
    userAvatar() {
      // 根据用户名生成头像（实际应用中应从用户数据获取）
      return `https://ui-avatars.com/api/?name=${this.user?.username || 'User'}&background=409EFF&color=fff`
    }
  },
  methods: {
    logout() {
      this.$store.dispatch('logout')
      this.$router.push('/')
      ElMessage.success('您已成功退出系统')
    }
  }
}
</script>

<style>
/* 全局样式优化 */
#app {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 
               'Microsoft YaHei', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
}

.app-container {
  min-height: 100vh;
}

/* 头部样式优化 */
.app-header {
  background: linear-gradient(135deg, #1a365d, #2c5282);
  color: white;
  height: 70px !important;
  padding: 0 20px !important;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
  position: sticky;
  top: 0;
  z-index: 1000;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
}

.logo {
  display: flex;
  align-items: center;
  font-size: 22px;
  font-weight: 700;
  color: white;
}

.logo i {
  font-size: 28px;
  margin-right: 10px;
  color: #ffd04b;
}

.nav-menu {
  flex: 1;
  margin: 0 30px;
  border-bottom: none !important;
  background-color: transparent !important;
}

.nav-menu .el-menu-item {
  height: 70px;
  line-height: 70px;
  font-size: 16px;
  padding: 0 20px !important;
  margin: 0 5px;
  border-radius: 4px;
  transition: all 0.3s ease;
  color: #e2e8f0 !important;
}

.nav-menu .el-menu-item:hover {
  background-color: rgba(255, 255, 255, 0.15) !important;
}

.nav-menu .el-menu-item.is-active {
  background-color: rgba(255, 208, 75, 0.15) !important;
  color: #ffd04b !important;
  font-weight: 500;
}

.nav-menu .el-menu-item i {
  margin-right: 8px;
  font-size: 18px;
}

.nav-menu .logout-btn:hover {
  background-color: rgba(255, 90, 90, 0.2) !important;
  color: #ff6b6b !important;
}

.user-info {
  display: flex;
  align-items: center;
}

.user-avatar {
  margin-right: 10px;
  border: 2px solid rgba(255, 255, 255, 0.5);
}

.username {
  font-size: 16px;
  font-weight: 500;
}

/* 主要内容区域优化 */
.app-main {
  padding: 30px 20px !important;
  flex: 1;
}

.content-container {
  max-width: 1200px;
  margin: 0 auto;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  padding: 30px;
  min-height: calc(100vh - 140px);
}

/* 页脚样式 */
.app-footer {
  background: #1a365d;
  color: white;
  padding: 20px 0 !important;
  text-align: center;
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.footer-links {
  display: flex;
  justify-content: center;
  margin-bottom: 15px;
}

.footer-links a {
  color: #cbd5e0;
  margin: 0 15px;
  text-decoration: none;
  transition: all 0.3s ease;
}

.footer-links a:hover {
  color: white;
  text-decoration: underline;
}

.copyright {
  color: #a0aec0;
  font-size: 14px;
}

/* 响应式设计 */
@media (max-width: 992px) {
  .header-content {
    flex-direction: column;
    height: auto;
    padding: 10px 0;
  }
  
  .logo {
    margin-bottom: 10px;
  }
  
  .nav-menu {
    margin: 10px 0;
    width: 100%;
  }
  
  .nav-menu .el-menu-item {
    height: 50px;
    line-height: 50px;
    font-size: 14px;
    padding: 0 10px !important;
  }
  
  .user-info {
    margin-top: 10px;
  }
}

@media (max-width: 768px) {
  .nav-menu .el-menu-item {
    font-size: 13px;
    padding: 0 8px !important;
    margin: 0 2px;
  }
  
  .nav-menu .el-menu-item span {
    display: none;
  }
  
  .nav-menu .el-menu-item i {
    margin-right: 0;
    font-size: 16px;
  }
  
  .content-container {
    padding: 20px 15px;
  }
}

@media (max-width: 480px) {
  .footer-links {
    flex-wrap: wrap;
  }
  
  .footer-links a {
    margin: 5px 10px;
  }
}
</style>