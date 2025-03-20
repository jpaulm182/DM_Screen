"""
Spells Data Module

Provides access to spells data for the DM Screen application
"""

# Import spell data from the source file
from app.data.spells_copy import SPELL_SCHOOLS, SPELL_LEVELS, SPELLS_BY_LEVEL

# Define class mappings by spell name
SPELL_CLASSES = {
    # Cantrips
    "Acid Splash": "Sorcerer, Wizard, Artificer",
    "Blade Ward": "Bard, Sorcerer, Warlock, Wizard",
    "Chill Touch": "Sorcerer, Warlock, Wizard",
    "Dancing Lights": "Bard, Sorcerer, Wizard, Artificer",
    "Fire Bolt": "Sorcerer, Wizard, Artificer",
    "Light": "Bard, Cleric, Sorcerer, Wizard, Artificer",
    "Mage Hand": "Bard, Sorcerer, Warlock, Wizard, Artificer",
    "Message": "Bard, Sorcerer, Wizard, Artificer",
    "Minor Illusion": "Bard, Sorcerer, Warlock, Wizard",
    "Prestidigitation": "Bard, Sorcerer, Warlock, Wizard, Artificer",
    
    # 1st Level
    "Alarm": "Ranger, Wizard, Artificer",
    "Burning Hands": "Sorcerer, Wizard",
    "Charm Person": "Bard, Druid, Sorcerer, Warlock, Wizard",
    "Detect Magic": "Bard, Cleric, Druid, Paladin, Ranger, Sorcerer, Wizard, Artificer",
    "Magic Missile": "Sorcerer, Wizard",
    
    # 2nd Level
    "Acid Arrow": "Wizard, Artificer",
    "Alter Self": "Sorcerer, Wizard, Artificer",
    "Blindness/Deafness": "Bard, Cleric, Sorcerer, Wizard",
    "Darkness": "Sorcerer, Warlock, Wizard",
    "Invisibility": "Bard, Sorcerer, Warlock, Wizard, Artificer",
    "Mirror Image": "Sorcerer, Warlock, Wizard",
    
    # 3rd Level
    "Animate Dead": "Cleric, Wizard",
    "Counterspell": "Sorcerer, Warlock, Wizard",
    "Fireball": "Sorcerer, Wizard",
    "Fly": "Sorcerer, Warlock, Wizard, Artificer",
    "Haste": "Sorcerer, Wizard, Artificer",
    "Lightning Bolt": "Sorcerer, Wizard",
    
    # 4th Level
    "Banishment": "Cleric, Paladin, Sorcerer, Warlock, Wizard",
    "Blight": "Druid, Sorcerer, Warlock, Wizard",
    "Confusion": "Bard, Druid, Sorcerer, Wizard",
    "Dimension Door": "Bard, Sorcerer, Warlock, Wizard",
    "Greater Invisibility": "Bard, Sorcerer, Wizard",
    "Ice Storm": "Druid, Sorcerer, Wizard",
    "Polymorph": "Bard, Druid, Sorcerer, Wizard",
    "Stone Shape": "Cleric, Druid, Wizard, Artificer",
    "Wall of Fire": "Druid, Sorcerer, Wizard",
    
    # 5th Level
    "Animate Objects": "Bard, Sorcerer, Wizard, Artificer",
    "Cloudkill": "Sorcerer, Wizard",
    "Cone of Cold": "Sorcerer, Wizard",
    "Hold Monster": "Bard, Sorcerer, Warlock, Wizard",
    "Legend Lore": "Bard, Cleric, Wizard",
    "Scrying": "Bard, Cleric, Druid, Warlock, Wizard",
    "Wall of Force": "Wizard, Artificer",
    
    # 6th Level
    "Chain Lightning": "Sorcerer, Wizard",
    "Disintegrate": "Sorcerer, Wizard",
    "Globe of Invulnerability": "Sorcerer, Wizard",
    "Mass Suggestion": "Bard, Sorcerer, Warlock, Wizard",
    "Sunbeam": "Cleric, Druid, Sorcerer, Wizard",
    "True Seeing": "Bard, Cleric, Sorcerer, Warlock, Wizard",
    
    # 7th Level
    "Delayed Blast Fireball": "Sorcerer, Wizard",
    "Etherealness": "Bard, Cleric, Sorcerer, Warlock, Wizard",
    "Finger of Death": "Sorcerer, Warlock, Wizard",
    "Forcecage": "Bard, Warlock, Wizard",
    "Plane Shift": "Cleric, Druid, Sorcerer, Warlock, Wizard",
    "Prismatic Spray": "Sorcerer, Wizard",
    "Reverse Gravity": "Druid, Sorcerer, Wizard",
    "Teleport": "Bard, Sorcerer, Wizard",
    
    # 8th Level
    "Antimagic Field": "Cleric, Wizard",
    "Clone": "Wizard",
    "Dominate Monster": "Bard, Sorcerer, Warlock, Wizard",
    "Feeblemind": "Bard, Druid, Warlock, Wizard",
    "Power Word Stun": "Bard, Sorcerer, Warlock, Wizard",
    
    # 9th Level
    "Gate": "Cleric, Sorcerer, Wizard",
    "Meteor Swarm": "Sorcerer, Wizard",
    "Power Word Kill": "Bard, Sorcerer, Warlock, Wizard",
    "Time Stop": "Sorcerer, Wizard",
    "True Polymorph": "Bard, Warlock, Wizard",
    "Wish": "Sorcerer, Wizard"
}

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
                # Add class information from our mapping, or empty string if not found
                'class': SPELL_CLASSES.get(spell['name'], "")
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