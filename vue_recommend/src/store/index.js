import { createStore } from 'vuex'
import axios from 'axios'  // ✅ 添加 axios 导入

// 配置 axios 基地址
axios.defaults.baseURL = 'http://localhost:5000'

export default createStore({
  state: {
    user: null,
    loading: false,
    error: null
  },
  mutations: {
    setUser(state, user) {
      state.user = user
    },
    setLoading(state, loading) {
      state.loading = loading
    },
    setError(state, error) {
      state.error = error
    }
  },
  actions: {
    async login({ commit }, credentials) {
      try {
        commit('setLoading', true)
        commit('setError', null)
        
        console.log('🔐 尝试登录:', credentials.username)
        
        // ✅ 调用后端登录API
        const response = await axios.post('/login', credentials)
        
        if (response.data && response.data.user_id) {
          const user = {
            id: response.data.user_id,
            username: response.data.username,
            email: response.data.email || `${credentials.username}@example.com`
          }
          
          commit('setUser', user)
          localStorage.setItem('user', JSON.stringify(user))
          
          console.log('✅ 登录成功，用户ID:', user.id)
          return user
        } else {
          throw new Error('登录响应数据不完整')
        }
      } catch (error) {
        // ✅ 详细的错误处理
        let errorMessage = '登录失败'
        
        if (error.response) {
          // 服务器返回了错误状态码
          errorMessage = error.response.data?.error || `服务器错误: ${error.response.status}`
          console.error('❌ 服务器错误:', error.response.data)
        } else if (error.request) {
          // 请求已发出但没有收到响应
          errorMessage = '无法连接到服务器，请检查后端服务是否运行'
          console.error('❌ 网络错误:', error.message)
        } else {
          // 其他错误
          errorMessage = error.message
          console.error('❌ 其他错误:', error.message)
        }
        
        commit('setError', errorMessage)
        throw new Error(errorMessage)
      } finally {
        commit('setLoading', false)
      }
    },
    
    logout({ commit }) {
      commit('setUser', null)
      localStorage.removeItem('user')
      commit('setError', null)
    },
    
    initializeStore({ commit }) {
      const userJson = localStorage.getItem('user')
      if (userJson) {
        try {
          const user = JSON.parse(userJson)
          commit('setUser', user)
          console.log('🔄 从本地存储恢复用户:', user.username)
        } catch (error) {
          console.error('❌ 解析用户信息失败:', error)
          localStorage.removeItem('user')
        }
      }
    }
  },
  getters: {
    isLoggedIn: state => state.user !== null,
    userId: state => state.user?.id || null,
    username: state => state.user?.username || '',
    isLoading: state => state.loading,
    error: state => state.error
  }
})