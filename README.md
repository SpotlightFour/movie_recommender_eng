# 🎬 movie_recommender_eng

> A full-stack AI-powered movie recommendation system integrating a backend recommendation engine, a frontend user interface, and a database.

## ⚡ Quick Start

### 1. Backend Environment Setup

```bash
# Clone the repository
git clone https://github.com/SpotlightFour/movie_recommender.git
cd movie_recommender/recommend

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Large Language Model File Download

> **Note**  
> Due to GitHub’s file size limit (max 100 MB), the large language model files cannot be uploaded via Git directly. Please download them manually following the steps below.

1. Visit [Qwen2.5-0.5B](https://huggingface.co/Qwen/Qwen2.5-0.5B) and download the following files (or replace with another model):
   - `model.safetensors` (main model file, approx. 942 MB)
   - Other configuration files (such as `config.json`, `tokenizer.json`, etc.)

2. Place all downloaded files into the `recommend/qwen_models/` directory.

3. The final directory structure should be:

   ```
   recommend/
   └── qwen_models/
       ├── model.safetensors
       ├── config.json
       ├── generation_config.json
       ├── model.safetensors.index.json
       ├── special_tokens_map.json
       ├── tokenizer_config.json
       └── tokenizer.json
   ```

### 3. Database Initialization

```bash
# Please install and start MySQL or PostgreSQL beforehand
# Use the SQL scripts provided by the project to create the database and tables
```

### 4. Frontend Environment Setup

```bash
# Enter the frontend directory
cd vue_recommend

# Install Node.js dependencies
npm install

# Run in development mode (hot reload)
npm run serve

# Build for production
npm run build
```

### 5. Start the Full System

Open two terminal windows and start the backend and frontend services in order:

- **Backend API service** (run in the `movie_recommender` directory):

  ```bash
  python recommend/app.py
  ```

- **Frontend dev server** (run in the `vue_recommend` directory):

  ```bash
  npm run serve
  ```

After successful startup, visit the frontend address in your browser (default `http://localhost:8080`) to use the movie recommendation system.
