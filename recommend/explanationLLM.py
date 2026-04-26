import os

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# 加载本地模型
try:
    # 正确的模型目录路径（指向包含所有文件的文件夹）
    model_dir = "./qwen_models"  # 根据实际下载路径调整

    # 检查模型文件是否存在
    if not os.path.exists(model_dir):
        print(f"模型目录不存在: {model_dir}")
        text_generator = None
    else:
        print(f"从目录加载模型: {model_dir}")

        # 加载tokenizer和模型
        tokenizer = AutoTokenizer.from_pretrained(
            model_dir,
            trust_remote_code=True
        )

        model = AutoModelForCausalLM.from_pretrained(
            model_dir,
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=True
        )

        # 创建文本生成管道 - 使用text-generation
        text_generator = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            device=0 if torch.cuda.is_available() else -1,
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            # 设置tokens限制
            max_new_tokens=200,  # 最大生成token数
            min_new_tokens=10,  # 最小生成token数
            do_sample=True,  # 启用采样
            temperature=0.7,  # 采样温度
            top_p=0.9,  # 核采样参数
        )

        print("本地模型加载成功")

except Exception as e:
    print(f"加载本地模型失败: {str(e)}")
    text_generator = None


class ExplanationLLM:
    def generate_explanation(self, prompt_pre):
        """使用本地模型生成推荐解释"""
        if not text_generator:
            return "我们根据您的观影偏好为您推荐了这部电影"

        try:
            # 构建更自然的提示
            prompt = f"请用简洁自然的中文解释为什么推荐这部电影：{prompt_pre}"

            # 生成解释
            results = text_generator(
                prompt,
                max_new_tokens=200,
                num_return_sequences=1,
                no_repeat_ngram_size=2
            )

            # 提取生成的文本
            generated_text = results[0]['generated_text']

            # 移除提示部分，只保留解释
            explanation = generated_text.replace(prompt, "").strip()

            # 优化生成的文本
            if explanation.startswith("因为"):
                explanation = explanation[2:]
            if explanation and not explanation.endswith(("。", "！", "？")):
                explanation += "。"

            return explanation if explanation else "这部电影与您之前的观影兴趣相符"
        except Exception as e:
            print(f"生成解释时出错: {str(e)}")
            return "这部电影是根据您的观影偏好推荐的"

    def convert_steps_to_mermaid(self, user_id, movie_title, predicted_rating, step_description):
        """
        将步骤描述转换为mermaid代码
        """
        # 解析步骤
        steps = []
        for line in step_description.split('\n'):
            if line.strip().startswith('步骤'):
                # 提取步骤描述
                parts = line.split(':', 1)
                if len(parts) > 1:
                    step_desc = parts[1].strip()
                    # 限制描述长度
                    clean_desc = step_desc[:25] + "..." if len(step_desc) > 25 else step_desc
                    steps.append(clean_desc)

        # 如果解析失败，使用默认步骤
        if not steps:
            steps = [
                "用户偏好分析",
                "书籍特征匹配",
                "匹配度评估",
                "生成推荐"
            ]

        # 生成mermaid代码
        short_title = movie_title[:20] + "..." if len(movie_title) > 20 else movie_title

        if predicted_rating and predicted_rating >= 4.5:
            rating_color = "#c8e6c9"
        elif predicted_rating and predicted_rating >= 4.0:
            rating_color = "#fff9c4"
        else:
            rating_color = "#ffcdd2"

        # 构建基础结构
        mermaid_lines = ["graph TD"]

        # 添加开始节点
        mermaid_lines.append(f"    A[用户{user_id}]")

        # 添加步骤节点
        previous_node = "A"
        for i, step in enumerate(steps):
            node_id = chr(66 + i)  # B, C, D, ...
            mermaid_lines.append(f"    {node_id}[{step}]")
            mermaid_lines.append(f"    {previous_node} --> {node_id}")
            previous_node = node_id

        # 添加评估和推荐节点
        assessment_node = chr(66 + len(steps))
        recommendation_node = chr(67 + len(steps))
        result_node = chr(68 + len(steps))

        mermaid_lines.append(f"    {previous_node} --> {assessment_node}{{评分评估}}")
        mermaid_lines.append(f"    {assessment_node} --> {recommendation_node}[评分: {predicted_rating or 'N/A'}]")
        mermaid_lines.append(f"    {recommendation_node} --> {result_node}[推荐《{short_title}》]")

        # 添加样式
        mermaid_lines.append("")
        mermaid_lines.append("    style A fill:#e1f5fe")
        mermaid_lines.append(f"    style {result_node} fill:{rating_color}")
        mermaid_lines.append(f"    style {assessment_node} fill:#f3e5f5")

        return "\n".join(mermaid_lines)
