import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Tuple, Union
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TextSimilarityCalculator:
    def __init__(self):
        """
        使用本地Sentence Transformers模型进行文本相似度计算
        """
        # 硬编码本地模型路径
        local_model_path = "./paraphrase-MiniLM-L6-v2"

        try:
            self.model = SentenceTransformer(local_model_path)
            logger.info(f"成功加载本地模型: {local_model_path}")
            self.model_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"模型向量维度: {self.model_dim}")
        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
            raise e  # 重新抛出异常

    @staticmethod
    def split_text(text: str) -> List[str]:
        """文本分割方法"""
        if not text or len(text.strip()) == 0:
            logger.warning("输入文本为空，返回空列表")
            return []

        # 创建文本分割器实例
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=50,
            chunk_overlap=10,
            length_function=len,
            separators=["。", "！", "？", "?", "!", "；", ";", "，", ",", "\n", " "]
        )

        chunks = text_splitter.create_documents([text])

        # 提取纯文本内容列表
        chunk_texts = [chunk.page_content for chunk in chunks]

        logger.info(f"文本分割完成: 原始长度{len(text)} → {len(chunk_texts)}个块")
        return chunk_texts

    def encode_texts(self, texts: List[str]) -> np.ndarray:
        """将文本列表编码为向量（处理空列表情况）"""
        if not texts:
            logger.warning("encode_texts接收空文本列表，返回空数组")
            return np.array([])
        return self.model.encode(texts, convert_to_tensor=False, show_progress_bar=False)

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本之间的余弦相似度（增强异常处理）"""
        if not text1 or not text2:
            logger.warning("输入文本为空，相似度返回0")
            return 0.0
        try:
            embeddings = self.model.encode([text1, text2], show_progress_bar=False)
            similarity = cosine_similarity(
                embeddings[0].reshape(1, -1),
                embeddings[1].reshape(1, -1)
            )[0][0]
            return float(round(similarity, 4))
        except Exception as e:
            logger.error(f"相似度计算错误: {str(e)}")
            return 0.0

    def calculate_batch_similarity(self, texts1: List[str], texts2: List[str]) -> np.ndarray:
        """批量计算文本相似度矩阵（处理空输入）"""
        if not texts1 or not texts2:
            logger.warning("texts1或texts2为空，返回空相似度矩阵")
            return np.array([])
        emb1 = self.encode_texts(texts1)
        emb2 = self.encode_texts(texts2)
        return cosine_similarity(emb1, emb2)


class Evaluator:
    """
    评估器类，用于计算解释文本的PSS和CRA分数
    """

    def __init__(self):
        """
        初始化评估器

        参数:
        - model_name: 预训练模型名称
        """
        self.calculator = TextSimilarityCalculator()

    def calculate_pss(
            self,
            context_items: List[str],
            response: Union[str, List[str]],
            threshold: float = 0.7,
            auto_split_response: bool = True
    ) -> float:
        """
        计算个性化显著性分数(PSS)

        参数:
        - context_items: 上下文项目列表
        - response: 解释文本（可以是字符串或列表）
        - threshold: 相似度阈值
        - auto_split_response: 是否自动拆分长回复

        返回:
        - PSS分数
        """
        # 统一处理response为列表格式
        if isinstance(response, str):
            if auto_split_response:
                response_chunks = self.calculator.split_text(response)
                logger.info(f"自动拆分回复为{len(response_chunks)}个语义块")
            else:
                response_chunks = [response]
        else:
            response_chunks = response

        if not context_items:
            logger.warning("context_items为空，PSS分数返回0")
            return 0.0
        if not response_chunks:
            logger.warning("response_chunks为空，PSS分数返回0")
            return 0.0

        # 批量计算相似度矩阵
        similarity_matrix = self.calculator.calculate_batch_similarity(context_items, response_chunks)

        max_similarities = []
        for i in range(len(context_items)):
            # 获取当前上下文与所有回复块的最大相似度
            max_sim = float(np.max(similarity_matrix[i])) if len(similarity_matrix[i]) > 0 else 0.0
            exceeds_threshold = 1 if max_sim >= threshold else 0
            max_similarities.append(exceeds_threshold)

        pss_score = float(np.mean(max_similarities)) if max_similarities else 0.0
        return pss_score

    def calculate_cra(
            self,
            causal_factors: List[str],
            response_text: str,
            threshold: float = 0.7
    ) -> float:
        """
        计算因果推理准确率(CRA)

        参数:
        - causal_factors: 因果因素列表
        - response_text: 解释文本
        - threshold: 相似度阈值

        返回:
        - CRA分数
        """
        if not causal_factors:
            logger.warning("causal_factors为空，CRA分数返回0")
            return 0.0
        if not response_text:
            logger.warning("response_text为空，CRA分数返回0")
            return 0.0

        # 将响应文本视为一个整体块
        response_chunks = [response_text]
        similarity_matrix = self.calculator.calculate_batch_similarity(causal_factors, response_chunks)

        causal_similarities = []
        for i in range(len(causal_factors)):
            sim = float(similarity_matrix[i][0]) if similarity_matrix.size > 0 else 0.0
            exceeds_threshold = 1 if sim >= threshold else 0
            causal_similarities.append(exceeds_threshold)

        cra_score = float(np.mean(causal_similarities)) if causal_similarities else 0.0
        return cra_score

    def evaluate(
            self,
            explanation: str,
            context: List[str],
            causal: List[str],
            threshold: float = 0.7
    ) -> Tuple[float, float]:
        """
        综合评估方法，一次性计算PSS和CRA分数

        参数:
        - explanation: 解释文本
        - context: 上下文列表
        - causal: 因果因素列表
        - threshold: 相似度阈值

        返回:
        - (PSS分数, CRA分数)
        """
        pss_score = self.calculate_pss(context, explanation, threshold)
        cra_score = self.calculate_cra(causal, explanation, threshold)

        return pss_score, cra_score


# 使用示例
if __name__ == "__main__":
    # 创建评估器实例
    evaluator = Evaluator()

    # 示例数据
    context = [
        "平均睡眠时间仅为5.5小时",
        "通常凌晨1:00后才就寝",
        "经常在下午3点喝咖啡",
        "自我报告为夜猫子睡眠类型",
        "日志记录熬夜后下午感到疲倦和效率低下"
    ]

    causal = [
        "长期睡眠不足导致白天疲劳",
        "下午摄入咖啡因可能干扰夜间睡眠质量",
        "不规律的晚睡习惯是疲劳的主要原因"
    ]

    explanation = "你平均睡5.5小时且常到凌晨1点后睡这直接导致了白天的疲劳，请尝试将睡觉时间提前到12点前，你下午3点喝咖啡的习惯可能会让你晚上更难入睡，建议在下午2点后避免咖啡因"

    # 计算分数
    pss_score, cra_score = evaluator.evaluate(explanation, context, causal)

    # 只输出分数
    print(f"PSS分数: {pss_score:.3f}")
    print(f"CRA分数: {cra_score:.3f}")