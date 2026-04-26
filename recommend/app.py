from flask import Flask, jsonify, request
from flask_cors import CORS
from sklearn import logger
from sqlalchemy import text

from explanationAgent import ExplanationAgent, ImprovedIMDbClient
from models import db, User, Movie, UserPreference, UserRating, UserAction, UserProfile
from recommender import HybridRecommender
from profile_builder import ProfileBuilder
from datetime import datetime

SECRET_KEY = 1

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:admin123@localhost/movie_recommender_eng'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY

db.init_app(app)

# 配置CORS，允许前端访问
CORS(app)

# 延迟初始化推荐器
hybrid_recommender = HybridRecommender()
profile_builder = ProfileBuilder()

# 加载LLM
# explanation_llm = ExplanationLLM()

# 初始化客户端
imdb_client = ImprovedIMDbClient

# 初始化智能体
explanation_agent = ExplanationAgent(hybrid_recommender, profile_builder)


# def get_explanation(type):
#     data = request.get_json()
#     user_id = data.get('user_id')
#     movie_title = data.get('movie_title')
#     director = data.get('director')
#     predicted_rating = data.get('predicted_rating')
#
#     if not all([user_id, movie_title, director]):
#         return jsonify({'error': '缺少必要参数'}), 400
#
#     # 根据解释类型生成不同的提示
#     if type == 1:
#         prompt = f"用户{user_id}可能会喜欢《{movie_title}》（导演：{director}），因为这部电影"
#         explanation = explanation_llm.generate_explanation(prompt)
#     elif type == 2:
#         prompt = f"《{movie_title}》是一部由{director}导演的电影，它之所以被推荐给用户{user_id}，是因为"
#         explanation = explanation_llm.generate_explanation(prompt)
#     elif type == 3:
#         # 直接让LLM生成mermaid代码
#         prompt = f"""请简要描述用户{user_id}推荐《{movie_title}》（导演：{director}）的决策过程，以3-4个步骤的形式呈现。
#
# 请严格按照以下格式回答，每个步骤一行：
#
# 步骤1: [第一步的简要描述]
# 步骤2: [第二步的简要描述]
# 步骤3: [第三步的简要描述]
# 步骤4: [第四步的简要描述]
#
# 请确保每个步骤描述简洁明了，不超过15个字。"""
#
#         explanation = explanation_llm.generate_explanation(prompt)
#         explanation = explanation_llm.convert_steps_to_mermaid(user_id, movie_title, predicted_rating, explanation)
#         print(explanation)
#     else:
#         prompt = f"用户{user_id}可能会喜欢《{movie_title}》，因为这部电影"
#         explanation = explanation_llm.generate_explanation(prompt)
#
#     return jsonify({
#         'success': True,
#         'explanation': explanation
#     })
@app.route('/explanation/<int:type>', methods=['POST'])
def get_explanation(type):
    """获取推荐解释（使用智能体）"""
    data = request.get_json()
    user_id = data.get('user_id')
    movie_title = data.get('movie_title')
    predicted_rating = data.get('predicted_rating')

    # 使用智能体生成解释
    if explanation_agent:
        explanation = explanation_agent.generate_explanation(
            user_id, movie_title, type, predicted_rating
        )
    else:
        # 回退到简单解释
        explanation = "我们根据您的偏好为您推荐了这部电影"

    return jsonify({
        'success': True,
        'explanation': explanation,
        'explanation_type': type
    })


@app.before_request
def check_db_connection():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"数据库连接失败: {str(e)}")
        return jsonify({'error': '数据库连接失败'}), 503


def init_recommender():
    """在应用上下文中初始化推荐器"""
    global hybrid_recommender
    with app.app_context():
        hybrid_recommender = HybridRecommender()


# # 应用启动时初始化推荐器
# init_recommender()

@app.route('/')
def index():
    return jsonify({"message": "Movie Recommendation API", "status": "running"})


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data or 'email' not in data:
            return jsonify({'error': 'Missing required fields'}), 400

        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 409

        new_user = User(
            username=data['username'],
            password=data['password'],
            email=data['email']
        )
        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            'message': 'User created successfully',
            'user_id': new_user.id,
            'username': new_user.username
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Missing credentials'}), 400

        user = User.query.filter_by(username=data['username']).first()
        if not user or user.password != data['password']:
            return jsonify({'error': 'Invalid credentials'}), 401

        return jsonify({
            'user_id': user.id,
            'username': user.username
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/movies', methods=['GET'])
def get_movies():
    try:
        # 获取当前用户ID（从查询参数或认证信息中）
        user_id = request.args.get('user_id')

        movies = Movie.query.all()
        result = []

        for movie in movies:
            movie_data = {
                'id': movie.id,
                'title': movie.title,
                'genres': movie.genres.split('|'),
                'release_year': movie.release_year,
                'director': movie.director,
                'description': movie.description,
                'poster_url': movie.poster_url,
                'actors': movie.actors.split(',') if movie.actors else []
            }

            # 计算电影的平均评分和评分人数
            ratings = UserRating.query.filter_by(movie_id=movie.id).all()
            if ratings:
                total_rating = sum(r.rating for r in ratings)
                movie_data['average_rating'] = round(total_rating / len(ratings), 1)
                movie_data['rating_count'] = len(ratings)
            else:
                movie_data['average_rating'] = 0.0
                movie_data['rating_count'] = 0

            # 添加当前用户评分（如果已登录）
            if user_id:
                user_rating = UserRating.query.filter_by(
                    user_id=user_id,
                    movie_id=movie.id
                ).first()
                movie_data['user_rating'] = user_rating.rating if user_rating else None

            result.append(movie_data)

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 添加GET路由
@app.route('/preferences/<int:user_id>', methods=['GET'])
def get_user_preferences(user_id):
    """获取用户偏好设置"""
    try:
        # 检查用户是否存在
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': f'User with ID {user_id} not found'}), 404

        # 获取用户偏好
        preferences = UserPreference.query.filter_by(user_id=user_id).all()
        pref_dict = {p.genre: p.preference_score for p in preferences}

        return jsonify(pref_dict), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/preferences', methods=['POST'])
def set_preferences():
    try:
        data = request.get_json()
        if not data or 'user_id' not in data or 'preferences' not in data:
            return jsonify({'error': 'Missing required fields'}), 400

        # 检查用户是否存在
        user = db.session.get(User, data['user_id'])
        if not user:
            return jsonify({'error': f'User with ID {data["user_id"]} not found'}), 404

        # 清除旧偏好
        UserPreference.query.filter_by(user_id=data['user_id']).delete()

        # 添加新偏好
        for genre, score in data['preferences'].items():
            pref = UserPreference(
                user_id=data['user_id'],
                genre=genre,
                preference_score=float(score)
            )
            db.session.add(pref)

        db.session.commit()

        # 更新用户画像
        profile_builder.update_user_profile(data['user_id'])
        print(f"✅ 用户 {data['user_id']} 画像已更新")

        # ✅ 修复：安全地调用 refresh 方法
        if hybrid_recommender and hasattr(hybrid_recommender, 'refresh'):
            hybrid_recommender.refresh()
            print(f"✅ 推荐器已刷新")
        else:
            print("⚠️ 推荐器没有 refresh 方法，跳过刷新")

        return jsonify({'message': 'Preferences updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/rate', methods=['POST'])
def rate_movie():
    try:
        data = request.get_json()
        if not data or 'user_id' not in data or 'movie_id' not in data or 'rating' not in data:
            return jsonify({'error': 'Missing required fields'}), 400

        # 检查用户是否存在
        user = db.session.get(User, data['user_id'])
        if not user:
            return jsonify({'error': f'User with ID {data["user_id"]} not found'}), 404

        # 检查电影是否存在
        movie = db.session.get(Movie, data['movie_id'])
        if not movie:
            return jsonify({'error': f'Movie with ID {data["movie_id"]} not found'}), 404

        # 检查是否已评分
        existing_rating = UserRating.query.filter_by(
            user_id=data['user_id'],
            movie_id=data['movie_id']
        ).first()

        if existing_rating:
            existing_rating.rating = float(data['rating'])
            existing_rating.rated_at = datetime.utcnow()
        else:
            rating = UserRating(
                user_id=data['user_id'],
                movie_id=data['movie_id'],
                rating=float(data['rating'])
            )
            db.session.add(rating)

        # 记录评分行为
        action = UserAction(
            user_id=data['user_id'],
            action_type='RATE',
            movie_id=data['movie_id'],
            action_value=str(data['rating'])
        )
        db.session.add(action)

        db.session.commit()

        # 更新用户画像
        profile_builder.update_user_profile(data['user_id'])

        # 获取更新后的电影数据（包含用户评分信息）
        ratings = UserRating.query.filter_by(movie_id=data['movie_id']).all()
        total_rating = sum(r.rating for r in ratings)
        average_rating = round(total_rating / len(ratings), 1) if ratings else 0.0

        updated_movie = {
            'id': movie.id,
            'title': movie.title,
            'genres': movie.genres.split(','),
            'release_year': movie.release_year,
            'director': movie.director,
            'description': movie.description,
            'poster_url': movie.poster_url,
            'actors': movie.actors.split(',') if movie.actors else [],
            'average_rating': average_rating,
            'rating_count': len(ratings),
            'user_rating': float(data['rating'])
        }

        return jsonify({
            'message': 'Rating submitted successfully',
            'movie': updated_movie
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/action', methods=['POST'])
def record_action():
    try:
        app.logger.info("Received /action request")
        data = request.get_json()
        app.logger.debug(f"Request data: {data}")
        if not data or 'user_id' not in data or 'action_type' not in data:
            return jsonify({'error': 'Missing required fields'}), 400

        # 检查用户是否存在
        user = db.session.get(User, data['user_id'])
        if not user:
            return jsonify({'error': f'User with ID {data["user_id"]} not found'}), 404

        action = UserAction(
            user_id=data['user_id'],
            action_type=data['action_type'],
            movie_id=data.get('movie_id'),
            action_value=data.get('action_value')
        )
        db.session.add(action)
        db.session.commit()

        # 更新用户画像
        profile_builder.update_user_profile(data['user_id'])

        return jsonify({'message': 'Action recorded successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/recommendations/<int:user_id>', methods=['GET'])
def get_recommendations(user_id):
    try:
        print(f"Received /recommendations request for user {user_id}")

        if hybrid_recommender is None:
            app.logger.error("Recommender system not initialized")
            return jsonify({'error': 'Recommender system not initialized'}), 503

        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': f'User with ID {user_id} not found'}), 404

        # 获取推荐结果
        recommendations = hybrid_recommender.recommend(user_id)
        result = []
        # 处理推荐结果，确保返回完整电影信息
        for rec_movie in recommendations:
            # 如果推荐结果是字典格式，包含电影ID
            if isinstance(rec_movie, dict) and 'id' in rec_movie:
                movie_id = rec_movie['id']
            # 如果推荐结果是Movie对象
            elif hasattr(rec_movie, 'id'):
                movie_id = rec_movie.id
            else:
                # 如果无法获取电影ID，跳过此项
                continue

            # 从数据库获取完整的电影信息
            movie = db.session.get(Movie, movie_id)
            if not movie:
                continue

            # 构建与/movies接口相同的电影数据结构
            movie_data = {
                'id': movie.id,
                'title': movie.title,
                'genres': movie.genres.split(','),
                'release_year': movie.release_year,
                'director': movie.director,
                'description': movie.description,
                'poster_url': movie.poster_url,
                'predicted_rating': rec_movie.get('predicted_rating', 3.0),
                'prediction_reason': rec_movie.get('reason', 3.0),
                'actors': movie.actors.split(',') if movie.actors else []
            }

            # 计算电影的平均评分和评分人数（与/movies接口一致）
            ratings = UserRating.query.filter_by(movie_id=movie.id).all()
            if ratings:
                total_rating = sum(r.rating for r in ratings)
                movie_data['average_rating'] = round(total_rating / len(ratings), 1)
                movie_data['rating_count'] = len(ratings)
            else:
                movie_data['average_rating'] = 0.0
                movie_data['rating_count'] = 0

            # 添加当前用户评分（如果已登录）
            user_rating = UserRating.query.filter_by(
                user_id=user_id,
                movie_id=movie.id
            ).first()
            movie_data['user_rating'] = user_rating.rating if user_rating else None

            result.append(movie_data)

        app.logger.info(f"返回推荐电影数量: {len(result)}")
        return jsonify(result), 200

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in get_recommendations: {str(e)}\n{error_trace}")
        return jsonify({'error': str(e)}), 500


@app.route('/recommendations/predict', methods=['POST'])
def predict_recommendation_changes():
    """预测偏好设置变化对推荐列表的影响（包含预测评分）"""
    try:
        data = request.get_json()
        if not data or 'user_id' not in data or 'preferences' not in data:
            return jsonify({'error': 'Missing required fields'}), 400

        user_id = data['user_id']
        new_preferences = data['preferences']

        # 检查用户是否存在
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': f'User with ID {user_id} not found'}), 404

        # 使用混合推荐器进行预测
        prediction_result = hybrid_recommender.predict_with_preferences(user_id, new_preferences)

        return jsonify(prediction_result), 200

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        app.logger.error(f"Error in predict_recommendation_changes: {str(e)}\n{error_trace}")
        return jsonify({'error': str(e)}), 500


@app.route('/profile/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    try:
        # 检查用户是否存在
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': f'User with ID {user_id} not found'}), 404

        profile = UserProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            # 返回空画像而不是错误
            return jsonify({
                'favorite_genres': {},
                'preferred_directors': {},
                'preferred_actors': {},
                'preferred_decade': None,
                'watch_time_pattern': None
            }), 200

        return jsonify({
            'favorite_genres': profile.favorite_genres or {},
            'preferred_directors': profile.preferred_directors or {},
            'preferred_actors': profile.preferred_actors or {},
            'preferred_decade': profile.preferred_decade,
            'watch_time_pattern': profile.watch_time_pattern
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/profile/update/<int:user_id>', methods=['POST'])
def update_user_profile(user_id):
    """手动更新用户画像"""
    try:
        # 检查用户是否存在
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': f'User with ID {user_id} not found'}), 404

        profile_builder.update_user_profile(user_id)
        return jsonify({'message': 'Profile updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/users', methods=['GET'])
def get_users():
    """获取所有用户列表（用于调试）"""
    try:
        users = User.query.all()
        return jsonify([{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'created_at': u.created_at.isoformat() if u.created_at else None
        } for u in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # 打印所有已注册的路由
        print("=== 已注册的路由 ===")
        for rule in app.url_map.iter_rules():
            print(f"{rule.rule} -> {rule.endpoint}")
        print("===================")

        # 打印用户列表用于调试
        users = User.query.all()
        print(f"✅ 当前用户数量: {len(users)}")

        print("✅ 推荐系统初始化完成")
        print("🚀 服务启动在 http://127.0.0.1:5000")

    app.run(debug=True, host='0.0.0.0', port=5000)
