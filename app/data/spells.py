"""
Spells Data Module

Provides access to spells data for the DM Screen application
"""

# Import spell data from the source file
from spells_copy import SPELL_SCHOOLS, SPELL_LEVELS, SPELLS_BY_LEVEL

def get_all_spells():
    """
    Convert the spells data into a list format suitable for the SpellReferencePanel
    
    Returns:
        list: A list of spell dictionaries with standardized format
    """
    all_spells = []
    spell_id = 1
    
    for level_name, spells in SPELLS_BY_LEVEL.items():
        # Convert level name to level number
        if level_name == "Cantrip":
            level_num = 0
        else:
            # Convert "1st", "2nd", etc. to integers
            level_num = int(level_name[0])
            
        for spell in spells:
            formatted_spell = {
                'id': spell_id,
                'name': spell['name'],
                'level': level_num,
                'school': spell['school'],
                'casting_time': spell['casting_time'],
                'range': spell['range'],
                'components': spell['components'],
                'duration': spell['duration'],
                'description': spell['description'],
                # Classes aren't in the original data, so we'll leave this empty
                'class': ""
            }
            all_spells.append(formatted_spell)
            spell_id += 1
            
    return all_spells

def get_spell_schools():
    """
    Get the list of spell schools
    
    Returns:
        list: A list of spell school names
    """
    return SPELL_SCHOOLS

def get_spell_levels():
    """
    Get the list of spell levels
    
    Returns:
        list: A list of spell level names
    """
    return SPELL_LEVELS 