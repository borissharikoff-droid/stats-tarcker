import json
import os
import logging
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# File to store previous statistics
STATS_FILE = "stats_history.json"


def load_previous_stats() -> Optional[Dict[str, Any]]:
    """
    Load previous statistics from JSON file.
    
    Returns:
        Dictionary with previous stats or None if file doesn't exist
    """
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loaded previous stats from {STATS_FILE}")
                return data
        else:
            logger.info("No previous stats file found")
            return None
    except Exception as e:
        logger.error(f"Failed to load previous stats: {e}")
        return None


def save_current_stats(stats_data: Dict[str, Any]) -> bool:
    """
    Save current statistics to JSON file.
    
    Args:
        stats_data: Dictionary with current statistics
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Add timestamp
        stats_data['timestamp'] = datetime.now().isoformat()
        
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved current stats to {STATS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save stats: {e}")
        return False


def stats_to_dict(stats_data) -> Dict[str, Any]:
    """
    Convert StatsData object to dictionary for storage.
    
    Args:
        stats_data: StatsData object
        
    Returns:
        Dictionary representation of stats
    """
    result = {}
    
    if stats_data.p2p_bot:
        result['p2p_bot'] = {
            'name': stats_data.p2p_bot.name,
            'metrics': stats_data.p2p_bot.metrics.copy()
        }
    
    if stats_data.posting_bot:
        result['posting_bot'] = {
            'name': stats_data.posting_bot.name,
            'metrics': stats_data.posting_bot.metrics.copy(),
            'subsections': {k: v.copy() for k, v in stats_data.posting_bot.subsections.items()}
        }
    
    return result


def parse_number(value: str) -> Optional[float]:
    """
    Parse a number from string, handling Russian number format.
    
    Args:
        value: String value like "2861" or "1,83"
        
    Returns:
        Float value or None if parsing failed
    """
    try:
        # Replace Russian decimal comma with dot
        cleaned = value.replace(',', '.').replace(' ', '').replace('\xa0', '')
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def calculate_diff(current_value: str, previous_value: str) -> Optional[str]:
    """
    Calculate difference between current and previous values.
    
    Args:
        current_value: Current value as string
        previous_value: Previous value as string
        
    Returns:
        Difference string like "+5" or "-3" or None
    """
    current_num = parse_number(current_value)
    previous_num = parse_number(previous_value)
    
    if current_num is None or previous_num is None:
        return None
    
    diff = current_num - previous_num
    
    if diff == 0:
        return None
    elif diff > 0:
        # Format as integer if it's a whole number
        if diff == int(diff):
            return f"+{int(diff)}"
        else:
            return f"+{diff:.2f}".replace('.', ',')
    else:
        if diff == int(diff):
            return f"{int(diff)}"
        else:
            return f"{diff:.2f}".replace('.', ',')


def get_diffs(current_stats: Dict[str, Any], previous_stats: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """
    Calculate differences between current and previous statistics.
    
    Args:
        current_stats: Current statistics dictionary
        previous_stats: Previous statistics dictionary (or None)
        
    Returns:
        Dictionary with differences for each metric
    """
    diffs = {
        'p2p_bot': {},
        'posting_bot': {},
        'subsections': {}
    }
    
    if not previous_stats:
        return diffs
    
    # P2P Bot differences
    if 'p2p_bot' in current_stats and 'p2p_bot' in previous_stats:
        current_metrics = current_stats['p2p_bot'].get('metrics', {})
        previous_metrics = previous_stats['p2p_bot'].get('metrics', {})
        
        for key, current_value in current_metrics.items():
            if key in previous_metrics:
                diff = calculate_diff(current_value, previous_metrics[key])
                if diff:
                    diffs['p2p_bot'][key] = diff
    
    # Posting Bot differences
    if 'posting_bot' in current_stats and 'posting_bot' in previous_stats:
        current_metrics = current_stats['posting_bot'].get('metrics', {})
        previous_metrics = previous_stats['posting_bot'].get('metrics', {})
        
        for key, current_value in current_metrics.items():
            if key in previous_metrics:
                diff = calculate_diff(current_value, previous_metrics[key])
                if diff:
                    diffs['posting_bot'][key] = diff
        
        # Subsections differences
        current_subsections = current_stats['posting_bot'].get('subsections', {})
        previous_subsections = previous_stats['posting_bot'].get('subsections', {})
        
        for section_name, current_section in current_subsections.items():
            if section_name in previous_subsections:
                diffs['subsections'][section_name] = {}
                previous_section = previous_subsections[section_name]
                
                for key, current_value in current_section.items():
                    if key in previous_section:
                        diff = calculate_diff(current_value, previous_section[key])
                        if diff:
                            diffs['subsections'][section_name][key] = diff
    
    return diffs
