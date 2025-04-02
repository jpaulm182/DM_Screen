# app/core/models/monster.py

import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import logging

@dataclass
class MonsterAbility:
    """Represents a single ability score."""
    score: int = 10
    # Note: Proficiency bonus is derived from CR, not stored per ability.

@dataclass
class MonsterSkill:
    """Represents a skill proficiency."""
    name: str
    modifier: int # The total modifier including ability + proficiency

@dataclass
class MonsterSense:
    """Represents a sense like Darkvision or Blindsight."""
    name: str
    range: str # e.g., "60 ft."

@dataclass
class MonsterTrait:
    """Represents a special trait."""
    name: str
    description: str

@dataclass
class MonsterAction:
    """Represents an action, bonus action, or reaction."""
    name: str
    description: str
    # Potential future fields: attack_bonus, damage_dice, damage_type

@dataclass
class MonsterLegendaryAction:
    """Represents a legendary action."""
    name: str
    description: str
    cost: int = 1 # Default cost

@dataclass
class Monster:
    """
    Represents a D&D 5e Monster, compatible with both standard
    reference monsters and custom creations.
    Uses field metadata for JSON serialization keys.
    """
    # Core Identification
    id: Optional[int] = None # Database ID (None for new/unsaved)
    name: str = "Unnamed Monster"
    is_custom: bool = False # Flag to distinguish DB source

    # Basic Stats (matching 'monsters' table where possible)
    size: str = "Medium"
    type: str = "humanoid" # e.g., beast, monstrosity
    alignment: str = "unaligned"
    armor_class: int = field(default=10, metadata={"json_key": "ac"})
    hit_points: str = field(default="10 (3d6)", metadata={"json_key": "hp"}) # e.g., "136 (16d10 + 48)"
    speed: str = "30 ft." # e.g., "30 ft., fly 60 ft."

    # Ability Scores
    strength: int = field(default=10, metadata={"json_key": "str"})
    dexterity: int = field(default=10, metadata={"json_key": "dex"})
    constitution: int = field(default=10, metadata={"json_key": "con"})
    intelligence: int = field(default=10, metadata={"json_key": "int"})
    wisdom: int = field(default=10, metadata={"json_key": "wis"})
    charisma: int = field(default=10, metadata={"json_key": "cha"})

    # Derived/Proficiency-based stats
    challenge_rating: str = field(default="1", metadata={"json_key": "cr"}) # e.g., "5" or "1/2"
    skills: List[MonsterSkill] = field(default_factory=list) # List of MonsterSkill objects
    senses: List[MonsterSense] = field(default_factory=list) # List of MonsterSense objects
    languages: str = "Common" # Comma-separated string

    # Features & Actions
    traits: List[MonsterTrait] = field(default_factory=list) # Special abilities
    actions: List[MonsterAction] = field(default_factory=list) # Standard actions
    legendary_actions: Optional[List[MonsterLegendaryAction]] = field(default=None) # Optional list

    # Fluff & Source
    description: Optional[str] = None # General description or lore
    source: str = "Custom" # Origin (e.g., "MM", "Custom", "LLM")

    # Timestamps for custom monsters
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Monster object to a dictionary suitable for JSON storage."""
        # Use asdict for basic conversion, then handle nested objects and metadata keys
        data = {}
        for f in self.__dataclass_fields__.values():
            value = getattr(self, f.name)
            json_key = f.metadata.get("json_key", f.name) # Use json_key if defined

            # Serialize nested dataclasses if they are lists or optional lists
            if isinstance(value, list) and value and hasattr(value[0], '__dataclass_fields__'):
                data[json_key] = [asdict(item) for item in value]
            elif hasattr(value, '__dataclass_fields__') and value is not None: # Single optional dataclass (though none currently used)
                 data[json_key] = asdict(value)
            elif f.name not in ["id", "is_custom"]: # Exclude DB id and custom flag from JSON
                data[json_key] = value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Monster':
        """Creates a Monster object from a dictionary (e.g., from JSON)."""
        # Map json_key back to field name
        field_map = {f.metadata.get("json_key", f.name): f.name for f in cls.__dataclass_fields__.values()}
        mapped_data = {field_map.get(k, k): v for k, v in data.items()}

        logger = logging.getLogger(__name__) # Get logger inside method
        logger.debug(f"Monster.from_dict called with data: {data}")

        # Deserialize nested lists
        for field_name, field_type in cls.__annotations__.items():
            # Handle List[SomeDataclass]
            if hasattr(field_type, '__origin__') and field_type.__origin__ == list:
                item_type = field_type.__args__[0]
                if hasattr(item_type, '__dataclass_fields__') and field_name in mapped_data and isinstance(mapped_data[field_name], list):
                     mapped_data[field_name] = [item_type(**item_data) for item_data in mapped_data[field_name]]
                pass # Keep as is

            # Handle Optional[List[SomeDataclass]]
            elif hasattr(field_type, '__origin__') and field_type.__origin__ == Optional:
                 inner_type = field_type.__args__[0]
                 if hasattr(inner_type, '__origin__') and inner_type.__origin__ == list:
                    item_type = inner_type.__args__[0]
                    logger.debug(f"Checking Optional[List] field: {field_name}, item_type: {item_type}")
                    if hasattr(item_type, '__dataclass_fields__') and field_name in mapped_data and mapped_data[field_name] is not None:
                        if isinstance(mapped_data[field_name], list):
                            original_data = mapped_data[field_name]
                            logger.debug(f"  Found list data for {field_name}: {original_data}")
                            try:
                                mapped_data[field_name] = [item_type(**item_data) for item_data in original_data]
                                logger.debug(f"  Successfully converted {field_name} to list of {item_type.__name__}")
                            except Exception as e:
                                 logger.error(f"  Error converting item in {field_name} list: {e}", exc_info=True)
                                 # Decide on error handling: skip field, use empty list, or raise?
                                 # Let's default to None for the Optional field on error
                                 mapped_data[field_name] = None
                                 logger.warning(f"  Setting {field_name} to None due to conversion error.")
                        else:
                             logger.warning(f"  Expected list for {field_name}, but got {type(mapped_data[field_name])}. Setting to None.")
                             mapped_data[field_name] = None
                    elif field_name in mapped_data and mapped_data[field_name] is None:
                         logger.debug(f"  Field {field_name} is explicitly None.")
                         # Keep it None, which is valid for Optional
                    elif field_name not in mapped_data:
                         logger.debug(f"  Optional list field {field_name} not found in input data. Will default to None.")
                         # Let the dataclass constructor handle the default (which is None)


        # Filter out keys not part of the dataclass
        init_data = {k: v for k, v in mapped_data.items() if k in cls.__dataclass_fields__}
        logger.debug(f"Final init_data for Monster: {init_data}")

        try:
            instance = cls(**init_data)
            logger.debug("Monster instance created successfully.")
            return instance
        except Exception as e:
            logger.error(f"Error creating Monster instance: {e}", exc_info=True)
            # Reraise or return None/default? Reraising might be better.
            raise

    @classmethod
    def from_db_row(cls, row: Dict[str, Any], is_custom: bool = False) -> 'Monster':
        """Creates a Monster object from a database row (dictionary)."""
        if is_custom:
            # Custom monsters store data in a JSON blob
            monster_data = json.loads(row.get('data', '{}'))
            monster_data['id'] = row.get('id') # Add DB ID
            monster_data['created_at'] = row.get('created_at')
            monster_data['updated_at'] = row.get('updated_at')
            monster_data['is_custom'] = True
            monster_data['source'] = monster_data.get('source', 'Custom') # Ensure source defaults to Custom
            # Ensure core fields are present even if missing in JSON blob
            monster_data['name'] = row.get('name', monster_data.get('name', 'Unnamed Custom'))

            return cls.from_dict(monster_data)
        else:
            # Standard monsters have individual columns
            # Basic mapping
            init_data = {
                'id': row.get('id'),
                'name': row.get('name'),
                'size': row.get('size'),
                'type': row.get('type'),
                'alignment': row.get('alignment'),
                'armor_class': row.get('ac'), # Map 'ac' column
                'hit_points': row.get('hp'), # Map 'hp' column
                'speed': row.get('speed'),
                'strength': row.get('str'), # Map 'str' column
                'dexterity': row.get('dex'), # etc.
                'constitution': row.get('con'),
                'intelligence': row.get('int'),
                'wisdom': row.get('wis'),
                'charisma': row.get('cha'),
                'challenge_rating': row.get('cr'), # Map 'cr' column
                'languages': row.get('languages'),
                'description': row.get('description'),
                'source': row.get('source', 'Unknown'), # Default source if missing
                'is_custom': False
            }

            # Parse complex fields (assuming simple JSON string storage in DB for now)
            # TODO: Refine parsing based on actual DB storage format for lists/dicts
            try:
                skills_data = json.loads(row.get('skills', '[]'))
                init_data['skills'] = [MonsterSkill(**s) for s in skills_data]
            except (json.JSONDecodeError, TypeError):
                init_data['skills'] = [] # Default to empty list on error

            try:
                senses_data = json.loads(row.get('senses', '[]'))
                init_data['senses'] = [MonsterSense(**s) for s in senses_data]
            except (json.JSONDecodeError, TypeError):
                 init_data['senses'] = []

            try:
                traits_data = json.loads(row.get('traits', '[]'))
                init_data['traits'] = [MonsterTrait(**t) for t in traits_data]
            except (json.JSONDecodeError, TypeError):
                 init_data['traits'] = []

            try:
                actions_data = json.loads(row.get('actions', '[]'))
                init_data['actions'] = [MonsterAction(**a) for a in actions_data]
            except (json.JSONDecodeError, TypeError):
                 init_data['actions'] = []

            try:
                legendary_actions_data = json.loads(row.get('legendary_actions', 'null'))
                if legendary_actions_data:
                    init_data['legendary_actions'] = [MonsterLegendaryAction(**la) for la in legendary_actions_data]
                else:
                     init_data['legendary_actions'] = None
            except (json.JSONDecodeError, TypeError):
                 init_data['legendary_actions'] = None


            # Filter out None values for fields that don't allow None
            final_init_data = {}
            for key, value in init_data.items():
                 if key in cls.__dataclass_fields__:
                    field_type = cls.__annotations__[key]
                    # Check if the field type is Optional (Union[T, None])
                    is_optional = hasattr(field_type, '__origin__') and field_type.__origin__ is Optional

                    if value is not None or is_optional:
                        final_init_data[key] = value
                    # If value is None but field isn't optional, use default factory/value
                    elif hasattr(cls.__dataclass_fields__[key], 'default_factory') and cls.__dataclass_fields__[key].default_factory is not None:
                         final_init_data[key] = cls.__dataclass_fields__[key].default_factory()
                    elif hasattr(cls.__dataclass_fields__[key], 'default') and cls.__dataclass_fields__[key].default is not None:
                         final_init_data[key] = cls.__dataclass_fields__[key].default

            return cls(**final_init_data) 