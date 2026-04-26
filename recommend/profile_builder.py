from models import User, db, UserProfile, UserAction, UserRating, Movie, UserPreference
from recommender import HybridRecommender

hybrid_recommender = HybridRecommender()


class ProfileBuilder:
    def update_user_profile(self, user_id):
        """更新用户画像"""
        try:
            # 检查用户是否存在
            user = User.query.get(user_id)
            if not user:
                print(f"❌ 用户 {user_id} 不存在")
                return

            print(f"🔄 开始更新用户 {user_id} 的画像")

            # 分析用户行为，返回0-5分范围的偏好
            analysis = self.analyze_user_behavior(user_id)

            # 确保所有分数都是数字类型
            analysis = self._ensure_numeric_preferences(analysis)

            # 检查是否已存在画像
            profile = UserProfile.query.filter_by(user_id=user_id).first()

            if profile:
                # 更新现有画像
                profile.favorite_genres = analysis['genres']
                profile.preferred_directors = analysis['directors']
                profile.preferred_actors = analysis['actors']
                profile.preferred_decade = analysis['decade']
                profile.watch_time_pattern = analysis['watch_time_pattern']
                profile.last_updated = db.func.current_timestamp()
                print(f"✅ 更新用户 {user_id} 画像成功")
            else:
                # 创建新画像
                profile = UserProfile(
                    user_id=user_id,
                    favorite_genres=analysis['genres'],
                    preferred_directors=analysis['directors'],
                    preferred_actors=analysis['actors'],
                    preferred_decade=analysis['decade'],
                    watch_time_pattern=analysis['watch_time_pattern']
                )
                db.session.add(profile)
                print(f"✅ 创建用户 {user_id} 画像成功")

            db.session.commit()

            # 刷新推荐器
            hybrid_recommender.refresh()
            print(f"✅ 推荐器已刷新")

        except Exception as e:
            print(f"❌ 更新用户画像失败: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()

    def _ensure_numeric_preferences(self, analysis):
        """确保所有偏好分数都是数字类型而不是字符串"""

        def convert_to_numeric(pref_dict):
            """将字典中的值转换为数字类型"""
            if not pref_dict:
                return {}

            numeric_dict = {}
            for key, value in pref_dict.items():
                try:
                    # 如果已经是数字，直接使用
                    if isinstance(value, (int, float)):
                        numeric_dict[key] = float(value)
                    # 如果是字符串，尝试转换为数字
                    elif isinstance(value, str):
                        numeric_dict[key] = float(value)
                    else:
                        numeric_dict[key] = float(value)
                except (ValueError, TypeError):
                    # 转换失败，设为0
                    numeric_dict[key] = 0.0
                    print(f"⚠️ 转换偏好分数失败: {key} = {value}")
            return numeric_dict

        # 转换所有偏好字典
        analysis['genres'] = convert_to_numeric(analysis.get('genres', {}))
        analysis['directors'] = convert_to_numeric(analysis.get('directors', {}))
        analysis['actors'] = convert_to_numeric(analysis.get('actors', {}))

        return analysis

    def analyze_user_behavior(self, user_id):
        """分析用户行为，返回0-5分范围的偏好"""
        print(f"🔍 分析用户 {user_id} 的行为数据")

        analysis = {
            'genres': {},  # 类型偏好 (0-5分)
            'directors': {},  # 导演偏好 (0-5分)
            'actors': {},  # 演员偏好 (0-5分)
            'decade': '',
            'watch_time_pattern': ''
        }

        try:
            # 1. 首先检查用户是否有显式偏好设置
            explicit_preferences = self._get_explicit_preferences(user_id)
            profile = UserProfile.query.filter_by(user_id=user_id).first()
            watch_time_pattern = profile[0]
            analysis['watch_time_pattern'] = watch_time_pattern.watch_time_pattern
            if explicit_preferences:
                print(f"📊 使用显式偏好设置: {len(explicit_preferences)}个类型")
                analysis['genres'] = explicit_preferences
                rating_based_prefs = self._learn_from_action(user_id)
                analysis.update(rating_based_prefs)
            else:
                # 2. 如果没有显式偏好，从评分数据中学习
                print("🎬 从评分数据学习偏好")
                rating_based_prefs = self._learn_from_action(user_id)
                analysis.update(rating_based_prefs)

            print(f"✅ 用户画像分析完成")
            print(f"📊 类型偏好: { {k: round(v, 1) for k, v in list(analysis['genres'].items())[:3]} }")
            print(f"🎬 导演偏好: { {k: round(v, 1) for k, v in list(analysis['directors'].items())[:2]} }")
            print(f"👤 演员偏好: { {k: round(v, 1) for k, v in list(analysis['actors'].items())[:2]} }")

        except Exception as e:
            print(f"❌ 分析用户行为失败: {e}")

        return analysis

    def _get_explicit_preferences(self, user_id):
        """获取用户的显式偏好设置（0-5分）"""
        try:
            preferences = UserPreference.query.filter_by(user_id=user_id).all()
            if not preferences:
                return None

            explicit_prefs = {}
            for pref in preferences:
                score = float(pref.preference_score) if pref.preference_score is not None else 0.0
                # 直接使用用户设置的分数（0-5分）
                explicit_prefs[pref.genre] = score

            print(f"📋 显式偏好: {explicit_prefs}")
            return explicit_prefs

        except Exception as e:
            print(f"❌ 获取显式偏好失败: {e}")
            return None

    def _learn_from_action(self, user_id):
        """从用户行为中学习偏好（综合考虑评分、点赞、收藏等行为）"""
        preferences = {
            'directors': {},
            'actors': {},
            'decade': ''
        }

        try:
            # 1. 获取用户的评分数据
            ratings = UserRating.query.filter_by(user_id=user_id).all()
            print(f"📈 分析 {len(ratings)} 个评分")

            # 2. 获取用户的行为数据（点赞、收藏、浏览等）
            user_actions = UserAction.query.filter_by(user_id=user_id).all()

            # 按行为类型分类
            likes = [action for action in user_actions if action.action_type == 'LIKE']
            bookmarks = [action for action in user_actions if action.action_type == 'BOOKMARK']
            views = [action for action in user_actions if action.action_type == 'VIEW']

            print(f"❤️ 分析 {len(likes)} 个点赞")
            print(f"🔖 分析 {len(bookmarks)} 个收藏")
            print(f"👀 分析 {len(views)} 个浏览")

            # 如果没有行为数据，直接返回
            if not ratings and not user_actions:
                print("ℹ️ 无用户行为数据")
                return preferences

            # 获取所有相关电影的ID
            movie_ids = set()

            # 添加评分的电影
            movie_ids.update([r.movie_id for r in ratings])

            # 添加点赞的电影
            movie_ids.update([like.movie_id for like in likes if like.movie_id])

            # 添加收藏的电影
            movie_ids.update([bookmark.movie_id for bookmark in bookmarks if bookmark.movie_id])

            # 添加浏览的电影（但只考虑多次浏览的电影）
            view_counts = {}
            for view in views:
                if view.movie_id:
                    view_counts[view.movie_id] = view_counts.get(view.movie_id, 0) + 1

            # 只考虑浏览次数超过1次的电影
            frequently_viewed_movies = [movie_id for movie_id, count in view_counts.items() if count > 1]
            movie_ids.update(frequently_viewed_movies)
            print(f"🔍 分析 {len(frequently_viewed_movies)} 个频繁浏览的电影")

            # 查询所有相关电影
            movies = Movie.query.filter(Movie.id.in_(movie_ids)).all()
            movie_dict = {m.id: m for m in movies}

            director_scores = {}
            actor_scores = {}
            decade_scores = {}

            # 处理评分行为
            for rating in ratings:
                movie = movie_dict.get(rating.movie_id)
                if not movie:
                    continue

                # 评分权重：高分电影权重更高
                weight = float(rating.rating)  # 直接使用1-5分的评分作为权重
                self._process_movie_features(movie, weight, director_scores, actor_scores, decade_scores)

            # 处理点赞行为（权重低于高评分但高于基础权重）
            for like in likes:
                if not like.movie_id:
                    continue

                movie = movie_dict.get(like.movie_id)
                if not movie:
                    continue

                # 点赞的权重设为3.5分（相当于中等偏上的评分）
                weight = 3.5
                self._process_movie_features(movie, weight, director_scores, actor_scores, decade_scores)

            # 处理收藏行为（权重最高，表示用户特别喜欢）
            for bookmark in bookmarks:
                if not bookmark.movie_id:
                    continue

                movie = movie_dict.get(bookmark.movie_id)
                if not movie:
                    continue

                # 收藏的权重设为5分（最高权重）
                weight = 5.0
                self._process_movie_features(movie, weight, director_scores, actor_scores, decade_scores)

            # 处理频繁浏览行为（权重较低，但表示用户有一定兴趣）
            for movie_id in frequently_viewed_movies:
                movie = movie_dict.get(movie_id)
                if not movie:
                    continue

                # 浏览的权重设为2.0分（较低权重）
                weight = 2.0
                self._process_movie_features(movie, weight, director_scores, actor_scores, decade_scores)

            # 打印调试信息
            print(f"🎬 导演原始分数: {dict(list(director_scores.items())[:3]) if director_scores else '无数据'}")
            print(f"👤 演员原始分数: {dict(list(actor_scores.items())[:3]) if actor_scores else '无数据'}")
            print(f"👤 年份原始分数: {dict(list(decade_scores.items())[:3]) if decade_scores else '无数据'}")

            # 归一化处理：将分数转换为0-5分范围
            def normalize_scores(scores_dict):
                if not scores_dict:
                    return {}

                max_score = max(scores_dict.values())
                if max_score == 0:
                    return {}

                normalized = {}
                for key, score in scores_dict.items():
                    # 归一化到0-5分，并保留1位小数
                    normalized[key] = round((score / max_score) * 5, 1)

                # 按分数降序排序，只保留分数较高的前几个
                sorted_items = sorted(normalized.items(), key=lambda x: x[1], reverse=True)
                return dict(sorted_items[:5])  # 只保留前5个

            # 将归一化后的分数赋值给preferences
            preferences['directors'] = normalize_scores(director_scores)
            preferences['actors'] = normalize_scores(actor_scores)
            preferences['decade'] = next(iter(normalize_scores(decade_scores)))

            # 打印学习结果
            print(
                f"📊 学习到的导演偏好: {dict(list(preferences['directors'].items())[:3]) if preferences['directors'] else '无数据'}")
            print(
                f"📊 学习到的演员偏好: {dict(list(preferences['actors'].items())[:3]) if preferences['actors'] else '无数据'}")
            print(
                f"📊 学习到的年份偏好: {(preferences['decade']) if preferences['decade'] else '无数据'}")

        except Exception as e:
            print(f"❌ 从用户行为学习失败: {e}")
            import traceback
            traceback.print_exc()

        return preferences

    def _process_movie_features(self, movie, weight, director_scores, actor_scores, decade_scores):
        """处理单部电影的特征并累加到分数中"""
        # 处理导演
        if movie.director:
            director = movie.director.strip()
            if director:  # 确保导演名字不为空
                director_scores[director] = director_scores.get(director, 0) + weight

        # 处理演员（取前3个主要演员）
        if movie.actors:
            actors = [a.strip() for a in movie.actors.split(',')]
            for i, actor in enumerate(actors[:3]):  # 只取前3个主要演员
                if actor:  # 确保演员名字不为空
                    # 主要演员权重更高
                    actor_weight = weight * (1.0 - i * 0.2)  # 第一个演员权重最高
                    actor_scores[actor] = actor_scores.get(actor, 0) + actor_weight

        # 处理年代
        if movie.release_year:
            decade = f"{(movie.release_year // 10) * 10}s"
            decade_scores[decade] = decade_scores.get(decade, 0) + weight