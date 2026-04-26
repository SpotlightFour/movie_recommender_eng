import os
import sys

from flask import Flask
from explanationAgent import ExplanationAgent
from models import db
from recommender import HybridRecommender
from profile_builder import ProfileBuilder

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = 1


def create_evaluation_app():
    """创建用于评估的 Flask 应用实例"""
    # 使用您现有的应用配置

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:admin123@localhost/movie_recommender'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = SECRET_KEY

    # 初始化扩展
    db.init_app(app)

    return app


def run_evaluation():
    """在应用上下文中运行评估"""
    app = create_evaluation_app()

    with app.app_context():
        print("✅ 应用上下文已创建，开始评估...")

        # 初始化组件
        recommender = HybridRecommender()
        profile_builder = ProfileBuilder()

        # 创建增强的智能体
        agent = ExplanationAgent(recommender, profile_builder)

        # 单个解释生成和评估
        result = agent.generate_and_evaluate_explanation(
            user_id=1,
            movie_title="盗梦空间",
            explanation_type=1,
            predicted_rating=4.5
        )

        print("评估结果:")
        print(f"解释: {result['explanation']}")
        print(f"PSS得分: {result['evaluation']['pss_score']:.3f}")
        print(f"CRA得分: {result['evaluation']['cra_score']:.3f}")


if __name__ == "__main__":
    run_evaluation()
