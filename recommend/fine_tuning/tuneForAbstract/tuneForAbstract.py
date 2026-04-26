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


class CPUOptimizedLoRATrainer:
    """CPU优化的LoRA训练器 - 修正版"""

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

    def _build_prompt_template(self, input_data):
        """修正后的提示词模板"""
        user_sequence = input_data.get('user_sequence', [])
        preferences = input_data.get('preferences', [])
        pref_weight_info = input_data.get('pref_weight_info', '未知')  # 添加偏好权重
        movie_info = input_data.get('movie_info', {})
        predicted_rating = input_data.get('predicted_rating', 0)
        explanation_type = input_data.get('explanation_type', 1)  # 添加解释类型

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

        # 根据解释类型调整提示词
        if explanation_type == 1:
            # 简洁解释：要求简短精炼
            prompt = f"""【思考框架-不输出】
1. 识别用户核心偏好：{preferences}
2. 匹配电影关键特征：类型、导演、评分
3. 生成个性化推荐理由

【指令】
请基于用户偏好和电影特征，生成3-5句简洁友好的推荐解释。

【背景信息】
{base_info}

【要求】
- 直接输出最终解释，不要思考过程
- 语言亲切自然，像朋友间的对话
- 控制在3-5句话内
- 突出个性化匹配点

【示例格式】
"从您喜欢《电影A》的观影历史中，我们看到您对悬疑类型有特别偏好。推荐的《记忆碎片》在叙事结构上与您的兴趣高度契合，预计您会很喜欢其中的反转设计。强烈推荐给您！"

请生成推荐解释："""

            # 只返回提示词部分，不包含答案
            return prompt
        else:
            # 其他解释类型的模板
            return f"请为以下电影生成推荐解释：{base_info}\n解释："

    def prepare_training_data(self):
        """准备训练数据"""
        print("准备训练数据...")

        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        training_examples = []

        for item in data.get('training_data', []):
            input_data = item.get('input', {})
            output_text = item.get('output', '')

            # 构建提示词（不包含答案）
            prompt = self._build_prompt_template(input_data)

            # 训练文本格式：提示词 + 答案
            # 这样模型学习的是在提示词后生成答案
            full_text = prompt + output_text

            training_examples.append({"text": full_text})

        dataset = Dataset.from_list(training_examples)

        def tokenize_function(examples):
            """修正tokenize函数"""
            texts = examples["text"]
            if not isinstance(texts, list):
                texts = [texts]

            tokenized = self.tokenizer(
                texts,
                truncation=True,
                padding=True,
                max_length=1024,
                return_tensors="pt",
            )

            # 对于因果语言建模，labels就是input_ids
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

            print("开始训练...")
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
    default_data_path = os.path.join(current_dir, "tuneForAbstract.json")
    default_output_dir = os.path.join(current_dir, "lora_results")

    parser = argparse.ArgumentParser(description="CPU优化的LoRA微调 - 解释1专用")
    parser.add_argument("--model_path", type=str, default=default_model_path)
    parser.add_argument("--data_path", type=str, default=default_data_path)
    parser.add_argument("--output_dir", type=str, default=default_output_dir)

    args = parser.parse_args()

    if not os.path.exists(args.model_path):
        print(f"错误: 模型路径不存在: {args.model_path}")
        return

    if not os.path.exists(args.data_path):
        print(f"错误: 数据路径不存在: {args.data_path}")
        return

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"\n开始训练配置:")
    print(f"模型路径: {args.model_path}")
    print(f"数据路径: {args.data_path}")
    print(f"输出目录: {args.output_dir}")

    trainer = CPUOptimizedLoRATrainer(args.model_path, args.data_path)
    result = trainer.train(args.output_dir)

    if result:
        print(f"\n训练成功完成！")
    else:
        print("\n训练失败！")


if __name__ == "__main__":
    main()