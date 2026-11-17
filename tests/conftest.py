import os

# Keep the entire test suite offline with zero OpenAI calls, even if .env exists locally.
os.environ["USE_FAKE_MODEL"] = "1"
