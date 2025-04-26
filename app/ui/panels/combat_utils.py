# combat_utils.py
"""
Utility functions for the combat tracker panel: dice rolling, attribute extraction, etc.
"""
import random
import re

def extract_dice_formula(hp_value):
    """Extract dice formula from a string or dict HP value."""
    if isinstance(hp_value, str):
        match = re.search(r'(\d+d\d+(?:[+-]\d+)?)', hp_value)
        if match:
            return match.group(1)
    elif isinstance(hp_value, dict):
        if 'formula' in hp_value:
            return hp_value['formula']
        if 'roll' in hp_value:
            return hp_value['roll']
    return None

def roll_dice(formula):
    """Roll dice from a formula like '6d10+12'."""
    match = re.match(r"(\d+)d(\d+)([+-]\d+)?", formula)
    if not match:
        return 0
    num = int(match.group(1))
    die = int(match.group(2))
    mod = int(match.group(3) or 0)
    return sum(random.randint(1, die) for _ in range(num)) + mod

def get_attr(obj, attr, default=None, alt_attrs=None):
    """Get attribute from object or dict, trying alternate attribute names if specified."""
    alt_attrs = alt_attrs or []
    try:
        if isinstance(obj, dict):
            if attr in obj:
                return obj[attr]
            for alt_attr in alt_attrs:
                if alt_attr in obj:
                    return obj[alt_attr]
        else:
            if hasattr(obj, attr):
                return getattr(obj, attr)
            for alt_attr in alt_attrs:
                if hasattr(obj, alt_attr):
                    return getattr(obj, alt_attr)
        return default
    except Exception:
        return default
