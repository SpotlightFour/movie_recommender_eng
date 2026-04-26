import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import store from './store'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import axios from 'axios'

// 配置axios基础URL
axios.defaults.baseURL = 'http://localhost:5000'
axios.defaults.timeout = 60000  // 增加到60秒
axios.defaults.withCredentials = false

// 请求拦截器
axios.interceptors.request.use(
  config => {
    console.log(`🔄 发送请求: ${config.method?.toUpperCase()} ${config.url}`)
    return config
  },
  error => {
    console.error('❌ 请求配置错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器 - 增强错误处理
axios.interceptors.response.use(
  response => {
    console.log(`✅ 请求成功: ${response.config.url}`, response.status)
    return response
  },
  error => {
    if (error.code === 'ECONNABORTED') {
      console.error('⏰ 请求超时:', error.config.url)
      error.message = '请求超时，后端处理时间较长，请稍后重试'
    } else if (error.response) {
      // 服务器返回错误状态码
      console.error('❌ 服务器错误:', error.response.status, error.response.data)
      switch (error.response.status) {
        case 401:
          store.dispatch('logout')
          router.push('/login')
          error.message = '未授权，请重新登录'
          break
        case 404:
          error.message = 'API端点未找到'
          break
        case 500:
          error.message = '服务器内部错误'
          break
        default:
          error.message = `请求错误: ${error.response.status}`
      }
    } else if (error.request) {
      // 请求已发出但没有收到响应
      console.error('🌐 网络错误: 无法连接到服务器')
      error.message = '无法连接到服务器，请检查后端服务状态'
    } else {
      // 其他错误
      console.error('❌ 请求配置错误:', error.message)
      error.message = `请求配置错误: ${error.message}`
    }

    // 显示错误提示
    if (error.config?.url !== '/login') {
      const { ElMessage } = ElementPlus
      ElMessage.error(error.message)
    }

    return Promise.reject(error)
  }
)

const app = createApp(App)

app.use(router)
app.use(store)
app.use(ElementPlus)

// 将axios挂载到Vue实例
app.config.globalProperties.$http = axios
app.config.globalProperties.$message = ElementPlus.ElMessage

// 初始化store
store.dispatch('initializeStore')

app.mount('#app')

console.log('🚀 Vue应用已启动，axios配置完成')