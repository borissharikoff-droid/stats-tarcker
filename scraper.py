import logging
import time
import io
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
import matplotlib

# Use non-interactive backend for server
matplotlib.use('Agg')

import config
from storage import stats_to_dict, load_previous_stats, save_current_stats, get_diffs, parse_number

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


def format_stats_message(stats_data: StatsData, diffs: Optional[Dict] = None) -> str:
    """
    Format statistics data as HTML message for Telegram.
    Format: <b>Label</b>: value (+diff) (no emojis, headers bold, values plain)
    
    Args:
        stats_data: StatsData object with parsed statistics
        diffs: Dictionary with differences from previous report
        
    Returns:
        HTML formatted message string
    """
    if stats_data.error:
        return f"<b>Ошибка получения статистики</b>: {stats_data.error}\n\n\n#Report"
    
    if diffs is None:
        diffs = {'p2p_bot': {}, 'posting_bot': {}, 'subsections': {}}
    
    message_parts = []
    
    # Format P2P Bot (p2pDox) block
    if stats_data.p2p_bot:
        block_lines = [f"<b>{stats_data.p2p_bot.name}</b>"]
        for key, value in stats_data.p2p_bot.metrics.items():
            diff = diffs.get('p2p_bot', {}).get(key, '')
            if diff:
                block_lines.append(f"<b>{key}</b>: {value} ({diff})")
            else:
                block_lines.append(f"<b>{key}</b>: {value}")
        message_parts.append('\n'.join(block_lines))
    
    # Format Posting Bot (Doxposting) block
    if stats_data.posting_bot:
        # Main metrics (general stats)
        block_lines = [f"<b>{stats_data.posting_bot.name}</b>"]
        for key, value in stats_data.posting_bot.metrics.items():
            diff = diffs.get('posting_bot', {}).get(key, '')
            if diff:
                block_lines.append(f"<b>{key}</b>: {value} ({diff})")
            else:
                block_lines.append(f"<b>{key}</b>: {value}")
        message_parts.append('\n'.join(block_lines))
        
        # Subsections as separate blocks (Posts, Stories)
        for section_name, section_metrics in stats_data.posting_bot.subsections.items():
            if section_metrics:
                section_lines = [f"<b>{section_name}</b>"]
                section_diffs = diffs.get('subsections', {}).get(section_name, {})
                for key, value in section_metrics.items():
                    diff = section_diffs.get(key, '')
                    if diff:
                        section_lines.append(f"<b>{key}</b>: {value} ({diff})")
                    else:
                        section_lines.append(f"<b>{key}</b>: {value}")
                message_parts.append('\n'.join(section_lines))
    
    if not message_parts:
        return "<b>Статистика</b>: данные не найдены\n\n\n#Report"
    
    # Join all parts and add #Report at the end with double newline
    result = '\n\n'.join(message_parts)
    result += "\n\n\n#Report"
    
    return result


def generate_charts(stats_data: StatsData) -> List[Tuple[str, bytes]]:
    """
    Generate pie charts for statistics.
    
    Args:
        stats_data: StatsData object with parsed statistics
        
    Returns:
        List of tuples (chart_name, image_bytes)
    """
    charts = []
    
    # Set up Russian font support
    plt.rcParams['font.family'] = 'DejaVu Sans'
    
    # Chart 1: P2P Bot metrics
    if stats_data.p2p_bot and stats_data.p2p_bot.metrics:
        fig, ax = plt.subplots(figsize=(8, 6))
        
        labels = []
        values = []
        for key, value in stats_data.p2p_bot.metrics.items():
            num = parse_number(value)
            if num and num > 0:
                # Shorten long labels
                short_key = key[:25] + '...' if len(key) > 25 else key
                labels.append(short_key)
                values.append(num)
        
        if values:
            colors = ['#4CAF50', '#2196F3', '#FFC107', '#9C27B0', '#FF5722']
            wedges, texts, autotexts = ax.pie(
                values, 
                labels=labels, 
                autopct='%1.1f%%',
                colors=colors[:len(values)],
                startangle=90
            )
            ax.set_title('p2pDox', fontsize=16, fontweight='bold')
            
            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
            buf.seek(0)
            charts.append(('p2pDox', buf.getvalue()))
            plt.close(fig)
    
    # Chart 2: Doxposting (Posts and Stories combined)
    if stats_data.posting_bot and stats_data.posting_bot.subsections:
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        colors_posts = ['#4CAF50', '#FFC107', '#F44336']  # Green, Yellow, Red
        colors_stories = ['#2196F3', '#FF9800', '#E91E63']  # Blue, Orange, Pink
        
        # Posts pie chart
        posts = stats_data.posting_bot.subsections.get('Посты', {})
        if posts:
            labels = []
            values = []
            for key, value in posts.items():
                num = parse_number(value)
                if num is not None and num >= 0:
                    labels.append(key)
                    values.append(max(num, 0.1))  # Avoid zero for pie chart
            
            if values and sum(values) > 0:
                wedges, texts, autotexts = axes[0].pie(
                    values,
                    labels=labels,
                    autopct=lambda pct: f'{pct:.1f}%' if pct > 1 else '',
                    colors=colors_posts[:len(values)],
                    startangle=90
                )
                axes[0].set_title('Посты', fontsize=14, fontweight='bold')
            else:
                axes[0].text(0.5, 0.5, 'Нет данных', ha='center', va='center')
                axes[0].set_title('Посты', fontsize=14, fontweight='bold')
        
        # Stories pie chart
        stories = stats_data.posting_bot.subsections.get('Сторис', {})
        if stories:
            labels = []
            values = []
            for key, value in stories.items():
                num = parse_number(value)
                if num is not None and num >= 0:
                    labels.append(key)
                    values.append(max(num, 0.1))
            
            if values and sum(values) > 0:
                wedges, texts, autotexts = axes[1].pie(
                    values,
                    labels=labels,
                    autopct=lambda pct: f'{pct:.1f}%' if pct > 1 else '',
                    colors=colors_stories[:len(values)],
                    startangle=90
                )
                axes[1].set_title('Сторис', fontsize=14, fontweight='bold')
            else:
                axes[1].text(0.5, 0.5, 'Нет данных', ha='center', va='center')
                axes[1].set_title('Сторис', fontsize=14, fontweight='bold')
        
        fig.suptitle('Doxposting', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # Save to bytes
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        buf.seek(0)
        charts.append(('Doxposting', buf.getvalue()))
        plt.close(fig)
    
    return charts


if __name__ == "__main__":
    # Test the scraper
    print("Testing scraper...")
    stats = fetch_statistics()
    print(format_stats_message(stats))
