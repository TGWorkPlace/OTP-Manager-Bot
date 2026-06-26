import os

# Bot credentials
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Admin
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# Database
DB_URI = os.environ.get("DB_URI", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "otp_manager")

# Web server port (Koyeb public)
PORT = int(os.environ.get("PORT", 8080))

# OTP auto-delete delay in seconds (0 = disabled)
OTP_AUTO_DELETE = int(os.environ.get("OTP_AUTO_DELETE", 0))

# Pagination
USERS_PER_PAGE = 20
