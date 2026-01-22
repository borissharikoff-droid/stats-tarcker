import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass, field

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class StatsBlock:
    """Represents a statistics block."""
    name: str
    metrics: Dict[str, str] = field(default_factory=dict)
    subsections: Dict[str, Dict[str, str]] = field(default_factory=dict)


@dataclass
class StatsData:
    """Container for all statistics data."""
    p2p_bot: Optional[StatsBlock] = None
    posting_bot: Optional[StatsBlock] = None
    raw_html: str = ""
    error: Optional[str] = None


def create_driver() -> webdriver.Chrome:
    """Create and configure Chrome WebDriver."""
    options = config.get_chrome_options()
    
    driver = None
    
    # Method 1: Try using chromedriver from specified path
    if config.CHROMEDRIVER_PATH:
        try:
            service = Service(executable_path=config.CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("Using chromedriver from specified path")
        except Exception as e:
            logger.warning(f"Failed to use specified chromedriver path: {e}")
    
    # Method 2: Try webdriver-manager
    if driver is None:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("Using chromedriver from webdriver-manager")
        except Exception as e:
            logger.warning(f"Failed to use webdriver-manager: {e}")
    
    # Method 3: Try default (chromedriver in PATH)
    if driver is None:
        try:
            driver = webdriver.Chrome(options=options)
            logger.info("Using default chromedriver from PATH")
        except Exception as e:
            logger.error(f"Failed to create Chrome driver: {e}")
            raise
    
    driver.set_page_load_timeout(30)
    return driver


def login(driver: webdriver.Chrome) -> bool:
    """
    Login to the statistics website.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        True if login successful, False otherwise
    """
    try:
        logger.info(f"Navigating to {config.STATS_URL}")
        driver.get(config.STATS_URL)
        
        # Wait for page to load
        wait = WebDriverWait(driver, 10)
        
        # Check if we're on login page (redirected)
        current_url = driver.current_url.lower()
        if 'login' not in current_url:
            logger.info("Already logged in or no login required")
            return True
        
        # Find login input field
        try:
            login_field = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='email']"))
            )
            logger.info("Found login field")
        except TimeoutException:
            logger.error("Could not find login field")
            return False
        
        # Find password field
        try:
            password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            logger.info("Found password field")
        except NoSuchElementException:
            logger.error("Could not find password field")
            return False
        
        # Enter credentials
        login_field.clear()
        login_field.send_keys(config.STATS_LOGIN)
        
        password_field.clear()
        password_field.send_keys(config.STATS_PASSWORD)
        
        # Find and click submit button
        try:
            submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button")
            submit_button.click()
            logger.info("Clicked submit button")
        except NoSuchElementException:
            # Try pressing Enter as fallback
            password_field.submit()
            logger.info("Submitted form via Enter key")
        
        # Wait for page to load after login
        time.sleep(3)
        
        # Check if login was successful
        current_url = driver.current_url
        logger.info(f"Current URL after login: {current_url}")
        
        # If still on login page, login failed
        if 'login' in current_url.lower():
            logger.error("Login failed - still on login page")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return False


def parse_statistics(driver: webdriver.Chrome) -> StatsData:
    """
    Parse statistics from the page after login.
    Based on the actual HTML structure of admin.doxmediagroup.com/Statistic
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        StatsData object containing parsed statistics
    """
    stats_data = StatsData()
    
    try:
        # Wait for page content to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
        time.sleep(2)
        
        # Get page source
        page_source = driver.page_source
        stats_data.raw_html = page_source
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(page_source, 'lxml')
        
        # Initialize blocks
        p2p_block = StatsBlock(name="p2pDox")
        posting_block = StatsBlock(name="Doxposting")
        
        # Find all top-level cards (direct children of rows)
        all_cards = soup.find_all('div', class_='card')
        
        for card in all_cards:
            # Skip nested cards (those inside other cards)
            parent_card = card.find_parent('div', class_='card')
            if parent_card:
                continue
            
            # Find card header
            card_header = card.find('div', class_='card-header')
            if not card_header:
                continue
            
            header_text = card_header.get_text(strip=True)
            
            # P2P Bot card
            if 'P2P' in header_text:
                logger.info("Parsing P2P Bot card")
                card_body = card.find('div', class_='card-body')
                if card_body:
                    # Method 1: Find all info-item divs
                    info_items = card_body.find_all('div', class_='info-item')
                    for item in info_items:
                        label = item.find('label')
                        badge = item.find('span', class_='badge')
                        if label and badge:
                            key = label.get_text(strip=True).rstrip(':')
                            value = badge.get_text(strip=True)
                            p2p_block.metrics[key] = value
                    
                    # Method 2: Find all d-flex divs with label and badge
                    if not p2p_block.metrics:
                        flex_items = card_body.find_all('div', class_='d-flex')
                        for item in flex_items:
                            label = item.find('label')
                            badge = item.find('span', class_='badge')
                            if label and badge:
                                key = label.get_text(strip=True).rstrip(':')
                                value = badge.get_text(strip=True)
                                p2p_block.metrics[key] = value
            
            # Posting Bot card
            elif 'Posting' in header_text:
                logger.info("Parsing Posting Bot card")
                card_body = card.find('div', class_='card-body')
                if card_body:
                    # Parse general statistics section
                    # Look for all d-flex divs that contain label and badge
                    all_flex_divs = card_body.find_all('div', class_='d-flex')
                    for div in all_flex_divs:
                        # Skip if inside nested card
                        if div.find_parent('div', class_='card border-primary') or div.find_parent('div', class_='card border-info'):
                            continue
                        label = div.find('label')
                        badge = div.find('span', class_='badge')
                        if label and badge:
                            key = label.get_text(strip=True).rstrip(':')
                            value = badge.get_text(strip=True)
                            posting_block.metrics[key] = value
                    
                    # Parse posts statistics card (nested card with border-primary)
                    posts_card = card_body.find('div', class_=lambda x: x and 'border-primary' in x)
                    if posts_card:
                        posting_block.subsections['Посты'] = {}
                        logger.info("Found posts card")
                        # Find all stat boxes with text-center class
                        stat_boxes = posts_card.find_all('div', class_='text-center')
                        for box in stat_boxes:
                            # Value is in div with fs-3 or fw-bold class
                            value_div = box.find('div', class_=lambda x: x and ('fs-3' in x or 'fw-bold' in x))
                            # Label is in div with text-muted class
                            label_div = box.find('div', class_='text-muted')
                            if value_div and label_div:
                                value = value_div.get_text(strip=True)
                                label = label_div.get_text(strip=True)
                                posting_block.subsections['Посты'][label] = value
                                logger.info(f"Posts: {label} = {value}")
                    
                    # Parse stories statistics card (nested card with border-info)
                    stories_card = card_body.find('div', class_=lambda x: x and 'border-info' in x)
                    if stories_card:
                        posting_block.subsections['Сторис'] = {}
                        logger.info("Found stories card")
                        stat_boxes = stories_card.find_all('div', class_='text-center')
                        for box in stat_boxes:
                            value_div = box.find('div', class_=lambda x: x and ('fs-3' in x or 'fw-bold' in x))
                            label_div = box.find('div', class_='text-muted')
                            if value_div and label_div:
                                value = value_div.get_text(strip=True)
                                label = label_div.get_text(strip=True)
                                posting_block.subsections['Сторис'][label] = value
                                logger.info(f"Stories: {label} = {value}")
        
        # Assign blocks
        if p2p_block.metrics:
            stats_data.p2p_bot = p2p_block
        else:
            logger.warning("No P2P Bot metrics found")
        
        if posting_block.metrics or posting_block.subsections:
            stats_data.posting_bot = posting_block
        else:
            logger.warning("No Posting Bot metrics found")
        
        logger.info(f"Parsed stats - P2P metrics: {len(stats_data.p2p_bot.metrics) if stats_data.p2p_bot else 0}, "
                   f"Posting metrics: {len(stats_data.posting_bot.metrics) if stats_data.posting_bot else 0}, "
                   f"Posting subsections: {len(stats_data.posting_bot.subsections) if stats_data.posting_bot else 0}")
        
    except Exception as e:
        logger.error(f"Failed to parse statistics: {e}")
        stats_data.error = str(e)
    
    return stats_data


def fetch_statistics() -> StatsData:
    """
    Main function to fetch statistics from the website.
    
    Returns:
        StatsData object with parsed statistics or error
    """
    driver = None
    try:
        logger.info("Creating WebDriver...")
        driver = create_driver()
        
        logger.info("Attempting login...")
        if not login(driver):
            return StatsData(error="Login failed")
        
        logger.info("Parsing statistics...")
        stats_data = parse_statistics(driver)
        
        return stats_data
        
    except Exception as e:
        logger.error(f"Failed to fetch statistics: {e}")
        return StatsData(error=str(e))
        
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def format_stats_message(stats_data: StatsData) -> str:
    """
    Format statistics data as HTML message for Telegram.
    Format: <b>Label</b>: value (no emojis, headers bold, values plain)
    
    Args:
        stats_data: StatsData object with parsed statistics
        
    Returns:
        HTML formatted message string
    """
    if stats_data.error:
        return f"<b>Ошибка получения статистики</b>: {stats_data.error}"
    
    message_parts = []
    
    # Format P2P Bot (p2pDox) block
    if stats_data.p2p_bot:
        block_lines = [f"<b>{stats_data.p2p_bot.name}</b>"]
        for key, value in stats_data.p2p_bot.metrics.items():
            block_lines.append(f"<b>{key}</b>: {value}")
        message_parts.append('\n'.join(block_lines))
    
    # Format Posting Bot (Doxposting) block
    if stats_data.posting_bot:
        # Main metrics (general stats)
        block_lines = [f"<b>{stats_data.posting_bot.name}</b>"]
        for key, value in stats_data.posting_bot.metrics.items():
            block_lines.append(f"<b>{key}</b>: {value}")
        message_parts.append('\n'.join(block_lines))
        
        # Subsections as separate blocks (Posts, Stories)
        for section_name, section_metrics in stats_data.posting_bot.subsections.items():
            if section_metrics:
                section_lines = [f"<b>{section_name}</b>"]
                for key, value in section_metrics.items():
                    section_lines.append(f"<b>{key}</b>: {value}")
                message_parts.append('\n'.join(section_lines))
    
    if not message_parts:
        return "<b>Статистика</b>: данные не найдены"
    
    return '\n\n'.join(message_parts)


if __name__ == "__main__":
    # Test the scraper
    print("Testing scraper...")
    stats = fetch_statistics()
    print(format_stats_message(stats))
