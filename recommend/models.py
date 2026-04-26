from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Movie(db.Model):
    __tablename__ = "movies"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    genres = db.Column(db.String(255), nullable=False)
    release_year = db.Column(db.Integer)
    director = db.Column(db.String(100))
    description = db.Column(db.Text)
    poster_url = db.Column(db.String(255))
    actors = db.Column(db.String(255))


class UserPreference(db.Model):
    __tablename__ = 'user_preferences'  # 显式指定表名

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    genre = db.Column(db.String(50), nullable=False)
    preference_score = db.Column(db.Float, default=0.0)


class UserRating(db.Model):
    __tablename__ = 'user_ratings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    rated_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class UserAction(db.Model):
    __tablename__ = 'user_actions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action_type = db.Column(db.String(20), nullable=False)  # VIEW, RATE, LIKE, BOOKMARK, SEARCH
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'))
    action_value = db.Column(db.String(255))
    action_time = db.Column(db.DateTime, default=db.func.current_timestamp())


class UserProfile(db.Model):
    __tablename__ = 'user_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    favorite_genres = db.Column(db.JSON)
    preferred_directors = db.Column(db.JSON)
    preferred_actors = db.Column(db.JSON)
    preferred_decade = db.Column(db.String(10))
    watch_time_pattern = db.Column(db.String(20))
    last_updated = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
