<template>
  <div class="register">
    <h2>注册</h2>
    <el-form :model="form" label-width="100px">
      <el-form-item label="用户名">
        <el-input v-model="form.username" placeholder="请输入用户名"></el-input>
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="form.password" type="password" placeholder="请输入密码"></el-input>
      </el-form-item>
      <el-form-item label="确认密码">
        <el-input v-model="form.confirmPassword" type="password" placeholder="请再次输入密码"></el-input>
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="form.email" placeholder="请输入邮箱"></el-input>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleRegister">注册</el-button>
        <el-button @click="goToLogin">返回登录</el-button>
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
        password: '',
        confirmPassword: '',
        email: ''
      }
    }
  },
  methods: {
    ...mapActions(['register']),
    async handleRegister() {
      if (this.form.password !== this.form.confirmPassword) {
        ElMessage.error('两次输入的密码不一致')
        return
      }
      
      try {
        await this.register({
          username: this.form.username,
          password: this.form.password,
          email: this.form.email
        })
        ElMessage.success('注册成功')
        this.$router.push('/')
      } catch (error) {
        ElMessage.error('注册失败：' + (error.response?.data?.error || '未知错误'))
      }
    },
    goToLogin() {
      this.$router.push('/login')
    }
  }
}
</script>

<style scoped>
.register {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}
</style>