<template>
  <el-dialog :title="'为 ' + movie.title + ' 评分'" :visible="visible" @close="$emit('close')" width="30%">
    <el-rate v-model="rating" :colors="colors" :max="5" show-score score-template="{value} 分" />
    <span slot="footer" class="dialog-footer">
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="primary" @click="submitRating">提交</el-button>
    </span>
  </el-dialog>
</template>

<script>
export default {
  props: {
    visible: Boolean,
    movie: Object
  },
  data() {
    return {
      rating: 5,
      colors: ['#99A9BF', '#F7BA2A', '#FF9900']
    }
  },
  methods: {
    submitRating() {
      this.$emit('submit', this.rating)
    }
  }
}
</script>