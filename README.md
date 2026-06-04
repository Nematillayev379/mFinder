# 🎬 Anime & Movie Finder Telegram Bot

Telegram bot that identifies anime, movies, and TV series from video clips using AI vision technology.

## ✨ Features

- 🎥 **Video Analysis** - Extracts frames using FFmpeg
- 🤖 **AI Vision** - OpenAI GPT-4V analyzes frames
- 🎬 **Anime Database** - AniList API integration
- 🎞️ **Movie Database** - TMDB API integration
- 📺 **Series Support** - Full TV series identification
- 🌍 **Multilingual** - Uzbek, English, Russian, Japanese
- 💰 **Streaming Links** - Free and paid platform recommendations
- ⚡ **Caching** - SQLite-based result caching
- 🛡️ **Rate Limiting** - 50 requests/day per user
- 🔒 **Secure** - Non-root Docker user, HTML escaping, timeouts

## 📋 Requirements

- Python 3.11+
- FFmpeg (auto-installed in Docker)
- Telegram Bot Token
- OpenAI API Key
- TMDB API Key (optional, for movies/series)

## 🚀 Quick Start (Local)

```bash
# 1. Clone repository
git clone <your-repo-url>
cd bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install FFmpeg
# Windows: Download from https://ffmpeg.org
# Linux: sudo apt install ffmpeg
# Mac: brew install ffmpeg

# 4. Create .env file
cp .env.example .env
# Edit .env with your API keys

# 5. Run bot
python main.py
```

## 🌐 Deploy to Render

### Method 1: One-Click Deploy (Recommended)

1. Push this folder to a GitHub repository
2. Go to [render.com](https://render.com) and sign in
3. Click **"New +"** → **"Blueprint"**
4. Connect your GitHub repository
5. Render will detect `render.yaml` automatically
6. Add environment variables in Render dashboard:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `TMDB_API_KEY`
7. Click **"Apply"**

### Method 2: Manual Setup

1. Push to GitHub
2. Go to [render.com](https://render.com) → **"New +"** → **"Worker Service"**
3. Connect repository
4. Configure:
   - **Runtime**: Docker
   - **Dockerfile Path**: `./Dockerfile`
   - **Plan**: Free
5. Add environment variables
6. Click **"Create Worker Service"**

## 🔑 Getting API Keys

### Telegram Bot Token
1. Open Telegram, find [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Follow instructions
4. Copy the token

### OpenAI API Key
1. Go to [platform.openai.com](https://platform.openai.com/api-keys)
2. Create new secret key
3. Add $5 credit (covers ~500-1000 videos)

### TMDB API Key
1. Sign up at [themoviedb.org](https://www.themoviedb.org)
2. Go to [Settings → API](https://www.themoviedb.org/settings/api)
3. Request API key (free, instant)

## 📁 Project Structure

```
bot/
├── main.py                  # Entry point
├── config.py                # Configuration & validation
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker configuration
├── render.yaml              # Render deployment config
├── .env.example             # Environment template
├── .dockerignore            # Docker ignore rules
├── .gitignore               # Git ignore rules
├── handlers/
│   ├── __init__.py
│   ├── start_handler.py     # /start, /help, /lang
│   └── video_handler.py     # Video processing
├── services/
│   ├── __init__.py
│   ├── frame_extractor.py   # FFmpeg integration
│   ├── vision_analyzer.py   # OpenAI GPT-4V
│   ├── anime_searcher.py    # AniList API
│   ├── movie_searcher.py    # TMDB API
│   ├── streaming_finder.py  # Streaming platforms
│   └── cache_service.py     # SQLite cache
└── utils/
    ├── __init__.py
    ├── formatter.py         # Response formatting
    └── languages.py         # i18n support
```

## 💰 Cost Estimation

| Service | Cost |
|---------|------|
| Render Free Tier | $0 (750 hours/month) |
| Telegram Bot | Free |
| OpenAI GPT-4V | ~$0.01-0.03/video |
| AniList API | Free |
| TMDB API | Free |

**1000 videos/month ≈ $10-30**

## 🛠️ Configuration

Edit `.env` or Render environment variables:

```env
TELEGRAM_BOT_TOKEN=your_token
OPENAI_API_KEY=sk-xxx
TMDB_API_KEY=xxx
OPENAI_MODEL=gpt-4o  # or gpt-4o-mini for cheaper
```

## 📊 Bot Commands

- `/start` - Start the bot
- `/help` - Show help
- `/lang` - Change language

## 🐛 Troubleshooting

### Bot not responding
- Check logs in Render dashboard
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Ensure OpenAI API has credit

### "ffmpeg not found" error
- In Docker: Already installed in image
- Local: Install FFmpeg and add to PATH

### Video not identifying
- Video must be at least 2-3 seconds
- Characters must be visible
- Try with clearer video

## 📝 License

MIT License - Free to use and modify

## 🤝 Support

For issues, check Render logs first, then create a GitHub issue.
