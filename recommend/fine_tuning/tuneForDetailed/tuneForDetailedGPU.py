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
from datetime import datetime

warnings.filterwarnings("ignore")

# 添加这行来避免tokenizers并行性警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class GPUOptimizedDetailedTrainer:
    """GPU优化的详细论证解释LoRA训练器 - 针对A800 GPU优化"""

    def __init__(self, model_path, data_path):
        self.model_path = model_path
        self.data_path = data_path
        self.model = None
        self.tokenizer = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def setup_model(self):
        """设置模型，针对A800 GPU优化"""
        print("正在加载模型和分词器...")
        print(f"使用设备: {self.device}")

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"模型路径不存在: {self.model_path}")

        print(f"模型目录内容: {os.listdir(self.model_path)[:5]}...")

        # 加载分词器
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        # 针对GPU优化加载模型
        print("使用BF16精度和GPU优化加载模型...")
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            dtype=torch.bfloat16,  # 使用BF16精度
            device_map="auto",  # 自动设备映射
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            use_cache=False  # 禁用缓存以支持梯度检查点
        )

        # 启用梯度检查点
        self.model.gradient_checkpointing_enable()
        self.model.config.use_cache = False

        print(f"模型参数量: {self.model.num_parameters():,}")
        print(f"模型设备: {next(self.model.parameters()).device}")

    def setup_lora(self):
        """设置LoRA配置，针对GPU优化"""
        # 使用更大的LoRA参数以利用GPU性能
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            inference_mode=False,
            r=16,  # 增加秩以利用GPU性能
            lora_alpha=32,
            lora_dropout=0.1,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            bias="none"
        )

        self.model = get_peft_model(self.model, lora_config)

        # 确保所有LoRA参数需要梯度
        for name, param in self.model.named_parameters():
            if "lora" in name:
                param.requires_grad = True

        self.model.print_trainable_parameters()

    def _build_prompt_template(self, input_data):
        """构建详细论证的提示词模板"""
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

        # 详细论证模板
        prompt = f"""【思考框架-不输出】
1. 数据分析：偏好权重{pref_weight_info}，历史记录{len(user_sequence)}部
2. 特征匹配：类型契合度、导演匹配度、评分对比
3. 论证构建：数据支撑的推荐理由
4. 结论强化：个性化价值体现

【指令】
作为电影推荐分析师，请基于数据生成详细且有说服力的论证解释。

【数据基础】
{base_info}

【论证要求】
- 使用具体数据支撑论点（偏好权重、评分对比等）
- 逻辑清晰，有说服力
- 语言专业但易于理解
- 突出个性化推荐的价值
- 10-12句话的连贯分析

【示例风格】
"分析显示，您在悬疑类型上有0.8的偏好权重，这与《记忆碎片》的悬疑元素高度匹配。您历史观看的{len(user_sequence)}部电影中，有30%涉及复杂叙事结构..."

请生成论证解释："""

        return prompt

    def tokenize_function(self, examples):
        """自定义分词函数"""
        texts = examples["text"]
        if not isinstance(texts, list):
            texts = [texts]

        # 详细论证通常较长，增加最大长度
        tokenized = self.tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=1536,  # 增加最大长度以适应详细解释
            return_tensors="pt",
        )

        # 确保labels需要梯度
        tokenized["labels"] = tokenized["input_ids"].clone()
        return tokenized

    def prepare_training_data(self):
        """准备训练数据"""
        print("准备训练数据...")
        print("提示词模板: 详细论证解释（10-12句话分析）")

        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        training_examples = []

        for item in data.get('training_data', []):
            input_data = item.get('input', {})
            output_text = item.get('output', '')

            # 验证必要字段
            required_fields = ['pref_weight_info', 'user_sequence']
            for field in required_fields:
                if field not in input_data:
                    print(f"警告: 输入数据缺少字段 '{field}'")

            # 构建提示词
            prompt = self._build_prompt_template(input_data)

            # 训练文本格式：提示词 + 答案
            full_text = prompt + output_text

            training_examples.append({"text": full_text})

        dataset = Dataset.from_list(training_examples)

        tokenized_dataset = dataset.map(
            self.tokenize_function,
            batched=True,
            batch_size=8,  # 增加批处理大小以利用GPU
            remove_columns=dataset.column_names
        )

        print(f"训练样本数量: {len(tokenized_dataset)}")

        if len(tokenized_dataset) > 1:
            train_test_split = tokenized_dataset.train_test_split(test_size=0.1, seed=42)
            return train_test_split["train"], train_test_split["test"]
        else:
            return tokenized_dataset, tokenized_dataset

    def train(self, output_dir=None):
        """执行训练"""
        try:
            # 创建带时间戳的输出目录
            if output_dir is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = f"./lora_results_detailed_{timestamp}"

            os.makedirs(output_dir, exist_ok=True)

            self.setup_model()
            self.setup_lora()
            train_dataset, eval_dataset = self.prepare_training_data()

            print(f"训练样本数: {len(train_dataset)}")
            if len(eval_dataset) > 0 and len(eval_dataset) < len(train_dataset):
                print(f"验证样本数: {len(eval_dataset)}")

            # GPU优化的训练参数
            training_args = TrainingArguments(
                output_dir=output_dir,
                overwrite_output_dir=True,
                per_device_train_batch_size=2,  # 减小批次大小
                per_device_eval_batch_size=2,
                gradient_accumulation_steps=4,  # 增加梯度累积
                num_train_epochs=10,
                learning_rate=2e-4,
                warmup_steps=10,
                logging_steps=10,
                eval_steps=50,
                save_steps=100,
                eval_strategy="steps" if len(eval_dataset) > 1 else "no",
                save_strategy="steps",
                load_best_model_at_end=True if len(eval_dataset) > 1 else False,
                metric_for_best_model="eval_loss" if len(eval_dataset) > 1 else None,
                greater_is_better=False,
                dataloader_pin_memory=True,
                remove_unused_columns=False,
                report_to=None,
                optim="adamw_8bit",  # 使用8位优化器
                lr_scheduler_type="cosine",
                weight_decay=0.01,
                bf16=True,
                fp16=False,
                max_grad_norm=1.0,
                gradient_checkpointing=True,
                dataloader_num_workers=2,  # 减少工作进程
                logging_dir=os.path.join(output_dir, "logs"),
                save_total_limit=2,
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

            print("开始训练详细论证模型...")
            print(f"输出目录: {output_dir}")

            # 训练前确保模型处于训练模式
            self.model.train()

            # 检查可训练参数
            trainable_params = [n for n, p in self.model.named_parameters() if p.requires_grad]
            print(f"可训练参数数量: {len(trainable_params)}")
            if trainable_params:
                print(f"示例可训练参数: {trainable_params[:3]}")

            # 训练前清空GPU缓存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            train_result = trainer.train()

            # 保存模型
            trainer.save_model()
            self.tokenizer.save_pretrained(output_dir)

            # 保存训练指标
            metrics = train_result.metrics
            trainer.log_metrics("train", metrics)
            trainer.save_metrics("train", metrics)
            trainer.save_state()

            print(f"训练完成！模型保存到: {output_dir}")

            # 打印详细训练结果
            print("\n=== 训练结果 ===")
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    print(f"  {key}: {value:.4f}")

            # 显示GPU内存使用情况
            if torch.cuda.is_available():
                print(f"\nGPU内存使用:")
                print(f"  已分配: {torch.cuda.memory_allocated() / 1024 ** 3:.2f} GB")
                print(f"  保留: {torch.cuda.memory_reserved() / 1024 ** 3:.2f} GB")
                print(f"  最大已分配: {torch.cuda.max_memory_allocated() / 1024 ** 3:.2f} GB")

            return output_dir

        except Exception as e:
            print(f"训练过程中出现错误: {str(e)}")
            import traceback
            traceback.print_exc()

            # 出错时清空GPU缓存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            return None


def main():
    """主函数"""
    import argparse

    current_script_path = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_script_path)
    parent_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(parent_dir)

    default_model_path = os.path.join(project_root, "granite-3.0-8b-instruct")
    default_data_path = os.path.join(current_dir, "tuneForDetailed.json")
    default_output_dir = os.path.join(current_dir, "lora_results")

    parser = argparse.ArgumentParser(description="GPU优化的LoRA微调 - 详细论证专用")
    parser.add_argument("--model_path", type=str, default=default_model_path,
                        help="基础模型路径")
    parser.add_argument("--data_path", type=str, default=default_data_path,
                        help="训练数据路径（tuneForDetailed.json）")
    parser.add_argument("--output_dir", type=str, help="输出目录")

    args = parser.parse_args()

    if not os.path.exists(args.model_path):
        print(f"错误: 模型路径不存在: {args.model_path}")
        print("请检查granite-3.0-8b-instruct文件夹是否位于项目根目录下")
        return

    if not os.path.exists(args.data_path):
        print(f"错误: 数据路径不存在: {args.data_path}")
        print(f"请确保tuneForDetailed.json文件存在")
        print(f"当前目录内容: {os.listdir(current_dir)}")
        return

    # 检查CUDA可用性
    if not torch.cuda.is_available():
        print("警告: CUDA不可用，将使用CPU训练")
    else:
        print(f"GPU信息: {torch.cuda.get_device_name(0)}")
        print(f"GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1024 ** 3:.1f} GB")

    print(f"\n=== 训练配置 ===")
    print(f"模型路径: {args.model_path}")
    print(f"数据路径: {args.data_path}")
    print(f"输出目录: {args.output_dir or '自动生成'}")
    print(f"提示词模板: 详细论证解释（10-12句话分析）")
    print(f"使用设备: {'GPU' if torch.cuda.is_available() else 'CPU'}")

    # 创建训练器并开始训练
    trainer = GPUOptimizedDetailedTrainer(args.model_path, args.data_path)
    result = trainer.train(args.output_dir)

    if result:
        print(f"\n=== 训练成功完成 ===")
        print(f"详细论证LoRA适配器保存在: {result}")
        print("提示：确保ExplanationAgent中详细论证的提示词模板与此训练使用的模板一致")
    else:
        print("\n=== 训练失败 ===")


if __name__ == "__main__":
    main()