import os
import torch
import json
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq
)
from peft import (
    LoraConfig,
    get_peft_model,
    TaskType,
    prepare_model_for_kbit_training
)
from datasets import Dataset
import warnings

warnings.filterwarnings("ignore")


class MermaidFlowchartTrainer:
    """Mermaid流程图生成的LoRA训练器"""

    def __init__(self, model_path, data_path):
        self.model_path = model_path
        self.data_path = data_path
        self.model = None
        self.tokenizer = None

    def setup_model(self):
        """设置模型，针对CPU优化"""
        print("正在加载模型和分词器...")

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"模型路径不存在: {self.model_path}")

        print(f"模型目录内容: {os.listdir(self.model_path)}")

        # 加载分词器
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # 针对CPU优化加载模型
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            dtype=torch.float32,
            device_map=None,
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )

        try:
            self.model = prepare_model_for_kbit_training(self.model)
            print("已准备4位训练")
        except:
            print("4位训练不可用，使用标准训练")

        print(f"模型参数量: {self.model.num_parameters():,}")

    def setup_lora(self):
        """设置LoRA配置"""
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            inference_mode=False,
            r=8,
            lora_alpha=16,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            bias="none"
        )

        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()

    def _build_prompt_template(self, input_data, output_text):
        """构建Mermaid流程图生成的提示词模板"""
        user_sequence = input_data.get('user_sequence', [])
        preferences = input_data.get('preferences', [])
        pref_weight_info = input_data.get('pref_weight_info', '未知')
        movie_info = input_data.get('movie_info', {})
        predicted_rating = input_data.get('predicted_rating', 0)

        # 基础信息
        base_info = f"""
用户历史序列: {user_sequence[:5]}...（共{len(user_sequence)}项）
用户偏好: {preferences}
偏好权重: {pref_weight_info}
推荐电影: 《{movie_info.get('title', '未知')}》
导演: {movie_info.get('director', '未知')}
类型: {', '.join(movie_info.get('genres', []))}
简介: {movie_info.get('overview', '暂无描述')[:100]}...
预测评分: {predicted_rating}
平均评分: {movie_info.get('vote_average', 0)}/5"""

        # Mermaid流程图生成模板
        prompt = f"""【思考框架-不输出】
1. 流程设计：开始→特征提取→匹配计算→得分汇总→结果输出
2. 分数计算：四个维度具体得分显示
3. 样式设计：颜色区分不同步骤类型

【指令】
请生成标准的Mermaid流程图代码，展示电影评分预测的完整计算过程。

【流程图要求】
必须严格按照以下结构和内容生成：

graph TD
    A[开始预测评分计算] --> B[提取电影特征]
    A --> C[获取用户偏好]
    B --> D[特征分析]
    C --> D
    D --> E[类型匹配计算]
    D --> F[导演匹配计算] 
    D --> G[演员匹配计算]
    D --> H[年代匹配计算]
    E --> I[类型得分: X.X/3.0]
    F --> J[导演得分: X.X/0.8]
    G --> K[演员得分: X.X/1.0]
    H --> L[年代得分: X.X/0.2]
    I --> M[得分汇总]
    J --> M
    K --> M
    L --> M
    M --> N[计算原始总分: X.X]
    N --> O[范围调整: 1.0-5.0]
    O --> P[最终预测评分: {predicted_rating}/5.0]
    P --> Q[推荐《{movie_info.get('title', '电影')}》]

【样式要求】
style A fill:#e3f2fd,stroke:#1e88e5,stroke-width:2px
style B fill:#bbdefb
style C fill:#bbdefb
style D fill:#90caf9
style E fill:#ef9a9a
style F fill:#90caf9
style G fill:#a5d6a7
style H fill:#fff59d
style I fill:#ef9a9a
style J fill:#90caf9
style K fill:#a5d6a7
style L fill:#fff59d
style M fill:#ffcc80
style N fill:#ffcc80
style O fill:#ffcc80
style P fill:#fff9c4
style Q fill:#c8e6c9,stroke:#4caf50,stroke-width:2px

【计算说明】
请基于电影《{movie_info.get('title', '未知')}》的特征合理计算各维度得分。

请生成完整的Mermaid代码："""

        return prompt

    def prepare_training_data(self):
        """准备训练数据"""
        print("准备训练数据...")
        print("提示词模板: Mermaid流程图生成")

        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        training_examples = []

        for item in data.get('training_data', []):
            input_data = item.get('input', {})
            output_text = item.get('output', '')

            # 验证必要字段
            required_fields = ['predicted_rating', 'movie_info']
            for field in required_fields:
                if field not in input_data:
                    print(f"警告: 输入数据缺少字段 '{field}'")

            # 构建提示词
            prompt = self._build_prompt_template(input_data, output_text)

            # 训练文本格式：提示词 + Mermaid代码
            full_text = prompt + output_text

            training_examples.append({"text": full_text})

        dataset = Dataset.from_list(training_examples)

        def tokenize_function(examples):
            texts = examples["text"]
            if not isinstance(texts, list):
                texts = [texts]

            # 增加最大长度以容纳Mermaid代码
            tokenized = self.tokenizer(
                texts,
                truncation=True,
                padding=True,
                max_length=2048,  # Mermaid代码较长，增加最大长度
                return_tensors="pt",
            )

            tokenized["labels"] = tokenized["input_ids"].clone()
            return tokenized

        tokenized_dataset = dataset.map(
            tokenize_function,
            batched=True,
            batch_size=1,
            remove_columns=dataset.column_names
        )

        print(f"训练样本数量: {len(tokenized_dataset)}")

        if len(tokenized_dataset) > 1:
            train_test_split = tokenized_dataset.train_test_split(test_size=0.2)
            return train_test_split["train"], train_test_split["test"]
        else:
            return tokenized_dataset, tokenized_dataset

    def train(self, output_dir="./lora_results"):
        """执行训练"""
        try:
            self.setup_model()
            self.setup_lora()
            train_dataset, eval_dataset = self.prepare_training_data()

            print(f"训练样本数: {len(train_dataset)}")
            if len(eval_dataset) > 0 and len(eval_dataset) < len(train_dataset):
                print(f"验证样本数: {len(eval_dataset)}")

            training_args = TrainingArguments(
                output_dir=output_dir,
                overwrite_output_dir=True,
                per_device_train_batch_size=1,
                per_device_eval_batch_size=1,
                gradient_accumulation_steps=4,
                num_train_epochs=5,
                learning_rate=1e-4,
                warmup_steps=5,
                logging_steps=10,
                eval_steps=50,
                save_steps=100,
                eval_strategy="steps" if len(eval_dataset) > 1 else "no",
                save_strategy="steps",
                load_best_model_at_end=True if len(eval_dataset) > 1 else False,
                metric_for_best_model="eval_loss" if len(eval_dataset) > 1 else None,
                greater_is_better=False,
                dataloader_pin_memory=False,
                remove_unused_columns=False,
                report_to=None,
                optim="adamw_torch",
                lr_scheduler_type="cosine",
                weight_decay=0.01,
                fp16=False,
                bf16=False,
                max_grad_norm=1.0,
            )

            data_collator = DataCollatorForSeq2Seq(
                self.tokenizer,
                pad_to_multiple_of=8,
                padding=True,
                return_tensors="pt",
            )

            trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset if len(eval_dataset) > 1 else None,
                tokenizer=self.tokenizer,
                data_collator=data_collator,
            )

            print("开始训练Mermaid流程图生成模型...")
            train_result = trainer.train()

            trainer.save_model()
            self.tokenizer.save_pretrained(output_dir)

            metrics = train_result.metrics
            trainer.log_metrics("train", metrics)
            trainer.save_metrics("train", metrics)
            trainer.save_state()

            print(f"训练完成！模型保存到: {output_dir}")

            print("\n训练结果:")
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    print(f"  {key}: {value:.4f}")

            return output_dir

        except Exception as e:
            print(f"训练过程中出现错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """主函数"""
    import argparse

    current_script_path = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_script_path)
    parent_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(parent_dir)

    default_model_path = os.path.join(project_root, "qwen_models")
    default_data_path = os.path.join(current_dir, "tuneForHow.json")
    default_output_dir = os.path.join(current_dir, "lora_results")

    parser = argparse.ArgumentParser(description="Mermaid流程图生成的LoRA微调")
    parser.add_argument("--model_path", type=str, default=default_model_path,
                        help="基础模型路径")
    parser.add_argument("--data_path", type=str, default=default_data_path,
                        help="训练数据路径（tuneForHow.json）")
    parser.add_argument("--output_dir", type=str, default=default_output_dir,
                        help="输出目录")

    args = parser.parse_args()

    if not os.path.exists(args.model_path):
        print(f"错误: 模型路径不存在: {args.model_path}")
        print("请检查qwen_models文件夹是否位于项目根目录下")
        return

    if not os.path.exists(args.data_path):
        print(f"错误: 数据路径不存在: {args.data_path}")
        print(f"请确保tuneForHow.json文件存在")
        print(f"当前目录内容: {os.listdir(current_dir)}")
        return

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"\n开始训练配置:")
    print(f"模型路径: {args.model_path}")
    print(f"数据路径: {args.data_path}")
    print(f"输出目录: {args.output_dir}")
    print(f"提示词模板: Mermaid流程图生成")

    # 创建训练器并开始训练
    trainer = MermaidFlowchartTrainer(args.model_path, args.data_path)
    result = trainer.train(args.output_dir)

    if result:
        print(f"\n训练成功完成！")
        print(f"Mermaid流程图生成LoRA适配器保存在: {result}")
        print("提示：确保调用时使用的提示词模板与此训练使用的模板一致")
    else:
        print("\n训练失败！")


if __name__ == "__main__":
    main()