from datetime import datetime

from flask import current_app

from models import db, Movie, UserRating, UserProfile


class HybridRecommender:
    def __init__(self):
        self.last_refresh = None

    def refresh(self):
        """刷新推荐器数据"""
        try:
            print("🔄 开始刷新推荐器数据...")

            self.last_refresh = datetime.utcnow()
            print("✅ 推荐器刷新完成")

        except Exception as e:
            print(f"❌ 刷新推荐器失败: {e}")

    def predict_with_preferences(self, user_id, new_preferences):
        """
        基于新的偏好设置预测推荐结果
        """
        try:
            print(f"🎯 开始为用户 {user_id} 进行推荐预测")

            # 获取用户当前画像
            user_profile = self._get_user_profile(user_id)
            if not user_profile:
                print("⚠️ 用户画像不存在")

            # 创建临时用户画像，合并新偏好
            temp_profile = {
                'favorite_genres': {},
                'preferred_directors': user_profile.preferred_directors or {},
                'preferred_actors': user_profile.preferred_actors or {}
            }

            # 应用新的类型偏好（0-5分范围）
            for genre, score in new_preferences.items():
                temp_profile['favorite_genres'][genre] = score

            print(f"🔧 临时画像 - 类型: {len(temp_profile['favorite_genres'])}个, "
                  f"导演: {len(temp_profile['preferred_directors'])}个, "
                  f"演员: {len(temp_profile['preferred_actors'])}个")

            # 获取当前推荐列表（用于对比）
            current_recommendations = self.recommend(user_id, top_n=5)
            current_movie_ids = set(movie['id'] for movie in current_recommendations)

            # 获取所有电影
            all_movies = Movie.query.all()
            print(f"📊 总电影数量: {len(all_movies)}")

            # 为每部电影计算新偏好下的预测评分
            predicted_scores = []
            for movie in all_movies:
                # 计算评分
                score = self.calculate_prediction_score(movie, temp_profile)

                predicted_scores.append({
                    'movie': movie,
                    'score': score,
                })

            # 按新评分排序
            predicted_scores.sort(key=lambda x: x['score'], reverse=True)
            predicted_movies = [item['movie'] for item in predicted_scores[:5]]
            predicted_movie_ids = set(movie.id for movie in predicted_movies)

            # 计算变化
            unchanged_movies = current_movie_ids.intersection(predicted_movie_ids)
            new_movies = predicted_movie_ids - current_movie_ids
            removed_movies = current_movie_ids - predicted_movie_ids

            print(f"📈 预测结果: 新增{len(new_movies)}部, 移除{len(removed_movies)}部, 不变{len(unchanged_movies)}部")

            # 生成结果
            def get_scored_movies(movie_ids, max_count=5):
                """获取带评分的电影列表"""
                scored_movies = []
                for movie_id in list(movie_ids)[:max_count]:
                    movie = next((m for m in all_movies if m.id == movie_id), None)
                    if movie:
                        # 找到对应的预测评分
                        prediction = next((p for p in predicted_scores if p['movie'].id == movie_id), None)
                        score_correspond = prediction['score'] if prediction else 2.5

                        scored_movies.append({
                            'id': movie.id,
                            'title': movie.title,
                            'prediction_score': round(score_correspond, 1),
                            'genres': movie.genres.split(',') if movie.genres else [],
                            'release_year': movie.release_year
                        })

                return scored_movies

            result = {
                'stats': {
                    'new_recommendations': len(new_movies),
                    'removed_recommendations': len(removed_movies),
                    'unchanged_recommendations': len(unchanged_movies)
                },
                'changes': {
                    'new_movies': get_scored_movies(new_movies, 5),
                    'removed_movies': get_scored_movies(removed_movies, 5),
                    'unchanged_movies': get_scored_movies(unchanged_movies, 5)
                },
                'prediction_metadata': {
                    'user_id': user_id,
                    'preferences_used': new_preferences,
                    'calculation_time': datetime.utcnow().isoformat()
                }
            }

            print("✅ 预测完成")
            return result

        except Exception as e:
            print(f"❌ 推荐预测失败: {e}")
            import traceback
            traceback.print_exc()

    def calculate_prediction_score(self, movie, user_profile):
        """
        计算电影的预测评分
        基于类型匹配、导演匹配、演员匹配等因素
        """
        try:

            # 类型匹配加分
            genre_bonus = self._calculate_genre_bonus(movie, user_profile)

            # 年代匹配加分
            year_bonus = self._calculate_year_bonus(movie, user_profile)

            # 导演匹配加分（如果有用户画像中的导演信息）
            director_bonus = self._calculate_director_bonus(movie, user_profile)

            # 演员匹配加分（如果有用户画像中的演员信息）
            actor_bonus = self._calculate_actor_bonus(movie, user_profile)

            # 计算总评分
            total_score = genre_bonus + year_bonus + director_bonus + actor_bonus

            # 确保评分在合理范围内
            return max(1.0, min(5.0, total_score))

        except Exception as e:
            print(f"❌ 计算预测评分失败: {e}")
            return 2.5  # 默认评分

    def _calculate_genre_bonus(self, movie, user_profile):
        """计算类型匹配加分"""
        try:
            bonus = 0.0

            if not movie.genres:
                return bonus

            # 获取用户类型偏好
            if isinstance(user_profile, dict):
                # 如果是字典，使用键访问
                preferred_genres = user_profile.get('favorite_genres', {})
            else:
                # 如果是对象，使用属性访问
                preferred_genres = getattr(user_profile, 'favorite_genres', {})

            if not preferred_genres:
                return bonus

            # 解析电影类型
            movie_genres = []
            if isinstance(movie.genres, str):
                movie_genres = [genre.strip() for genre in movie.genres.split(',')]
            elif isinstance(movie.genres, list):
                movie_genres = movie.genres
            else:
                return bonus

            # 计算类型匹配度
            genre_match_score = 0
            max_possible_score = 0

            for genre in movie_genres:
                if genre in preferred_genres:
                    # 用户对该类型的偏好程度（0-5分）
                    preference_strength = preferred_genres[genre]
                    genre_match_score += preference_strength
                max_possible_score += 5  # 每个类型最高5分

            if max_possible_score > 0:
                # 归一化到0-3分范围
                match_ratio = genre_match_score / max_possible_score
                bonus = match_ratio * 3.0

            return bonus

        except Exception as e:
            print(f"❌ 计算类型加分失败: {e}")
            return 0.0

    def _calculate_year_bonus(self, movie, user_profile):
        """计算年代匹配加分"""
        try:
            if not movie.release_year:
                return 0.0

            # 简单的年代匹配逻辑
            current_year = datetime.now().year
            movie_year = int(movie.release_year)
            year_diff = current_year - movie_year

            # 新电影有轻微优势
            if year_diff <= 5:  # 5年内的新电影
                return 0.2
            elif year_diff <= 10:  # 5-10年的电影
                return 0.1
            else:  # 10年以上的老电影
                return 0.0

        except Exception as e:
            print(f"❌ 计算年代加分失败: {e}")
            return 0.0

    def _calculate_director_bonus(self, movie, user_profile):
        """计算导演匹配加分"""
        try:
            if not movie.director:
                return 0.0

            if isinstance(user_profile, dict):
                preferred_directors = user_profile.get('preferred_directors', {})
            else:
                preferred_directors = getattr(user_profile, 'preferred_directors', {})

            if not preferred_directors:
                return 0.0

            # 检查导演是否在用户偏好中
            if movie.director in preferred_directors:
                director_preference = preferred_directors[movie.director]
                # 导演偏好强度映射到0-0.8分
                return (director_preference / 5.0) * 0.8

            return 0.0

        except Exception as e:
            print(f"❌ 计算导演加分失败: {e}")
            return 0.0

    def _calculate_actor_bonus(self, movie, user_profile):
        """计算演员匹配加分"""
        try:
            if not movie.actors:
                return 0.0

            if isinstance(user_profile, dict):
                preferred_actors = user_profile.get('preferred_actors', {})
            else:
                preferred_actors = getattr(user_profile, 'preferred_actors', {})

            if not preferred_actors:
                return 0.0

            # 解析电影演员
            movie_actors = []
            if isinstance(movie.actors, str):
                movie_actors = [actor.strip() for actor in movie.actors.split(',')]
            elif isinstance(movie.actors, list):
                movie_actors = movie.actors
            else:
                return 0.0

            # 计算演员匹配度（取匹配度最高的演员）
            max_actor_bonus = 0.0

            for actor in movie_actors[:3]:  # 只检查前3个主演
                if actor in preferred_actors:
                    actor_preference = preferred_actors[actor]
                    # 演员偏好强度映射到0-1分
                    actor_bonus = (actor_preference / 5.0) * 1.0
                    max_actor_bonus = max(max_actor_bonus, actor_bonus)

            return max_actor_bonus

        except Exception as e:
            print(f"❌ 计算演员加分失败: {e}")
            return 0.0

    def recommend(self, user_id, top_n=5):
        """推荐逻辑：基于用户画像直接计算预测评分"""
        try:
            print(f"🎯 开始为用户 {user_id} 生成推荐")

            # 获取用户画像
            user_profile = self._get_user_profile(user_id)
            if not user_profile:
                print("⚠️ 用户画像为空，使用热门推荐")
                return self._get_popular_movies(top_n)

            print(f"👤 用户画像信息:")
            print(f"   类型偏好: {user_profile.favorite_genres}")
            print(f"   导演偏好: {user_profile.preferred_directors}")
            print(f"   演员偏好: {user_profile.preferred_actors}")

            # 获取所有电影
            movies = Movie.query.all()
            print(f"📊 总电影数量: {len(movies)}")

            # 为每部电影计算预测评分
            movie_scores = []

            for movie in movies:
                # 使用calculate_prediction_score方法计算评分
                score = self.calculate_prediction_score(movie, user_profile)

                movie_scores.append({
                    'movie': movie,
                    'score': score
                })

            # 按总评分排序
            movie_scores.sort(key=lambda x: x['score'], reverse=True)

            # 生成推荐结果
            recommendations = []
            for item in movie_scores[:top_n]:
                movie = item['movie']
                recommendations.append({
                    'id': movie.id,
                    'title': movie.title,
                    'genres': movie.genres.split(',') if movie.genres else [],
                    'release_year': movie.release_year,
                    'director': movie.director,
                    'description': movie.description,
                    'poster_url': movie.poster_url,
                    'actors': movie.actors.split(',') if movie.actors else [],
                    'predicted_rating': round(item['score'], 1),
                    'reason': self._generate_recommendation_reason(movie, user_profile, item)
                })

            print(f"✅ 生成 {len(recommendations)} 个推荐")

            # 打印推荐结果详情
            for i, rec in enumerate(recommendations):
                print(f"   {i + 1}. {rec['title']} - 评分: {rec['predicted_rating']} - 理由: {rec['reason']}")

            return recommendations

        except Exception as e:
            print(f"❌ 简化推荐失败: {e}")
            import traceback
            traceback.print_exc()
            return self._get_popular_movies(top_n)

    def _generate_recommendation_reason(self, movie, user_profile, score_info):
        """生成简化的推荐理由"""
        reasons = []

        # 评分理由
        score = score_info['score']
        if score >= 4.0:
            reasons.append("高度匹配")
        elif score >= 3.0:
            reasons.append("良好匹配")
        else:
            reasons.append("You May Like")

        # 类型匹配理由
        if movie.genres and user_profile.favorite_genres:
            movie_genres = movie.genres.split(',') if isinstance(movie.genres, str) else movie.genres
            matched_genres = []

            for genre in movie_genres:
                genre = genre.strip()
                if genre in user_profile.favorite_genres and user_profile.favorite_genres[genre] >= 3:
                    matched_genres.append(genre)

            if matched_genres:
                reasons.append(f"类型:{','.join(matched_genres[:2])}")

        # 导演匹配理由
        if movie.director and user_profile.preferred_directors:
            if movie.director in user_profile.preferred_directors:
                reasons.append(f"导演:{movie.director}")

        # 演员匹配理由
        if movie.actors and user_profile.preferred_actors:
            movie_actors = movie.actors.split(',') if isinstance(movie.actors, str) else movie.actors
            matched_actors = []

            for actor in movie_actors[:2]:  # 只检查前2个主演
                actor = actor.strip()
                if actor in user_profile.preferred_actors:
                    matched_actors.append(actor)

            if matched_actors:
                reasons.append(f"演员:{','.join(matched_actors)}")

        return " | ".join(reasons)

    def _get_user_profile(self, user_id):
        """获取用户画像数据"""
        try:
            with current_app.app_context():
                profile = UserProfile.query.filter_by(user_id=user_id).first()
                return profile
        except Exception as e:
            print(f"❌ 获取用户画像失败: {e}")
            return None

    def _get_popular_movies(self, top_n):
        """获取热门电影"""
        try:
            # 使用评分次数最多的电影
            popular = db.session.query(
                Movie.id,
                Movie.title,
                Movie.genres,
                Movie.release_year,
                Movie.director,
                Movie.description,
                Movie.poster_url,
                Movie.actors,
                db.func.count(UserRating.id).label('rating_count')
            ).join(UserRating).group_by(Movie.id).order_by(db.desc('rating_count')).limit(top_n).all()

            if not popular:
                # 如果没有评分数据，返回最近的电影
                popular = Movie.query.order_by(Movie.release_year.desc()).limit(top_n).all()
                return [self._format_movie(m) for m in popular]

            return [{
                'id': m.id,
                'title': m.title,
                'genres': m.genres.split(','),
                'release_year': m.release_year,
                'director': m.director,
                'description': m.description,
                'poster_url': m.poster_url,
                'actors': m.actors.split(',') if m.actors else []
            } for m in popular]

        except Exception as e:
            print(f"❌ 获取热门电影失败: {e}")
            # 返回一些默认电影
            movies = Movie.query.limit(top_n).all()
            return [self._format_movie(m) for m in movies]

    def _format_movie(self, movie):
        """格式化电影信息"""
        return {
            'id': movie.id,
            'title': movie.title,
            'genres': movie.genres.split(','),
            'release_year': movie.release_year,
            'director': movie.director,
            'description': movie.description,
            'poster_url': movie.poster_url,
            'actors': movie.actors.split(',') if movie.actors else []
        }
