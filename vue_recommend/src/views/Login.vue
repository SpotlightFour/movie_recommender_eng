<template>
  <div class="login">
    <h2>登录</h2>
    <el-form :model="form" label-width="80px">
      <el-form-item label="用户名">
        <el-input v-model="form.username" placeholder="请输入用户名"></el-input>
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" placeholder="请输入密码"></el-input>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleLogin">登录</el-button>
        <el-button @click="goToRegister">注册</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { mapActions } from 'vuex'
import { ElMessage } from 'element-plus';

export default {
  data() {
    return {
      form: {
        username: '',
        password: ''
      }
    }
  },
  methods: {
    ...mapActions(['login']),
    async handleLogin() {
      try {
        // 显示加载状态
        const loading = this.$loading({
          lock: true,
          text: '登录中...',
          spinner: 'el-icon-loading',
          background: 'rgba(0, 0, 0, 0.7)'
        })
        
        // 等待登录操作完成并获取用户信息
        const user = await this.login(this.form)
        
        // 关闭加载状态
        loading.close()
        
        // 使用真实的用户ID
        console.log('登录成功，用户ID:', user.id)
        
        ElMessage.success('登录成功')
        this.$router.push('/')
      } catch (error) {
        ElMessage.error(error.message)
        console.error('登录错误详情:', error)
      }
    },
    goToRegister() {
      this.$router.push('/register')
    }
  }
}
</script>

<style scoped>
.login {
  max-width: 500px;
  margin: 0 auto;
  padding: 20px;
}
</style>