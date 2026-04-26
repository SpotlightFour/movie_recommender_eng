import random
import re
import os
import time
from typing import List, Dict, Any

import numpy as np
from flask import Flask
from flask_cors import CORS
from peft import PeftConfig
import requests
import torch
from bs4 import BeautifulSoup
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

from evaluatorTest import Evaluator
from models import Movie, UserProfile, UserRating, UserAction, db
from profile_builder import ProfileBuilder
from recommender import HybridRecommender

SECRET_KEY = 1

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:admin123@localhost/movie_recommender'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY

db.init_app(app)
print(f"CUDA可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU设备: {torch.cuda.get_device_name(0)}")
    print(f"显存总量: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")

# 配置CORS，允许前端访问
CORS(app)

# 延迟初始化推荐器
hybrid_recommender = HybridRecommender()
profile_builder = ProfileBuilder()

# IMDb配置
IMDB_BASE_URL = "https://www.imdb.com"

# 加载本地模型
try:
    model_dir = "./qwen_models"
    if not os.path.exists(model_dir):
        print(f"模型目录不存在: {model_dir}")
        text_generator = None
    else:
        print(f"从目录加载模型: {model_dir}")
        tokenizer = AutoTokenizer.from_pretrained(
            model_dir,
            trust_remote_code=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_dir,
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=True
        )
        text_generator = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            device=0 if torch.cuda.is_available() else -1,
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            max_new_tokens=200,
            min_new_tokens=10,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
        )
        print("本地模型加载成功")
except Exception as e:
    print(f"加载本地模型失败: {str(e)}")
    text_generator = None

# class IMDbClient:
#     """IMDb客户端 - 通过网页爬取获取电影数据"""
#
#     def __init__(self):
#         self.base_url = "https://www.imdb.com"
#         self.headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
#             'Accept-Language': 'en-US,en;q=0.9',
#             'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
#             'Referer': 'https://www.imdb.com/'
#         }
#
#     def search_movie(self, title):
#         """搜索电影"""
#         try:
#             # 清理标题
#             clean_title = re.sub(r'\(.*?\)', '', title).strip()
#             clean_title = re.sub(r'[^\w\s]', ' ', clean_title)
#
#             search_url = f"{self.base_url}/find"
#             params = {
#                 'q': clean_title,
#                 's': 'tt'  # 搜索标题
#             }
#
#             response = requests.get(search_url, params=params, headers=self.headers, timeout=10)
#             response.raise_for_status()
#
#             soup = BeautifulSoup(response.text, 'html.parser')
#
#             # 查找第一个搜索结果
#             result_link = soup.find('a', href=re.compile(r'/title/tt\d+'))
#             if result_link:
#                 href = result_link.get('href', '')
#                 imdb_id_match = re.search(r'/title/(tt\d+)/', href)
#                 if imdb_id_match:
#                     imdb_id = imdb_id_match.group(1)
#                     return self.get_movie_details(imdb_id)
#
#             return None
#         except Exception as e:
#             print(f"IMDb搜索失败: {str(e)}")
#             return None
#
#     def get_movie_details(self, imdb_id):
#         """获取电影详细信息"""
#         try:
#             url = f"{self.base_url}/title/{imdb_id}/"
#             response = requests.get(url, headers=self.headers, timeout=10)
#             response.raise_for_status()
#
#             soup = BeautifulSoup(response.text, 'html.parser')
#             return self._parse_movie_page(soup, imdb_id)
#
#         except Exception as e:
#             print(f"获取电影详情失败: {str(e)}")
#             return None
#
#     def _parse_movie_page(self, soup, imdb_id):
#         """解析IMDb电影页面"""
#         movie_data = {}
#
#         # 提取标题
#         title_element = soup.find('h1')
#         movie_data['title'] = title_element.get_text(strip=True) if title_element else "未知标题"
#
#         # 提取原始标题
#         original_title_element = soup.find('div', {'data-testid': 'hero-title-block__original-title'})
#         if original_title_element:
#             original_text = original_title_element.get_text(strip=True)
#             # 移除"Original title: "前缀
#             movie_data['original_title'] = original_text.replace('Original title: ', '')
#         else:
#             movie_data['original_title'] = movie_data['title']
#
#         # 提取发行年份
#         year_element = soup.find('a', href=re.compile(r'/search/title\?year='))
#         if year_element:
#             year_text = year_element.get_text(strip=True)
#             year_match = re.search(r'\d{4}', year_text)
#             movie_data['release_year'] = year_match.group(0) if year_match else "未知年份"
#         else:
#             movie_data['release_year'] = "未知年份"
#
#         # 提取导演信息
#         directors = []
#         director_section = soup.find('a', href=re.compile(r'/name/nm\d+/'))
#         if director_section:
#             # 查找导演名称
#             director_name = director_section.get_text(strip=True)
#             if director_name and director_name not in ['Director', 'Stars']:
#                 directors.append(director_name)
#
#         # 备用方法查找导演
#         if not directors:
#             director_elements = soup.select('[data-testid="title-pc-principal-credit"]')
#             for element in director_elements:
#                 if 'Director' in element.get_text():
#                     director_links = element.find_all('a')
#                     for link in director_links:
#                         name = link.get_text(strip=True)
#                         if name and name not in ['Director', 'Stars']:
#                             directors.append(name)
#                             break
#
#         movie_data['directors'] = directors
#
#         # 提取演员信息
#         actors = []
#         cast_section = soup.find('div', {'data-testid': 'title-cast'})
#         if cast_section:
#             actor_elements = cast_section.find_all('a', href=re.compile(r'/name/nm\d+/'))
#             for actor in actor_elements[:6]:  # 取前6个主要演员
#                 actor_name = actor.get_text(strip=True)
#                 if actor_name and actor_name not in ['Director', 'Stars']:
#                     actors.append(actor_name)
#
#         # 备用方法查找演员
#         if not actors:
#             actor_elements = soup.select('a[data-testid="title-cast-item__actor"]')
#             for actor in actor_elements[:6]:
#                 actor_name = actor.get_text(strip=True)
#                 if actor_name:
#                     actors.append(actor_name)
#
#         movie_data['actors'] = actors
#
#         # 提取类型
#         genres = []
#         genre_elements = soup.find_all('a', href=re.compile(r'/search/title\?genres='))
#         for genre_element in genre_elements:
#             genre = genre_element.get_text(strip=True)
#             if genre and genre not in genres:
#                 genres.append(genre)
#         movie_data['genres'] = genres
#
#         # 提取剧情简介
#         description = "暂无描述"
#         plot_element = soup.find('span', {'data-testid': 'plot-l'})
#         if plot_element:
#             description = plot_element.get_text(strip=True)
#         else:
#             plot_element = soup.find('div', class_=re.compile(r'.*summary.*'))
#             if plot_element:
#                 description = plot_element.get_text(strip=True)
#
#         movie_data['overview'] = description
#
#         # 提取海报URL
#         poster_url = ""
#         meta_image = soup.find('meta', property='og:image')
#         if meta_image and 'content' in meta_image.attrs:
#             poster_url = meta_image['content']
#         else:
#             poster_element = soup.find('img', class_=re.compile(r'.*poster.*'))
#             if poster_element and 'src' in poster_element.attrs:
#                 poster_url = poster_element['src']
#
#         movie_data['poster_url'] = poster_url
#
#         # 提取评分信息
#         rating_element = soup.find('span', {'data-testid': 'rating'})
#         if rating_element:
#             rating_text = rating_element.get_text(strip=True)
#             try:
#                 movie_data['vote_average'] = float(rating_text)
#             except:
#                 movie_data['vote_average'] = 0
#         else:
#             movie_data['vote_average'] = 0
#
#         # 提取评分人数
#         rating_count_element = soup.find('div', {'data-testid': 'rating-count'})
#         if rating_count_element:
#             count_text = rating_count_element.get_text(strip=True)
#             count_match = re.search(r'(\d+,?\d*)', count_text.replace(',', ''))
#             if count_match:
#                 movie_data['vote_count'] = int(count_match.group(1))
#             else:
#                 movie_data['vote_count'] = 0
#         else:
#             movie_data['vote_count'] = 0
#
#         # 提取时长
#         runtime_element = soup.find('li', {'data-testid': 'title-techspec_runtime'})
#         if runtime_element:
#             runtime_text = runtime_element.get_text(strip=True)
#             runtime_match = re.search(r'(\d+)', runtime_text)
#             if runtime_match:
#                 movie_data['runtime'] = int(runtime_match.group(1))
#             else:
#                 movie_data['runtime'] = 0
#         else:
#             movie_data['runtime'] = 0
#
#         movie_data['imdb_id'] = imdb_id
#
#         return movie_data
#
#     def format_movie_info(self, imdb_data):
#         """格式化IMDb数据为统一格式"""
#         if not imdb_data:
#             return None
#
#         return {
#             'title': imdb_data.get('title', ''),
#             'original_title': imdb_data.get('original_title', ''),
#             'release_year': imdb_data.get('release_year', ''),
#             'director': ', '.join(imdb_data.get('directors', [])),
#             'genres': imdb_data.get('genres', []),
#             'overview': imdb_data.get('overview', '暂无描述'),
#             'poster_url': imdb_data.get('poster_url', ''),
#             'actors': imdb_data.get('actors', []),
#             'vote_average': imdb_data.get('vote_average', 0),
#             'vote_count': imdb_data.get('vote_count', 0),
#             'runtime': imdb_data.get('runtime', 0),
#             'source': 'imdb'
#         }


class ImprovedIMDbClient:
    """改进的IMDb客户端，使用更稳定的解析方法"""

    def __init__(self):
        self.base_url = "https://www.imdb.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Referer': 'https://www.imdb.com/',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def search_movie(self, title):
        """改进的电影搜索方法"""
        try:
            # 清理标题，提高搜索准确性
            clean_title = self._clean_title(title)

            # 使用更精确的搜索URL
            search_url = f"{self.base_url}/find"
            params = {
                'q': clean_title,
                's': 'tt',
                'ttype': 'ft'  # 限制为电影类型
            }

            response = self.session.get(search_url, params=params, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 多种方式查找结果链接
            result_link = self._find_result_link(soup)

            if result_link:
                imdb_id = self._extract_imdb_id(result_link)
                if imdb_id:
                    # 添加随机延迟，避免被反爬
                    time.sleep(random.uniform(1, 3))
                    return self.get_movie_details(imdb_id)

            return None

        except Exception as e:
            print(f"IMDb搜索失败: {str(e)}")
            return None

    def _clean_title(self, title):
        """清理电影标题"""
        # 移除括号内容
        clean_title = re.sub(r'\(.*?\)', '', title)
        # 移除特殊字符但保留空格
        clean_title = re.sub(r'[^\w\s]', ' ', clean_title)
        # 合并多个空格
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        return clean_title

    def _find_result_link(self, soup):
        """多种方式查找结果链接"""
        # 方式1: 查找主要结果区域
        result_section = soup.find('section', {'data-testid': 'find-results-section-title'})
        if result_section:
            link = result_section.find('a', href=re.compile(r'/title/tt\d+'))
            if link:
                return link.get('href')

        # 方式2: 查找表格行中的链接
        table_rows = soup.find_all('tr', class_='findResult')
        for row in table_rows:
            link = row.find('a', href=re.compile(r'/title/tt\d+'))
            if link:
                return link.get('href')

        # 方式3: 直接查找所有可能的链接
        links = soup.find_all('a', href=re.compile(r'/title/tt\d+'))
        for link in links:
            href = link.get('href')
            if href and '/title/tt' in href and 'name' not in href:
                return href

        return None

    def _extract_imdb_id(self, href):
        """从链接中提取IMDb ID"""
        match = re.search(r'/title/(tt\d+)', href)
        return match.group(1) if match else None

    def get_movie_details(self, imdb_id):
        """获取电影详细信息，使用多种解析策略"""
        try:
            url = f"{self.base_url}/title/{imdb_id}/"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 尝试多种解析策略
            movie_data = self._parse_with_json_ld(soup, imdb_id)
            if not movie_data or not movie_data.get('title'):
                movie_data = self._parse_with_metadata(soup, imdb_id)

            if not movie_data or not movie_data.get('title'):
                movie_data = self._parse_traditional(soup, imdb_id)

            return movie_data

        except Exception as e:
            print(f"获取电影详情失败: {str(e)}")
            return None

    def _parse_with_json_ld(self, soup, imdb_id):
        """使用JSON-LD结构化数据解析（最可靠）"""
        try:
            script_tag = soup.find('script', type='application/ld+json')
            if not script_tag:
                return None

            import json
            data = json.loads(script_tag.string)

            movie_data = {
                'title': data.get('name', ''),
                'original_title': data.get('name', ''),
                'release_year': data.get('datePublished', '')[:4] if data.get('datePublished') else '',
                'directors': [],
                'actors': [],
                'genres': data.get('genre', []),
                'overview': data.get('description', '暂无描述'),
                'poster_url': data.get('image', ''),
                'vote_average': 0,
                'vote_count': 0,
                'runtime': 0,
                'imdb_id': imdb_id
            }

            # 处理导演信息
            director = data.get('director')
            if director:
                if isinstance(director, list):
                    movie_data['directors'] = [d.get('name', '') for d in director if d.get('name')]
                else:
                    movie_data['directors'] = [director.get('name', '')] if director.get('name') else []

            # 处理演员信息
            actors = data.get('actor', [])
            if actors:
                if isinstance(actors, list):
                    movie_data['actors'] = [a.get('name', '') for a in actors[:6] if a.get('name')]
                else:
                    movie_data['actors'] = [actors.get('name', '')] if actors.get('name') else []

            # 处理评分
            aggregate_rating = data.get('aggregateRating', {})
            if aggregate_rating:
                movie_data['vote_average'] = aggregate_rating.get('ratingValue', 0)
                movie_data['vote_count'] = aggregate_rating.get('ratingCount', 0)

            # 处理时长
            duration = data.get('duration', '')
            if duration:
                # 解析ISO 8601时长格式
                match = re.search(r'PT(\d+)M', duration)
                if match:
                    movie_data['runtime'] = int(match.group(1))

            print(f"✅ 通过JSON-LD成功解析: {movie_data['title']}")
            return movie_data

        except Exception as e:
            print(f"JSON-LD解析失败: {str(e)}")
            return None

    def _parse_crew_info(self, soup):
        """导演和演员信息解析"""
        crew_data = {'directors': [], 'actors': []}

        try:
            # 使用您提供的代码段提取导演
            directors = []
            director_links = soup.find_all('a', href=re.compile(r'/name/nm\d+/'))

            for director_link in director_links:
                director_name = director_link.get_text(strip=True)
                if (director_name and
                        director_name not in ['Director', 'Stars'] and
                        len(director_name) > 1):  # 确保不是单个字符
                    directors.append(director_name)

            # 去重
            directors = list(dict.fromkeys(directors))

            # 限制导演数量（通常1-2个）
            crew_data['directors'] = directors[:2]

            # 提取演员信息（类似方法）
            actors = []
            actor_links = soup.find_all('a', href=re.compile(r'/name/nm\d+/'))

            for actor_link in actor_links:
                actor_name = actor_link.get_text(strip=True)
                if (actor_name and
                        actor_name not in ['Director', 'Stars'] and
                        actor_name not in directors and  # 避免重复
                        len(actor_name) > 1 and
                        len(actors) < 6):  # 限制演员数量
                    actors.append(actor_name)

            crew_data['actors'] = actors

            print(f"🎬 提取到导演: {crew_data['directors']}")
            print(f"🎭 提取到演员: {crew_data['actors']}")

        except Exception as e:
            print(f"解析演职员信息失败: {str(e)}")

        return crew_data

    def _parse_with_metadata(self, soup, imdb_id):
        """改进的meta标签解析"""
        movie_data = {'imdb_id': imdb_id}

        try:
            # 标题
            title_meta = soup.find('meta', property='og:title')
            if title_meta:
                movie_data['title'] = title_meta['content']
            else:
                # 备用标题提取
                title_element = soup.find('h1')
                if title_element:
                    title_text = title_element.get_text(strip=True)
                    # 移除年份信息
                    movie_data['title'] = re.sub(r'\s*\(\d{4}\)\s*', '', title_text)

            # 原始标题（与标题相同）
            movie_data['original_title'] = movie_data.get('title', '')

            # 年份提取
            year_match = re.search(r'\((\d{4})\)', soup.get_text())
            if year_match:
                movie_data['release_year'] = year_match.group(1)
            else:
                # 从URL或meta信息中提取年份
                year_meta = soup.find('meta', property='og:title')
                if year_meta:
                    year_match = re.search(r'\((\d{4})\)', year_meta['content'])
                    if year_match:
                        movie_data['release_year'] = year_match.group(1)

            # 描述
            desc_meta = soup.find('meta', property='og:description')
            movie_data['overview'] = desc_meta['content'] if desc_meta else '暂无描述'

            # 海报
            image_meta = soup.find('meta', property='og:image')
            movie_data['poster_url'] = image_meta['content'] if image_meta else ''

            # 使用改进的crew解析
            crew_data = self._parse_crew_info(soup)
            movie_data.update(crew_data)

            # 类型信息
            movie_data['genres'] = self._parse_genres(soup)

            # 评分信息
            movie_data.update(self._parse_ratings(soup))

            if movie_data.get('title'):
                print(f"✅ 通过meta标签成功解析: {movie_data['title']}")
                return movie_data

        except Exception as e:
            print(f"meta标签解析失败: {str(e)}")

        return None

    def _parse_genres(self, soup):
        """解析电影类型"""
        genres = []
        try:
            # 多种方式查找类型信息
            genre_links = soup.find_all('a', href=re.compile(r'/search/title\?genres='))
            for link in genre_links:
                genre = link.get_text(strip=True)
                if genre and genre not in genres:
                    genres.append(genre)

            # 从meta标签查找
            genre_meta = soup.find('meta', property='og:genre')
            if genre_meta and genre_meta.get('content'):
                genres.extend([g.strip() for g in genre_meta['content'].split(',')])

        except Exception as e:
            print(f"解析类型失败: {str(e)}")

        return list(set(genres))[:5]  # 去重并限制数量

    def _parse_ratings(self, soup):
        """解析评分信息"""
        ratings = {'vote_average': 0, 'vote_count': 0}

        try:
            # 评分值
            rating_element = soup.find('span', class_=re.compile(r'.*rating.*'))
            if rating_element:
                rating_text = rating_element.get_text()
                match = re.search(r'(\d+\.?\d*)', rating_text)
                if match:
                    ratings['vote_average'] = float(match.group(1))

            # 评分人数
            count_element = soup.find('span', class_=re.compile(r'.*count.*'))
            if count_element:
                count_text = count_element.get_text()
                match = re.search(r'([\d,]+)', count_text.replace(',', ''))
                if match:
                    ratings['vote_count'] = int(match.group(1))

        except Exception as e:
            print(f"解析评分失败: {str(e)}")

        return ratings

    def _parse_traditional(self, soup, imdb_id):
        """传统解析方法（备用）"""
        movie_data = {'imdb_id': imdb_id}

        try:
            # 基本标题信息
            title_element = soup.find('h1')
            if title_element:
                title_text = title_element.get_text(strip=True)
                movie_data['title'] = re.sub(r'\s*\(\d{4}\)\s*', '', title_text)

                # 提取年份
                year_match = re.search(r'\((\d{4})\)', title_text)
                movie_data['release_year'] = year_match.group(1) if year_match else ''

            # 这里可以添加更多的传统解析逻辑...

        except Exception as e:
            print(f"传统解析失败: {str(e)}")

        return movie_data if movie_data.get('title') else None

    def format_movie_info(self, imdb_data):
        """格式化IMDb数据为统一格式"""
        if not imdb_data:
            return None
        directors = imdb_data.get('directors', [])
        return {
            'title': imdb_data.get('title', ''),
            'original_title': imdb_data.get('original_title', imdb_data.get('title', '')),
            'release_year': imdb_data.get('release_year', ''),
            'director': ', '.join(directors),
            'genres': imdb_data.get('genres', []),
            'overview': imdb_data.get('overview', '暂无描述'),
            'poster_url': imdb_data.get('poster_url', ''),
            'actors': imdb_data.get('actors', []),
            'vote_average': imdb_data.get('vote_average', 0),
            'vote_count': imdb_data.get('vote_count', 0),
            'runtime': imdb_data.get('runtime', 0),
            'source': 'imdb'
        }


class ExplanationAgent:
    """智能体：生成个性化电影推荐解释"""

    def __init__(self, recommender, profile_builder,
                 base_model_path="./qwen_models"):
        self.recommender = recommender
        self.profile_builder = profile_builder
        self.imdb_client = ImprovedIMDbClient()

        # 初始化评估器
        self.evaluator = Evaluator()

        # 模型路径配置
        self.base_model_path = base_model_path

        # 为三种解释类型分别指定LoRA适配器路径
        self.lora_adapter_paths = {
            1: './fine_tuning/tuneForAbstract/lora_results',  # Why(abstract)解释
            2: './fine_tuning/tuneForDetailed/lora_results',  # Why(detailed)解释
            3: './fine_tuning/tuneForHow/lora_results'  # How解释
        }

        # 模型实例字典，按解释类型存储
        self.models = {}  # {explanation_type: model}
        self.tokenizers = {}  # {explanation_type: tokenizer}

        # 加载所有模型
        self._load_all_models()

    def _load_all_models(self):
        """为所有解释类型加载对应的模型并合并LoRA适配器"""
        try:
            print("开始加载所有解释类型的模型并合并LoRA适配器...")

            # 首先加载基础模型和分词器
            print("加载基础模型和分词器...")
            base_tokenizer = AutoTokenizer.from_pretrained(
                self.base_model_path,
                trust_remote_code=True
            )

            if base_tokenizer.pad_token is None:
                base_tokenizer.pad_token = base_tokenizer.eos_token

            base_model = AutoModelForCausalLM.from_pretrained(
                self.base_model_path,
                dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True
            )

            # 将基础模型设置为默认模型
            self.models['base'] = base_model
            self.tokenizers['base'] = base_tokenizer
            print("基础模型加载成功")

            # 为每种解释类型加载对应的LoRA适配器并合并
            for exp_type, lora_path in self.lora_adapter_paths.items():
                model_name = self._get_explanation_type_name(exp_type)
                print(f"加载并合并{model_name}的LoRA适配器...")

                if os.path.exists(lora_path):
                    try:
                        # 检查LoRA适配器配置
                        config = PeftConfig.from_pretrained(lora_path)
                        print(f"LoRA适配器配置: r={config.r}, alpha={config.lora_alpha}")

                        # 为每个解释类型创建一个新的基础模型实例
                        model = AutoModelForCausalLM.from_pretrained(
                            self.base_model_path,
                            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                            device_map="auto" if torch.cuda.is_available() else None,
                            trust_remote_code=True
                        )

                        # 加载LoRA适配器
                        model = PeftModel.from_pretrained(model, lora_path)

                        # 默认合并适配器以获得更好的推理性能
                        print("合并LoRA适配器...")
                        model = model.merge_and_unload()

                        # 保存合并后的模型和分词器
                        self.models[exp_type] = model
                        self.tokenizers[exp_type] = base_tokenizer  # 使用基础分词器

                        print(f"{model_name}模型加载并合并成功")

                    except Exception as e:
                        print(f"加载并合并{model_name}LoRA适配器失败: {str(e)}")
                        # 使用基础模型作为回退
                        self.models[exp_type] = base_model
                        self.tokenizers[exp_type] = base_tokenizer
                        print(f"{model_name}将使用基础模型")
                else:
                    print(f"未找到{model_name}的LoRA适配器路径: {lora_path}")
                    # 使用基础模型作为回退
                    self.models[exp_type] = base_model
                    self.tokenizers[exp_type] = base_tokenizer
                    print(f"{model_name}将使用基础模型")

            print("所有模型加载和合并完成")

        except Exception as e:
            print(f"加载模型失败: {str(e)}")
            import traceback
            traceback.print_exc()
            # 设置回退方案
            self.models = {}
            self.tokenizers = {}

    def _get_explanation_type_name(self, explanation_type):
        """获取解释类型名称"""
        names = {
            1: "Why(abstract)解释",
            2: "Why(detailed)解释",
            3: "How解释"
        }
        return names.get(explanation_type, f"类型{explanation_type}")

    def _get_model_for_explanation(self, explanation_type):
        """获取指定解释类型对应的模型和分词器"""
        # 优先使用该解释类型的专用模型
        if explanation_type in self.models:
            return self.models[explanation_type], self.tokenizers[explanation_type]

        # 回退到基础模型
        if 'base' in self.models:
            return self.models['base'], self.tokenizers['base']

        # 如果都没有，返回None
        return None, None

    def _generate_with_model(self, prompt, explanation_type, max_new_tokens=300):
        """使用指定解释类型的专用模型生成解释"""
        try:
            # 获取对应解释类型的模型和分词器
            model, tokenizer = self._get_model_for_explanation(explanation_type)

            if model is None or tokenizer is None:
                return self._get_fallback_explanation(explanation_type)

            model_name = self._get_explanation_type_name(explanation_type)
            print(f"使用{model_name}专用模型生成解释")

            # 根据设备类型准备输入
            if torch.cuda.is_available():
                inputs = tokenizer(prompt, return_tensors="pt", padding=True, truncation=True, max_length=512).to(
                    model.device)
            else:
                inputs = tokenizer(prompt, return_tensors="pt", padding=True, truncation=True, max_length=512)

            # 根据解释类型调整生成长度
            token_lengths = {
                1: 200,  # "Why(abstract)解释"
                2: 400,  # "Why(detailed)解释"
                3: 300  # "How解释"
            }
            max_tokens = token_lengths.get(explanation_type, 300)

            # 生成文本
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

            return generated_text

        except Exception as e:
            print(f"模型生成失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._get_fallback_explanation(explanation_type)

    def generate_explanation(self, user_id, movie_title, explanation_type, predicted_rating):
        """智能体主方法：生成个性化解释"""
        try:
            # 步骤1: 获取电影信息
            movie_info = self._get_movie_info(movie_title)
            if not movie_info:
                print(f"未找到电影信息: {movie_title}")
                return self._get_fallback_explanation(explanation_type)

            print(f"找到电影: {movie_info['title']}, 导演: {movie_info.get('director', '未知')}")

            # 步骤2: 生成提示词
            prompt = self._generate_prompt(user_id, movie_info, explanation_type, predicted_rating)
            print(f"生成的提示词长度: {len(prompt)}")

            # 步骤3: 调用对应解释类型的专用模型生成解释
            explanation = self._generate_with_model(prompt, explanation_type)
            explanation = "I notice that you have a particular fondness for director Nolan's works. The action sequences in Inception are as captivating as those in Forrest Gump."
            evaluation_results = self.evaluate_explanation(user_id, movie_title, explanation, explanation_type)
            print(
                f"评估完成 - PSS: {evaluation_results.get('pss_score', 0):.4f}, CRA: {evaluation_results.get('cra_score', 0):.4f}")
            # 特殊处理类型3的流程图
            # if explanation_type == 3:
            #     explanation = self._convert_steps_to_mermaid(user_id, movie_info['title'], predicted_rating,
            #                                                  explanation)

            print(f"生成解释成功，类型: {explanation_type}")
            return explanation if explanation else self._get_fallback_explanation(explanation_type)

        except Exception as e:
            print(f"生成解释失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._get_fallback_explanation(explanation_type)

    def _get_fallback_explanation(self, explanation_type):
        """回退解释"""
        fallback_explanations = {
            1: "根据您的观影偏好，我们为您推荐了这部电影。",
            2: "这是一部值得观看的优秀电影，具有独特的艺术价值。",
            3: "推荐系统基于内容分析和用户偏好匹配为您选择了这部电影。"
        }
        return fallback_explanations.get(explanation_type, "我们为您推荐了这部电影。")

    def _get_user_sequence(self, user_id, max_length=50):
        """获取用户历史序列（电影标题列表）"""
        try:
            # 获取评分记录
            ratings = UserRating.query.filter_by(user_id=user_id) \
                .order_by(UserRating.rated_at.desc()) \
                .limit(max_length).all()

            sequence = []
            for rating in ratings:
                movie = Movie.query.get(rating.movie_id)
                if movie:
                    sequence.append(movie.title)

            # 如果不足，从行为中获取
            if len(sequence) < max_length:
                actions = UserAction.query.filter_by(user_id=user_id) \
                    .filter(UserAction.movie_id.isnot(None)) \
                    .order_by(UserAction.action_time.desc()) \
                    .limit(max_length - len(sequence)).all()

                for action in actions:
                    movie = Movie.query.get(action.movie_id)
                    if movie:
                        sequence.append(movie.title)

            return sequence[:max_length]
        except Exception as e:
            print(f"获取用户序列失败: {str(e)}")
            return []

    def _get_user_preferences(self, user_id):
        """获取用户偏好列表"""
        try:
            profile = UserProfile.query.filter_by(user_id=user_id).first()
            if profile and profile.favorite_genres:
                # 按偏好分数排序
                sorted_genres = sorted(profile.favorite_genres.items(), key=lambda x: x[1], reverse=True)
                preferences = [genre for genre, score in sorted_genres[:3]]  # 取前3个偏好
                return preferences
            else:
                # 如果没有偏好数据，返回默认
                return ['动作', '喜剧', '剧情']
        except Exception as e:
            print(f"获取用户偏好失败: {str(e)}")
            return ['动作', '喜剧', '剧情']

    def _get_preference_weights(self, user_id, preferences):
        """获取偏好权重列表"""
        try:
            profile = UserProfile.query.filter_by(user_id=user_id).first()
            weights = []
            if profile and profile.favorite_genres:
                for pref in preferences:
                    weight = profile.favorite_genres.get(pref, 0.1)
                    weights.append(weight)
                # 归一化
                total = sum(weights)
                if total > 0:
                    weights = [w / total for w in weights]
                else:
                    weights = [1 / len(preferences)] * len(preferences)
            else:
                weights = [1 / len(preferences)] * len(preferences)
            return weights
        except Exception as e:
            print(f"获取偏好权重失败: {str(e)}")
            return [1 / len(preferences)] * len(preferences)

    def _get_movie_info(self, movie_title):
        """获取电影信息（优先在线搜索，失败时使用数据库）"""
        # 首先尝试在线搜索
        online_info = self._search_movie_online(movie_title)
        if online_info:
            return online_info

        # 在线搜索失败时，回退到数据库查询
        print("在线搜索失败，尝试从数据库查询")
        try:
            movie = Movie.query.filter(Movie.title.ilike(f"%{movie_title}%")).first()
            if movie:
                # 计算电影的平均评分
                from models import UserRating
                ratings = UserRating.query.filter_by(movie_id=movie.id).all()

                if ratings:
                    total_rating = sum(r.rating for r in ratings)
                    average_rating = total_rating / len(ratings)
                else:
                    average_rating = 0

                return {
                    'title': movie.title,
                    'director': movie.director or "未知导演",
                    'genres': movie.genres.split(',') if movie.genres else ["未知类型"],
                    'release_year': movie.release_year or "未知年份",
                    'overview': movie.description or "暂无描述",
                    'actors': movie.actors.split(',') if movie.actors else [],
                    'vote_average': round(average_rating, 1),  # 使用实际平均评分
                    'vote_count': len(ratings),  # 使用实际评分人数
                    'source': 'database'
                }
            return None
        except Exception as e:
            print(f"数据库查询失败: {str(e)}")
            return None

    def _search_movie_online(self, movie_title):
        """从网上搜索电影信息"""
        if not self.imdb_client:
            print("IMDB客户端未初始化，无法进行网络搜索")
            return None

        try:
            print(f"正在从IMDB搜索电影: {movie_title}")
            movie_data = self.imdb_client.search_movie(movie_title)
            if movie_data:
                formatted_data = self.imdb_client.format_movie_info(movie_data)
                print(f"找到在线电影信息: {formatted_data['title']}")
                return formatted_data
            return None
        except Exception as e:
            print(f"在线搜索电影失败: {str(e)}")
            return None

    def _generate_prompt(self, user_id, movie_info, explanation_type, predicted_rating):

        """生成思维链提示词"""
        # 获取用户历史序列
        user_sequence = self._get_user_sequence(user_id, 20)

        # 获取用户偏好和权重
        preferences = self._get_user_preferences(user_id)
        preference_weights = self._get_preference_weights(user_id, preferences)

        hybrid_recommender = HybridRecommender()
        # 1. 首先尝试精确匹配（不区分大小写）
        movie = Movie.query.filter(Movie.title.ilike(movie_info.get('title'))).first()
        user_profile = UserProfile.query.filter(UserProfile.user_id).first
        if movie:
            # 计算各类型匹配得分
            # 类型匹配加分
            genre_bonus = hybrid_recommender._calculate_genre_bonus(movie, user_profile)

            # 年代匹配加分
            year_bonus = hybrid_recommender._calculate_year_bonus(movie, user_profile)

            # 导演匹配加分（如果有用户画像中的导演信息）
            director_bonus = hybrid_recommender._calculate_director_bonus(movie, user_profile)

            # 演员匹配加分（如果有用户画像中的演员信息）
            actor_bonus = hybrid_recommender._calculate_actor_bonus(movie, user_profile)
        else:
            # 2. 精确匹配失败，尝试使用数据库的LIKE进行模糊匹配
            movie = Movie.query.filter(Movie.title.like(f"%{movie_info.get('title')}%")).first()

            # 计算各类型匹配得分
            # 类型匹配加分
            genre_bonus = hybrid_recommender._calculate_genre_bonus(movie, user_profile)

            # 年代匹配加分
            year_bonus = hybrid_recommender._calculate_year_bonus(movie, user_profile)

            # 导演匹配加分（如果有用户画像中的导演信息）
            director_bonus = hybrid_recommender._calculate_director_bonus(movie, user_profile)

            # 演员匹配加分（如果有用户画像中的演员信息）
            actor_bonus = hybrid_recommender._calculate_actor_bonus(movie, user_profile)

        # 计算总评分
        total_score = genre_bonus + year_bonus + director_bonus + actor_bonus
        # 构建偏好权重信息
        pref_weight_info = []
        for i, (pref, weight) in enumerate(zip(preferences, preference_weights)):
            pref_weight_info.append(f"{pref}: {weight:.3f}")

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
类型得分: {genre_bonus}/3.0]
导演得分: {director_bonus}/0.8]
演员得分: {actor_bonus}/1.0]
年代得分: {year_bonus}/0.2]
总得分: {total_score}
平均评分: {movie_info.get('vote_average', 0)}/5"""

        # 根据解释类型调整提示词
        if explanation_type == 1:
            # Why(abstract）解释：要求简短精炼
            return f"""【思考框架-不输出】
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

        elif explanation_type == 2:
            # 论证解释：要求详细分析
            return f"""【思考框架-不输出】
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

        elif explanation_type == 3:
            # Why(abstract）解释：要求步骤清晰
            return f"""【思考框架-不输出】
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
    E --> I[类型得分: {genre_bonus}/3.0]
    F --> J[导演得分: {director_bonus}/0.8]
    G --> K[演员得分: {actor_bonus}/1.0]
    H --> L[年代得分: {year_bonus}/0.2]
    I --> M[得分汇总]
    J --> M
    K --> M
    L --> M
    M --> N[计算原始总分: {total_score}]
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

    def evaluate_explanation(self, user_id: int, movie_title: str, explanation: str,
                             explanation_type: int) -> Dict[str, Any]:
        """
        评估生成的解释质量

        参数:
        - user_id: 用户ID
        - movie_title: 电影标题
        - explanation: 生成的解释文本
        - explanation_type: 解释类型（1,2,3）

        返回:
        - 包含PSS和CRA分数的字典
        """
        try:
            # 获取评估所需的上下文和因果因素
            context_items = self._get_evaluation_context(user_id, movie_title, explanation_type)
            causal_factors = self._get_evaluation_causal_factors(user_id, movie_title, explanation_type)

            # 使用Evaluator进行评估
            pss_score, cra_score = self.evaluator.evaluate(
                explanation=explanation,
                context=context_items,
                causal=causal_factors,
                threshold=0.7
            )

            return {
                'pss_score': round(pss_score, 4),
                'cra_score': round(cra_score, 4),
                'explanation_type': explanation_type,
                'user_id': user_id,
                'movie_title': movie_title,
                'context_items_count': len(context_items),
                'causal_factors_count': len(causal_factors),
                'evaluation_success': True
            }

        except Exception as e:
            print(f"解释评估失败: {str(e)}")
            return {
                'pss_score': 0.0,
                'cra_score': 0.0,
                'explanation_type': explanation_type,
                'user_id': user_id,
                'movie_title': movie_title,
                'error': str(e),
                'evaluation_success': False
            }

    def _get_evaluation_context(self, user_id: int, movie_title: str, explanation_type: int = None) -> List[str]:
        """
        为PSS评估构建上下文项目，根据解释类型调整详细程度
        """
        context_items = []

        try:
            # 获取用户偏好和电影信息（基础信息）
            preferences = self._get_user_preferences(user_id)
            movie_info = self._get_movie_info(movie_title)

            # 针对解释类型2（详细论证）提供更丰富的信息
            if explanation_type == 2:
                # 详细版本 - 适合论证解释
                user_sequence = self._get_user_sequence(user_id, max_length=10)  # 更多历史记录

                # 1. 详细的历史观影信息
                if user_sequence:
                    context_items.append(f"用户最近观看了{len(user_sequence)}部电影")
                    recent_movies = user_sequence[:5]
                    context_items.append(f"最近观看的电影包括：{', '.join([f'《{m}》' for m in recent_movies])}")

                # 2. 详细的偏好信息（带权重）
                if preferences:
                    preference_weights = self._get_preference_weights(user_id, preferences)
                    pref_details = []
                    for pref, weight in zip(preferences[:3], preference_weights[:3]):
                        pref_details.append(f"{pref}(权重:{weight:.2f})")
                    context_items.append(f"用户主要偏好：{', '.join(pref_details)}")

                # 3. 详细的电影信息
                if movie_info:
                    # 基本特征
                    context_items.extend([
                        f"推荐电影《{movie_info.get('title', '未知')}》",
                        f"导演：{movie_info.get('director', '未知')}",
                        f"类型：{', '.join(movie_info.get('genres', []))}",
                        f"IMDb评分：{movie_info.get('vote_average', 0)}/10（基于{movie_info.get('vote_count', 0)}人评分）"
                    ])

                    # 主要演员信息
                    actors = movie_info.get('actors', [])
                    if actors:
                        context_items.append(f"主要演员：{', '.join(actors[:4])}")

                # 4. 推荐系统分析信息（针对类型2）
                hybrid_recommender = HybridRecommender()
                user_profile = UserProfile.query.filter_by(user_id=user_id).first()
                movie_obj = Movie.query.filter(Movie.title.ilike(movie_info.get('title', ''))).first()

                if movie_obj and user_profile:
                    # 计算各项匹配分数
                    genre_bonus = hybrid_recommender._calculate_genre_bonus(movie_obj, user_profile)
                    year_bonus = hybrid_recommender._calculate_year_bonus(movie_obj, user_profile)
                    director_bonus = hybrid_recommender._calculate_director_bonus(movie_obj, user_profile)
                    actor_bonus = hybrid_recommender._calculate_actor_bonus(movie_obj, user_profile)
                    total_score = genre_bonus + year_bonus + director_bonus + actor_bonus

                    context_items.extend([
                        f"类型匹配得分：{genre_bonus:.2f}/3.0",
                        f"导演匹配得分：{director_bonus:.2f}/0.8",
                        f"演员匹配得分：{actor_bonus:.2f}/1.0",
                        f"年代匹配得分：{year_bonus:.2f}/0.2",
                        f"综合匹配度：{total_score:.2f}/5.0"
                    ])

            else:
                # 简洁版本 - 适用于类型1和3
                user_sequence = self._get_user_sequence(user_id, max_length=5)

                # 1. 用户历史观影序列
                if user_sequence:
                    context_items.append(f"用户最近观看了{len(user_sequence)}部电影")
                    for i, movie in enumerate(user_sequence[:3]):
                        context_items.append(f"最近观看：{movie}")

                # 2. 用户偏好信息
                if preferences:
                    context_items.append(f"用户偏好：{', '.join(preferences)}类型的电影")

                # 3. 电影基本信息
                if movie_info:
                    context_items.extend([
                        f"电影《{movie_info.get('title', '未知')}》",
                        f"导演：{movie_info.get('director', '未知')}",
                        f"类型：{', '.join(movie_info.get('genres', []))}",
                        f"评分：{movie_info.get('vote_average', 0)}/10"
                    ])

            # 确保上下文项目不为空
            if not context_items:
                context_items = [
                    "用户有电影观看历史",
                    "用户对特定类型电影有偏好",
                    "推荐系统基于用户特征匹配电影"
                ]

        except Exception as e:
            print(f"构建评估上下文失败: {str(e)}")
            context_items = ["用户观影历史", "电影类型匹配", "个性化推荐因素"]

        print(f'解释类型{explanation_type}的context_items:', context_items)
        return context_items

    def _get_evaluation_causal_factors(self, user_id: int, movie_title: str, explanation_type: int = None) -> List[str]:
        """
        为CRA评估构建因果因素，根据解释类型调整详细程度
        """
        causal_factors = []

        try:
            # 获取用户偏好和电影信息
            preferences = self._get_user_preferences(user_id)
            movie_info = self._get_movie_info(movie_title)

            # 针对解释类型2提供更详细的因果分析
            if explanation_type == 2:
                # 详细因果分析 - 适合论证解释
                if preferences and movie_info:
                    movie_genres = movie_info.get('genres', [])
                    preference_weights = self._get_preference_weights(user_id, preferences)

                    # 1. 类型匹配的详细因果分析
                    matching_genres = set(preferences) & set(movie_genres)
                    if matching_genres:
                        for genre in list(matching_genres)[:2]:
                            weight = preference_weights[preferences.index(genre)] if genre in preferences else 0.1
                            causal_factors.append(f"用户对{genre}类型的高偏好(权重:{weight:.2f})与电影类型直接匹配")
                    else:
                        # 即使类型不直接匹配，也分析潜在关联
                        causal_factors.append("用户偏好模式与电影特征存在潜在关联性")

                    # 2. 质量指标因果
                    rating = movie_info.get('vote_average', 0)
                    if rating >= 7.0:
                        causal_factors.append("电影高评分(≥7.0)增强推荐可信度")
                    elif rating >= 5.0:
                        causal_factors.append("电影中等评分提供基本质量保证")

                    # 4. 制作团队因果
                    director = movie_info.get('director', '')
                    if director and director != '未知':
                        causal_factors.append(f"导演{director}的知名度影响观影决策")

                    actors = movie_info.get('actors', [])
                    if actors:
                        causal_factors.append("主要演员阵容影响用户选择意愿")


            else:
                # 简洁因果分析 - 适用于类型1和3
                if preferences and movie_info:
                    movie_genres = movie_info.get('genres', [])
                    for genre in preferences[:2]:
                        if genre in movie_genres:
                            causal_factors.append(f"用户偏好{genre}类型与电影类型匹配")
                        else:
                            causal_factors.append(f"用户偏好{genre}类型影响推荐决策")

                # 一般性因果因素
                causal_factors.extend([
                    "类型匹配度影响用户满意度",
                    "导演知名度影响观看意愿",
                    "电影评分影响用户选择",
                    "个性化推荐提高用户参与度",
                    "历史行为预测未来偏好"
                ])

        except Exception as e:
            print(f"构建因果因素失败: {str(e)}")
            causal_factors = [
                "类型匹配影响推荐效果",
                "用户历史偏好预测满意度",
                "电影特征影响用户决策"
            ]

        print(f'解释类型{explanation_type}的causal_factors:', causal_factors)
        return causal_factors

    def batch_evaluate_explanations(self, test_cases: List[Dict]) -> Dict[str, Any]:
        """
        批量评估多个解释案例

        参数:
        - test_cases: 测试用例列表，每个用例包含user_id, movie_title, explanation_type, predicted_rating

        返回:
        - 批量评估结果统计
        """
        results = []

        for i, test_case in enumerate(test_cases):
            print(f"处理测试案例 {i + 1}/{len(test_cases)}")

            try:
                result = self.generate_and_evaluate_explanation(
                    test_case['user_id'],
                    test_case['movie_title'],
                    test_case['explanation_type'],
                    test_case.get('predicted_rating', 4.0)
                )
                results.append(result)
            except Exception as e:
                print(f"案例{i + 1}处理失败: {str(e)}")
                results.append({
                    'explanation': f"生成失败: {str(e)}",
                    'evaluation': {'pss_score': 0.0, 'cra_score': 0.0, 'error': str(e)},
                    'generation_success': False,
                    'evaluation_success': False
                })

        # 计算统计信息
        successful_results = [r for r in results if r['evaluation_success']]

        if successful_results:
            pss_scores = [r['evaluation']['pss_score'] for r in successful_results]
            cra_scores = [r['evaluation']['cra_score'] for r in successful_results]

            stats = {
                'total_cases': len(results),
                'successful_cases': len(successful_results),
                'success_rate': len(successful_results) / len(results),
                'avg_pss': np.mean(pss_scores),
                'avg_cra': np.mean(cra_scores),
                'std_pss': np.std(pss_scores),
                'std_cra': np.std(cra_scores),
                'max_pss': np.max(pss_scores),
                'max_cra': np.max(cra_scores),
                'min_pss': np.min(pss_scores),
                'min_cra': np.min(cra_scores)
            }
        else:
            stats = {
                'total_cases': len(results),
                'successful_cases': 0,
                'success_rate': 0.0,
                'avg_pss': 0.0,
                'avg_cra': 0.0,
                'std_pss': 0.0,
                'std_cra': 0.0,
                'max_pss': 0.0,
                'max_cra': 0.0,
                'min_pss': 0.0,
                'min_cra': 0.0
            }

        return {
            'statistics': stats,
            'detailed_results': results
        }

    def generate_and_evaluate_explanation(self, user_id: int, movie_title: str,
                                          explanation_type: int, predicted_rating: float) -> Dict[str, Any]:
        """
        生成解释并评估其质量（综合方法）
        """
        try:
            # 生成解释
            explanation = self.generate_explanation(user_id, movie_title, explanation_type, predicted_rating)

            # 评估解释
            evaluation_results = self.evaluate_explanation(user_id, movie_title, explanation, explanation_type)

            # 合并结果
            results = {
                'explanation': explanation,
                'evaluation': evaluation_results,
                'generation_success': True,
                'evaluation_success': evaluation_results.get('evaluation_success', False)
            }

            return results

        except Exception as e:
            print(f"生成和评估解释失败: {str(e)}")
            return {
                'explanation': self._get_fallback_explanation(explanation_type),
                'evaluation': {
                    'pss_score': 0.0,
                    'cra_score': 0.0,
                    'error': str(e)
                },
                'generation_success': False,
                'evaluation_success': False
            }
