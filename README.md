# Make It Easy 🎥➡️📄

A powerful web service that transforms YouTube how-to videos into comprehensive step-by-step PDF instructions using AI.

## ✨ Features

- 🎬 **YouTube Video Processing** - Downloads videos from YouTube URLs (including Shorts)
- 🎤 **Speech Transcription** - Uses OpenAI Whisper for accurate audio-to-text conversion
- 🤖 **AI-Powered Analysis** - Leverages Deepseek AI to break down content into clear steps
- 🖼️ **Frame Extraction** - Automatically extracts relevant images for each step using FFmpeg
- 📋 **PDF Generation** - Creates beautiful, structured PDF guides with text and images
- 🌐 **Web Interface** - User-friendly web UI with real-time progress tracking
- ⚡ **Background Processing** - Non-blocking API with job status monitoring

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- FFmpeg installed on your system

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/holyredbeard/makeiteasy.git
   cd makeiteasy
   ```

2. **Install FFmpeg:**
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # Windows (using chocolatey)
   choco install ffmpeg
   ```

3. **Set up Python environment:**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

4. **Set up Whisper environment (recommended):**
   ```bash
   # Create separate environment for Whisper
   python -m venv whisper_env
   source whisper_env/bin/activate
   pip install openai-whisper
   ```

### Running the Service

```bash
# Activate the Whisper environment
source whisper_env/bin/activate

# Start the server
uvicorn main:app --reload
```

The service will be available at:
- **Web Interface:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs

## 🎯 Usage

### Web Interface

1. Open http://localhost:8000 in your browser
2. Paste a YouTube URL (works with regular videos and Shorts)
3. Click "🚀 Create PDF Instructions"
4. Monitor the real-time progress through 5 stages:
   - 📥 Downloading video from YouTube
   - ✏️ Transcribing audio content
   - 🧠 Analyzing content with AI
   - 🖼️ Extracting images from video
   - 📄 Generating PDF with instructions
5. Download your PDF when complete!

### API Usage

#### Submit a Video for Processing
```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{"youtube_url": "https://www.youtube.com/shorts/M7s6kyxm54E"}'
```

#### Check Processing Status
```bash
curl "http://localhost:8000/status/{job_id}"
```

#### Download Generated PDF
```bash
curl "http://localhost:8000/result/{job_id}" -o instructions.pdf
```

### Python Client Example

```python
import requests
import time

# Submit video for processing
response = requests.post(
    "http://localhost:8000/generate",
    json={"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
)
job_id = response.json()["job_id"]
print(f"Job submitted: {job_id}")

# Poll for completion
while True:
    status_response = requests.get(f"http://localhost:8000/status/{job_id}")
    status = status_response.json()["status"]
    print(f"Status: {status}")
    
    if status == "completed":
        # Download the PDF
        pdf_response = requests.get(f"http://localhost:8000/result/{job_id}")
        with open("instructions.pdf", "wb") as f:
            f.write(pdf_response.content)
        print("PDF downloaded successfully!")
        break
    elif status == "failed":
        print("Processing failed!")
        break
    
    time.sleep(5)
```

## 🛠️ API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/generate` | Submit YouTube URL for processing |
| `GET` | `/status/{job_id}` | Get job status and progress |
| `GET` | `/result/{job_id}` | Download generated PDF |
| `GET` | `/` | Web interface |
| `GET` | `/docs` | API documentation |

### Status Values

- `processing` - Initial processing started
- `transcribing` - Converting speech to text
- `analyzing` - AI analyzing content for steps
- `extracting_frames` - Extracting images from video
- `generating_pdf` - Creating final PDF
- `completed` - Process finished successfully
- `failed` - An error occurred

## 🔧 Configuration

The service uses the Deepseek AI API for content analysis. The API key is currently hardcoded but can be configured as an environment variable:

```bash
export DEEPSEEK_API_KEY="your-api-key-here"
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Web Client    │────│  FastAPI     │────│  Background     │
│                 │    │  Server      │    │  Tasks          │
└─────────────────┘    └──────────────┘    └─────────────────┘
                              │                      │
                              │                      ▼
                              │            ┌─────────────────┐
                              │            │  yt-dlp         │
                              │            │  (Download)     │
                              │            └─────────────────┘
                              │                      │
                              │                      ▼
                              │            ┌─────────────────┐
                              │            │  Whisper        │
                              │            │  (Transcribe)   │
                              │            └─────────────────┘
                              │                      │
                              │                      ▼
                              │            ┌─────────────────┐
                              │            │  Deepseek AI    │
                              │            │  (Analyze)      │
                              │            └─────────────────┘
                              │                      │
                              │                      ▼
                              │            ┌─────────────────┐
                              │            │  FFmpeg         │
                              │            │  (Extract)      │
                              │            └─────────────────┘
                              │                      │
                              │                      ▼
                              │            ┌─────────────────┐
                              │            │  FPDF           │
                              │            │  (Generate)     │
                              │            └─────────────────┘
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📋 Requirements

See `requirements.txt` for a complete list of Python dependencies.

Key dependencies:
- FastAPI - Web framework
- Whisper - Speech recognition
- yt-dlp - YouTube video downloading
- FFmpeg-python - Video processing
- FPDF2 - PDF generation
- Requests - HTTP client for AI API

## 🐛 Troubleshooting

### Common Issues

**Whisper Import Error:**
```bash
# Make sure you're using the whisper_env environment
source whisper_env/bin/activate
uvicorn main:app --reload
```

**FFmpeg Not Found:**
```bash
# Install FFmpeg for your system
brew install ffmpeg  # macOS
sudo apt install ffmpeg  # Ubuntu
```

**Tensor Reshape Error:**
- This usually occurs with very short videos or videos without clear speech
- The system now handles this gracefully with improved error handling

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 🙏 Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) for speech recognition
- [Deepseek AI](https://deepseek.com/) for content analysis
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube video downloading
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework

---

**Made with ❤️ by [holyredbeard](https://github.com/holyredbeard)** 