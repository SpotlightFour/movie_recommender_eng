import os
import time
from typing import List, Dict, Any, Optional

from flask import Flask
from flask_cors import CORS
from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool
from langchain_huggingface import HuggingFacePipeline
from peft import PeftModel
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from pydantic import BaseModel, Field


from evaluatorTest import Evaluator
from explanationAgentPlus import ImprovedIMDbClient
from models import Movie, UserProfile, UserRating, UserAction, db
from profile_builder import ProfileBuilder
from recommender import HybridRecommender

SECRET_KEY = 1

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:admin123@localhost/movie_recommender'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY

db.init_app(app)

# 配置CORS，允许前端访问
CORS(app)

# 初始化组件
hybrid_recommender = HybridRecommender()
profile_builder = ProfileBuilder()


# ==================== LangChain智能体重构 ====================

class MovieSearchInput(BaseModel):
    """电影搜索工具输入模式"""
    movie_title: str = Field(..., description="要搜索的电影标题")


class UserPreferencesInput(BaseModel):
    """用户偏好工具输入模式"""
    user_id: int = Field(..., description="用户ID")


class MovieInfoInput(BaseModel):
    """电影信息工具输入模式"""
    movie_title: str = Field(..., description="电影标题")


class GenerateExplanationInput(BaseModel):
    """生成解释工具输入模式"""
    user_id: int = Field(..., description="用户ID")
    movie_title: str = Field(..., description="电影标题")
    explanation_type: int = Field(..., description="解释类型: 1=抽象, 2=详细, 3=步骤")
    predicted_rating: float = Field(..., description="预测评分")


class EvaluateExplanationInput(BaseModel):
    """评估解释工具输入模式"""
    explanation: str = Field(..., description="要评估的解释文本")
    context_items: List[str] = Field(..., description="上下文信息列表")
    causal_factors: List[str] = Field(..., description="因果因素列表")


class IMDbSearchTool(BaseTool):
    """IMDb搜索工具 - 封装原有IMDb客户端功能"""
    name: str = "imdb_search"
    description: str = "从IMDb网站搜索电影详细信息，包括导演、演员、类型、评分、剧情简介等"
    args_schema: type[BaseModel] = MovieSearchInput

    def __init__(self, imdb_client=None, **kwargs):
        super().__init__(**kwargs)
        self.imdb_client = imdb_client or ImprovedIMDbClient()

    def _run(self, movie_title: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """执行IMDb搜索"""
        try:
            print(f"🔍 IMDb搜索工具: 搜索电影 '{movie_title}'")
            movie_data = self.imdb_client.search_movie(movie_title)

            if movie_data:
                formatted_info = self.imdb_client.format_movie_info(movie_data)

                # 构建结构化信息
                result = f"""✅ 成功获取电影信息:
电影标题: {formatted_info.get('title', 'N/A')}
原始标题: {formatted_info.get('original_title', 'N/A')}
上映年份: {formatted_info.get('release_year', 'N/A')}
导演: {formatted_info.get('director', 'N/A')}
类型: {', '.join(formatted_info.get('genres', []))}
演员: {', '.join(formatted_info.get('actors', [])[:5])}
剧情简介: {formatted_info.get('overview', 'N/A')[:200]}...
IMDb评分: {formatted_info.get('vote_average', 0)}/10 (基于{formatted_info.get('vote_count', 0)}票)
时长: {formatted_info.get('runtime', 0)}分钟
数据来源: {formatted_info.get('source', 'N/A')}"""
                return result
            else:
                return f"❌ 未找到电影 '{movie_title}' 的IMDb信息"

        except Exception as e:
            print(f"IMDb搜索工具错误: {str(e)}")
            return f"搜索电影 '{movie_title}' 时发生错误: {str(e)}"


class UserPreferencesTool(BaseTool):
    """用户偏好工具 - 封装原有用户偏好获取功能"""
    name: str = "get_user_preferences"
    description: str = "获取用户的观影偏好、历史评分和观看记录"
    args_schema: type[BaseModel] = UserPreferencesInput

    def _run(self, user_id: int, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """获取用户偏好信息"""
        try:
            print(f"👤 用户偏好工具: 获取用户 {user_id} 的偏好")

            with app.app_context():
                # 获取用户画像
                profile = UserProfile.query.filter_by(user_id=user_id).first()

                if not profile or not profile.favorite_genres:
                    return f"用户 {user_id} 没有偏好数据，使用默认偏好"

                # 获取最近评分记录
                recent_ratings = UserRating.query.filter_by(user_id=user_id) \
                    .order_by(UserRating.rated_at.desc()) \
                    .limit(10).all()

                # 获取观看历史
                recent_actions = UserAction.query.filter_by(user_id=user_id) \
                    .order_by(UserAction.action_time.desc()) \
                    .limit(10).all()

                # 构建偏好信息
                sorted_genres = sorted(profile.favorite_genres.items(),
                                       key=lambda x: x[1], reverse=True)

                preferences_text = "用户偏好:\n"
                for genre, score in sorted_genres[:5]:  # 取前5个偏好
                    preferences_text += f"  - {genre}: {score:.3f}\n"

                # 最近评分
                if recent_ratings:
                    preferences_text += "\n最近评分记录:\n"
                    for rating in recent_ratings[:5]:
                        movie = Movie.query.get(rating.movie_id)
                        if movie:
                            preferences_text += f"  - {movie.title}: {rating.rating}/5\n"

                # 最近观看
                if recent_actions:
                    preferences_text += "\n最近观看记录:\n"
                    for action in recent_actions[:5]:
                        if action.action_type == 'view':
                            movie = Movie.query.get(action.movie_id)
                            if movie:
                                preferences_text += f"  - 观看了 {movie.title}\n"

                return preferences_text.strip()

        except Exception as e:
            print(f"用户偏好工具错误: {str(e)}")
            return f"获取用户 {user_id} 偏好时发生错误: {str(e)}"


class MovieInfoTool(BaseTool):
    """电影信息工具 - 封装数据库查询功能"""
    name: str = "get_movie_info"
    description: str = "从本地数据库获取电影详细信息，包括类型、导演、评分等"
    args_schema: type[BaseModel] = MovieInfoInput

    def _run(self, movie_title: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """从数据库获取电影信息"""
        try:
            print(f"🎬 电影信息工具: 搜索电影 '{movie_title}'")

            with app.app_context():
                # 尝试精确匹配
                movie = Movie.query.filter(Movie.title.ilike(movie_title)).first()

                if not movie:
                    # 尝试模糊匹配
                    movie = Movie.query.filter(Movie.title.ilike(f"%{movie_title}%")).first()

                if movie:
                    # 计算平均评分
                    ratings = UserRating.query.filter_by(movie_id=movie.id).all()
                    avg_rating = sum(r.rating for r in ratings) / len(ratings) if ratings else 0

                    result = f"""✅ 数据库中找到电影:
标题: {movie.title}
导演: {movie.director or '未知'}
类型: {movie.genres or '未知'}
上映年份: {movie.release_year or '未知'}
描述: {movie.description[:200] if movie.description else '无描述'}...
平均评分: {avg_rating:.1f}/5 (基于{len(ratings)}个评分)
演员: {movie.actors[:200] if movie.actors else '未知'}"""
                    return result
                else:
                    return f"❌ 数据库中未找到电影 '{movie_title}'"

        except Exception as e:
            print(f"电影信息工具错误: {str(e)}")
            return f"搜索电影 '{movie_title}' 时发生错误: {str(e)}"


class ExplanationGeneratorTool(BaseTool):
    """解释生成工具 - 封装原有的模型生成功能"""
    name: str = "generate_explanation"
    description: str = "生成电影推荐的个性化解释。需要电影信息、用户偏好和预测评分作为输入"
    args_schema: type[BaseModel] = GenerateExplanationInput

    def __init__(self, models_dict: Dict, tokenizers_dict: Dict, **kwargs):
        super().__init__(**kwargs)
        self.models = models_dict
        self.tokenizers = tokenizers_dict
        self.base_tokenizer = tokenizers_dict.get('base')

    def _run(self, user_id: int, movie_title: str,
             explanation_type: int, predicted_rating: float,
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """生成解释"""
        try:
            print(f"🤖 解释生成工具: 为用户 {user_id} 生成电影 {movie_title} 的类型 {explanation_type} 解释")

            # 获取模型和分词器
            model, tokenizer = self._get_model_for_explanation(explanation_type)
            if not model or not tokenizer:
                return "❌ 无法加载生成模型"

            # 生成提示词
            prompt = self._generate_prompt(user_id, movie_title, explanation_type, predicted_rating)

            # 使用模型生成
            if torch.cuda.is_available():
                inputs = tokenizer(prompt, return_tensors="pt", padding=True,
                                   truncation=True, max_length=512).to(model.device)
            else:
                inputs = tokenizer(prompt, return_tensors="pt", padding=True,
                                   truncation=True, max_length=512)

            # 调整生成长度
            token_lengths = {1: 200, 2: 400, 3: 300}
            max_tokens = token_lengths.get(explanation_type, 300)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.9,
                    top_k=50,
                    repetition_penalty=1.1,
                    pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )

            # 解码输出
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            generated_text = response.replace(prompt, "").strip()

            return f"✅ 生成的解释 (类型{explanation_type}):\n\n{generated_text}"

        except Exception as e:
            print(f"解释生成工具错误: {str(e)}")
            return f"生成解释时发生错误: {str(e)}"

    def _get_model_for_explanation(self, explanation_type: int):
        """获取指定解释类型的模型"""
        if explanation_type in self.models:
            return self.models[explanation_type], self.tokenizers.get(explanation_type, self.base_tokenizer)
        elif 'base' in self.models:
            return self.models['base'], self.base_tokenizer
        return None, None

    def _generate_prompt(self, user_id: int, movie_title: str,
                         explanation_type: int, predicted_rating: float) -> str:
        """生成提示词 - 简化版本，实际实现需要完整的逻辑"""
        # 这里应该调用原有的_generate_prompt方法
        # 为了简化，返回一个基本提示
        return f"""请为电影《{movie_title}》生成一个推荐解释。
用户ID: {user_id}
解释类型: {explanation_type}
预测评分: {predicted_rating}
请基于用户的历史偏好和电影的相似性，生成一个个性化的推荐解释。"""


class ExplanationEvaluatorTool(BaseTool):
    """解释评估工具"""
    name: str = "evaluate_explanation"
    description: str = "评估解释的质量，返回PSS和CRA分数"
    args_schema: type[BaseModel] = EvaluateExplanationInput

    def __init__(self, evaluator=None, **kwargs):
        super().__init__(**kwargs)
        self.evaluator = evaluator or Evaluator()

    def _run(self, explanation: str, context_items: List[str],
             causal_factors: List[str],
             run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """评估解释质量"""
        try:
            print("📈 评估解释质量")

            pss_score, cra_score = self.evaluator.evaluate(
                explanation=explanation,
                context=context_items,
                causal=causal_factors,
                threshold=0.7
            )

            return f"""评估结果:
🎯 个性化(PSS)得分: {pss_score:.4f}
🔗 因果关系(CRA)得分: {cra_score:.4f}
📊 综合质量: {'优秀' if (pss_score + cra_score) / 2 > 0.7 else '良好' if (pss_score + cra_score) / 2 > 0.5 else '需要改进'}"""

        except Exception as e:
            print(f"评估工具错误: {str(e)}")
            return f"评估解释时发生错误: {str(e)}"


class CacheManager:
    """缓存管理器 - 替代原有的记忆模块"""

    def __init__(self):
        self.cache = {
            'user_preferences': {},  # 用户偏好缓存
            'movie_info': {},  # 电影信息缓存
            'explanations': {},  # 解释结果缓存
            'search_results': {}  # 搜索结果缓存
        }
        self.ttl = 3600  # 1小时过期

    def get(self, key: str, cache_type: str = 'movie_info'):
        """获取缓存"""
        if cache_type in self.cache and key in self.cache[cache_type]:
            data, timestamp = self.cache[cache_type][key]
            if time.time() - timestamp < self.ttl:
                return data
        return None

    def set(self, key: str, data: Any, cache_type: str = 'movie_info'):
        """设置缓存"""
        if cache_type not in self.cache:
            self.cache[cache_type] = {}
        self.cache[cache_type][key] = (data, time.time())
        return True

    def clear(self, cache_type: str = None):
        """清空缓存"""
        if cache_type:
            if cache_type in self.cache:
                self.cache[cache_type].clear()
        else:
            for cache in self.cache.values():
                cache.clear()
        print("✅ 缓存已清空")

    def stats(self):
        """获取缓存统计"""
        return {k: len(v) for k, v in self.cache.items()}


class TaskPlanner:
    """任务规划器 - 替代原有的规划模块"""

    def __init__(self):
        self.task_templates = {
            1: self._plan_abstract_explanation,  # 抽象解释
            2: self._plan_detailed_explanation,  # 详细解释
            3: self._plan_process_explanation  # 步骤解释
        }

    def create_plan(self, user_id: int, movie_title: str,
                    explanation_type: int, predicted_rating: float) -> Dict:
        """创建执行计划"""
        plan_func = self.task_templates.get(explanation_type, self._plan_abstract_explanation)
        return plan_func(user_id, movie_title, predicted_rating)

    def _plan_abstract_explanation(self, user_id: int, movie_title: str,
                                   predicted_rating: float) -> Dict:
        """规划抽象解释任务"""
        return {
            "task_type": "abstract_explanation",
            "steps": [
                {"action": "get_movie_info", "params": {"movie_title": movie_title}},
                {"action": "get_user_preferences", "params": {"user_id": user_id}},
                {"action": "generate_explanation", "params": {
                    "user_id": user_id,
                    "movie_title": movie_title,
                    "explanation_type": 1,
                    "predicted_rating": predicted_rating
                }},
                {"action": "evaluate_explanation", "params": {}}
            ],
            "description": "生成简洁的抽象解释（3-5句话）"
        }

    def _plan_detailed_explanation(self, user_id: int, movie_title: str,
                                   predicted_rating: float) -> Dict:
        """规划详细解释任务"""
        return {
            "task_type": "detailed_explanation",
            "steps": [
                {"action": "imdb_search", "params": {"movie_title": movie_title}},
                {"action": "get_movie_info", "params": {"movie_title": movie_title}},
                {"action": "get_user_preferences", "params": {"user_id": user_id}},
                {"action": "generate_explanation", "params": {
                    "user_id": user_id,
                    "movie_title": movie_title,
                    "explanation_type": 2,
                    "predicted_rating": predicted_rating
                }},
                {"action": "evaluate_explanation", "params": {}}
            ],
            "description": "生成详细的论证解释（10-12句话）"
        }

    def _plan_process_explanation(self, user_id: int, movie_title: str,
                                  predicted_rating: float) -> Dict:
        """规划步骤解释任务"""
        return {
            "task_type": "process_explanation",
            "steps": [
                {"action": "imdb_search", "params": {"movie_title": movie_title}},
                {"action": "get_user_preferences", "params": {"user_id": user_id}},
                {"action": "generate_explanation", "params": {
                    "user_id": user_id,
                    "movie_title": movie_title,
                    "explanation_type": 3,
                    "predicted_rating": predicted_rating
                }},
                {"action": "evaluate_explanation", "params": {}}
            ],
            "description": "生成推荐过程的步骤解释（流程图）"
        }


class MovieExplanationAgent:
    """电影解释智能体 - 基于LangChain重构"""

    def __init__(self, model_path="./qwen_models"):
        print("🚀 初始化电影解释智能体...")

        # 初始化缓存管理器
        self.cache_manager = CacheManager()

        # 初始化任务规划器
        self.task_planner = TaskPlanner()

        # 初始化IMDb客户端
        self.imdb_client = ImprovedIMDbClient()

        # 初始化评估器
        self.evaluator = Evaluator()

        # 加载模型
        self.models, self.tokenizers = self._load_models(model_path)

        # 初始化工具
        self.tools = self._initialize_tools()

        # 初始化LangChain智能体
        self.agent_executor = self._create_agent()

        print("✅ 电影解释智能体初始化完成")

    def _load_models(self, model_path: str):
        """加载所有模型"""
        models = {}
        tokenizers = {}

        try:
            print(f"从目录加载模型: {model_path}")

            if not os.path.exists(model_path):
                print(f"模型目录不存在: {model_path}")
                return {}, {}

            # 加载基础模型
            tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                trust_remote_code=True
            )

            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True
            )

            models['base'] = model
            tokenizers['base'] = tokenizer
            print("✅ 基础模型加载成功")

            # LoRA适配器路径
            lora_paths = {
                1: './fine_tuning/tuneForAbstract/lora_results',
                2: './fine_tuning/tuneForDetailed/lora_results',
                3: './fine_tuning/tuneForHow/lora_results'
            }

            # 加载LoRA适配器
            for exp_type, lora_path in lora_paths.items():
                if os.path.exists(lora_path):
                    try:
                        print(f"加载LoRA适配器: {lora_path}")

                        # 创建新模型实例
                        adapter_model = AutoModelForCausalLM.from_pretrained(
                            model_path,
                            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                            device_map="auto" if torch.cuda.is_available() else None,
                            trust_remote_code=True
                        )

                        # 加载LoRA权重
                        adapter_model = PeftModel.from_pretrained(adapter_model, lora_path)

                        # 合并权重
                        adapter_model = adapter_model.merge_and_unload()

                        models[exp_type] = adapter_model
                        tokenizers[exp_type] = tokenizer

                        print(f"✅ LoRA适配器 {exp_type} 加载成功")

                    except Exception as e:
                        print(f"❌ 加载LoRA适配器失败: {str(e)}")
                        # 使用基础模型作为回退
                        models[exp_type] = model
                        tokenizers[exp_type] = tokenizer
                else:
                    print(f"❌ LoRA路径不存在: {lora_path}")
                    models[exp_type] = model
                    tokenizers[exp_type] = tokenizer

            return models, tokenizers

        except Exception as e:
            print(f"❌ 加载模型失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}, {}

    def _initialize_tools(self):
        """初始化所有工具"""
        tools = [
            IMDbSearchTool(imdb_client=self.imdb_client),
            UserPreferencesTool(),
            MovieInfoTool(),
            ExplanationGeneratorTool(models_dict=self.models, tokenizers_dict=self.tokenizers),
            ExplanationEvaluatorTool(evaluator=self.evaluator)
        ]
        return tools

    def _create_agent(self):
        """创建LangChain智能体执行器"""

        # 定义系统提示词
        system_prompt = """你是一个电影推荐解释智能体。你的任务是根据用户请求生成个性化的电影推荐解释。

你可以使用以下工具：
{tools}

使用以下格式：
Question: 用户的问题
Thought: 你需要思考接下来要做什么
Action: 要使用的工具名称，必须是以下之一：[{tool_names}]
Action Input: 工具的输入
Observation: 工具的结果
...（这个思考/行动/观察可以重复多次）
Thought: 我现在有最终答案
Final Answer: 最终的完整解释

开始！

历史对话：
{chat_history}

Question: {input}
{agent_scratchpad}"""

        # 创建提示词模板
        prompt = PromptTemplate(
            input_variables=["input", "chat_history", "agent_scratchpad"],
            template=system_prompt
        )

        # 创建记忆
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        # 由于我们使用HF Pipeline，需要将其包装为LangChain LLM
        if 'base' in self.models:
            hf_pipeline = pipeline(
                "text-generation",
                model=self.models['base'],
                tokenizer=self.tokenizers['base'],
                device=0 if torch.cuda.is_available() else -1,
                max_new_tokens=200,
                temperature=0.7,
                do_sample=True,
                top_p=0.9
            )

            llm = HuggingFacePipeline(pipeline=hf_pipeline)

        # 创建智能体
        agent = create_react_agent(
            llm=llm,
            tools=self.tools,
            prompt=prompt
        )

        # 创建执行器
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=memory,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5
        )

        return agent_executor

    def generate_explanation(self, user_id: int, movie_title: str,
                             explanation_type: int, predicted_rating: float) -> Dict:
        """生成解释的主方法"""
        print(f"\n{'=' * 60}")
        print(f"🎬 开始处理解释请求")
        print(f"👤 用户ID: {user_id}")
        print(f"📽️ 电影: {movie_title}")
        print(f"🔧 解释类型: {explanation_type}")
        print(f"⭐ 预测评分: {predicted_rating}")
        print(f"{'=' * 60}\n")

        try:
            # 1. 创建执行计划
            print("📋 创建执行计划...")
            plan = self.task_planner.create_plan(user_id, movie_title, explanation_type, predicted_rating)
            print(f"✅ 计划创建完成: {plan['description']}")

            # 2. 检查缓存
            cache_key = f"{user_id}_{movie_title}_{explanation_type}"
            cached_explanation = self.cache_manager.get(cache_key, 'explanations')

            if cached_explanation:
                print("💾 使用缓存的解释结果")
                return {
                    'explanation': cached_explanation,
                    'source': 'cache',
                    'plan': plan,
                    'success': True
                }

            # 3. 准备上下文信息
            context_items = self._get_context_items(user_id, movie_title)
            causal_factors = self._get_causal_factors(user_id, movie_title)

            # 4. 使用智能体生成解释
            print("🤖 使用智能体生成解释...")

            # 构建智能体输入
            task_description = f"""为用户{user_id}的电影《{movie_title}》生成个性化推荐解释。

要求:
1. 解释类型: {explanation_type} ({self._get_explanation_type_name(explanation_type)})
2. 预测评分: {predicted_rating}/5.0
3. 请使用可用的工具获取电影信息和用户偏好
4. 生成高质量、个性化的解释

请按以下步骤执行:
1. 首先获取电影《{movie_title}》的详细信息
2. 然后获取用户{user_id}的偏好和历史记录
3. 最后生成个性化解释"""

            # 执行智能体
            agent_response = self.agent_executor.invoke({
                "input": task_description,
                "chat_history": []
            })

            explanation = agent_response.get("output", "")

            if not explanation or len(explanation.strip()) < 10:
                print("⚠️ 智能体未生成有效解释，使用回退方案")
                explanation = self._get_fallback_explanation(explanation_type)

            # 5. 评估解释质量
            print("📈 评估解释质量...")
            evaluation = self._evaluate_explanation(explanation, context_items, causal_factors)

            # 6. 缓存结果
            self.cache_manager.set(cache_key, explanation, 'explanations')

            result = {
                'explanation': explanation,
                'evaluation': evaluation,
                'plan': plan,
                'source': 'agent',
                'success': True
            }

            print(
                f"✅ 解释生成完成! 评估分数: PSS={evaluation.get('pss_score', 0):.3f}, CRA={evaluation.get('cra_score', 0):.3f}")

            return result

        except Exception as e:
            print(f"❌ 生成解释时发生错误: {str(e)}")
            import traceback
            traceback.print_exc()

            return {
                'explanation': self._get_fallback_explanation(explanation_type),
                'error': str(e),
                'success': False
            }

    def _get_context_items(self, user_id: int, movie_title: str) -> List[str]:
        """获取上下文信息"""
        context_items = []

        try:
            with app.app_context():
                # 获取用户偏好
                preferences = self._get_user_preferences(user_id)
                if preferences:
                    context_items.append(f"用户偏好: {', '.join(preferences)}")

                # 获取电影信息
                movie_info = self._get_movie_info_from_db(movie_title)
                if movie_info:
                    context_items.append(f"电影: 《{movie_info.get('title', movie_title)}》")
                    if movie_info.get('genres'):
                        context_items.append(f"电影类型: {', '.join(movie_info.get('genres', []))}")

                # 添加用户历史
                user_sequence = self._get_user_sequence(user_id, 5)
                if user_sequence:
                    context_items.append(f"用户最近观看: {', '.join(user_sequence[:3])}...")

        except Exception as e:
            print(f"获取上下文失败: {str(e)}")

        return context_items if context_items else ["用户偏好", "电影信息", "历史记录"]

    def _get_causal_factors(self, user_id: int, movie_title: str) -> List[str]:
        """获取因果因素"""
        causal_factors = []

        try:
            with app.app_context():
                preferences = self._get_user_preferences(user_id)
                movie_info = self._get_movie_info_from_db(movie_title)

                if preferences and movie_info:
                    movie_genres = movie_info.get('genres', [])

                    # 类型匹配的因果分析
                    matching_genres = set(preferences) & set(movie_genres)
                    if matching_genres:
                        for genre in list(matching_genres)[:2]:
                            causal_factors.append(f"用户偏好{genre}类型与电影{genre}类型直接匹配")
                    else:
                        if preferences:
                            main_pref = preferences[0]
                            causal_factors.append(f"虽然电影没有{main_pref}类型，但其他特征可能吸引用户")

                    # 通用因果因素
                    causal_factors.extend([
                        "类型匹配度影响用户满意度",
                        "导演知名度影响观看意愿",
                        "电影评分影响用户选择",
                        "个性化推荐提高用户参与度"
                    ])

        except Exception as e:
            print(f"获取因果因素失败: {str(e)}")

        return causal_factors if causal_factors else [
            "类型匹配影响推荐效果",
            "用户历史偏好预测满意度",
            "电影特征影响用户决策"
        ]

    def _get_user_preferences(self, user_id: int) -> List[str]:
        """获取用户偏好"""
        try:
            profile = UserProfile.query.filter_by(user_id=user_id).first()
            if profile and profile.favorite_genres:
                sorted_genres = sorted(profile.favorite_genres.items(),
                                       key=lambda x: x[1], reverse=True)
                preferences = [genre for genre, score in sorted_genres[:3]]
                return preferences
        except Exception as e:
            print(f"获取用户偏好失败: {str(e)}")

        return ['动作', '喜剧', '剧情']  # 默认偏好

    def _get_movie_info_from_db(self, movie_title: str) -> Dict:
        """从数据库获取电影信息"""
        try:
            movie = Movie.query.filter(Movie.title.ilike(f"%{movie_title}%")).first()
            if movie:
                return {
                    'title': movie.title,
                    'director': movie.director or "",
                    'genres': movie.genres.split(',') if movie.genres else [],
                    'release_year': movie.release_year or "",
                    'overview': movie.description or ""
                }
        except Exception as e:
            print(f"从数据库获取电影信息失败: {str(e)}")

        return {}

    def _get_user_sequence(self, user_id: int, max_length: int = 5) -> List[str]:
        """获取用户历史序列"""
        try:
            ratings = UserRating.query.filter_by(user_id=user_id) \
                .order_by(UserRating.rated_at.desc()) \
                .limit(max_length).all()

            sequence = []
            for rating in ratings:
                movie = Movie.query.get(rating.movie_id)
                if movie:
                    sequence.append(movie.title)

            return sequence
        except Exception as e:
            print(f"获取用户序列失败: {str(e)}")
            return []

    def _evaluate_explanation(self, explanation: str, context_items: List[str],
                              causal_factors: List[str]) -> Dict:
        """评估解释"""
        try:
            pss_score, cra_score = self.evaluator.evaluate(
                explanation=explanation,
                context=context_items,
                causal=causal_factors,
                threshold=0.7
            )

            return {
                'pss_score': round(pss_score, 4),
                'cra_score': round(cra_score, 4),
                'context_items_count': len(context_items),
                'causal_factors_count': len(causal_factors)
            }
        except Exception as e:
            print(f"评估解释失败: {str(e)}")
            return {'pss_score': 0.0, 'cra_score': 0.0}

    def _get_explanation_type_name(self, explanation_type: int) -> str:
        """获取解释类型名称"""
        names = {
            1: "Why(abstract)解释",
            2: "Why(detailed)解释",
            3: "How解释"
        }
        return names.get(explanation_type, f"类型{explanation_type}")

    def _get_fallback_explanation(self, explanation_type: int) -> str:
        """回退解释"""
        fallback_explanations = {
            1: "根据您的观影偏好，我们为您推荐了这部电影。",
            2: "这是一部值得观看的优秀电影，具有独特的艺术价值。",
            3: "推荐系统基于内容分析和用户偏好匹配为您选择了这部电影。"
        }
        return fallback_explanations.get(explanation_type, "我们为您推荐了这部电影。")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return self.cache_manager.stats()

    def clear_cache(self) -> Dict:
        """清空缓存"""
        self.cache_manager.clear()
        return {'status': 'success', 'message': '缓存已清空'}