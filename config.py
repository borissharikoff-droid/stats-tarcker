import os
from dotenv import load_dotenv

# Load environment variables from .env or config.env file if exists
if os.path.exists('.env'):
    load_dotenv('.env')
elif os.path.exists('config.env'):
    load_dotenv('config.env')
else:
    load_dotenv()  # Try default

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Statistics Website Configuration
STATS_URL = "https://admin.doxmediagroup.com/Statistic"
STATS_LOGIN_URL = "https://admin.doxmediagroup.com/Statistic"
STATS_LOGIN = os.getenv("STATS_LOGIN", "")
STATS_PASSWORD = os.getenv("STATS_PASSWORD", "")

# Schedule Configuration (hours when to send stats, default: midnight and noon)
SCHEDULE_HOURS = [int(h) for h in os.getenv("SCHEDULE_HOURS", "0,12").split(",")]

# Selenium Configuration for Railway (headless Chrome)
SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"
CHROME_BIN = os.getenv("CHROME_BIN", "")  # Empty = use default
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "")  # Empty = use webdriver-manager

# Timezone for scheduler
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")


def get_chrome_options():
    """Get Chrome options configured for headless mode on Railway."""
    from selenium.webdriver.chrome.options import Options
    
    options = Options()
    
    if SELENIUM_HEADLESS:
        options.add_argument("--headless")
    
    # Required for running in containers
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    
    # Set Chrome binary location if specified
    if CHROME_BIN:
        options.binary_location = CHROME_BIN
    
    return options
