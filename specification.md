# DND 5e Dynamic DM Screen Specification

Project Overview

The Dynamic DM Screen aims to be the ultimate digital Dungeon Master's companion for D&D 5e, providing instant access to crucial information while offering powerful tools for dynamic content generation and campaign management.

This program will not be a web application and all databases will be local to the program.

Implementation Status Legend:
✅ Implemented
🔄 In Progress
⚠️ Partially Implemented
❌ Not Started
🔜 Planned Next

## PRIMARY DEVELOPMENT FOCUS: LLM Framework Implementation

7. LLM Integration (HIGH PRIORITY)
    - 🔜 Core LLM API integration with provider selection
    - 🔜 Persistent storage of all LLM-generated content
    - 🔜 Campaign-specific content organization and retrieval
    - 🔜 Context management system for effective prompting
    - 🔜 Monster stat block extraction and formatting
    - 🔜 Spell lookup and interpretation
    - 🔜 Basic NPC generation with personality traits
    - 🔜 Rules clarification and edge case interpretation
    - 🔄 Location-appropriate random encounter generation
    - 🔄 Custom magic item creation with balanced mechanics
    - 🔄 Interactive tavern and shop scenes with dynamic NPCs
    - 🔄 Campaign-aware content generation that builds on existing story elements
    - 🔄 Session prep assistance with encounter and location planning
    - 🔄 Player background integration into generated content
    - 🔄 Contextual help and suggestions during gameplay
    - 🔄 Voice and text prompting for hands-free operation during gameplay
    - 🔄 Comprehensive context access to all campaign data, notes, character stats, history, and world information for highly relevant and personalized responses
    - 🔄 Adaptive generation based on party composition, character backgrounds, and previous session outcomes
    - 🔄 Fast combat resolution with detailed narrative results

Core Features

1. Dynamic Layout System
    - ✅ Customizable multi-panel interface
    - ✅ Drag-and-drop organization of information panels
    - ✅ Save/load different layouts for different campaign types
    - ✅ Responsive design supporting multiple screen sizes
    - ✅ Dark/light mode support
    - ❌ Font size adjustments for accessibility
    - ✅ Smart panel organization based on category
    - ✅ Simultaneous view of related panels (combat, reference, etc.)

2. Essential Reference Panels
    - ✅ Combat tracker with initiative management
    - ✅ Condition reference with quick-apply functionality
    - ✅ Basic rules quick-reference
    - ✅ NPC/Monster stat block viewer
    - ✅ Spell reference and tracker
    - ✅ DC/Check difficulty guidelines (part of rules reference)
    - ✅ Cover and terrain effects (part of rules reference)
    - ✅ Weather and environmental effects
    - ✅ Time and travel pace tracker
    - 🔜 LLM-powered rules lookup and interpretation panel

3. Dynamic Content Generation
    - ❌ Terrain-based encounter tables
    - ❌ Difficulty-scaled encounters
    - ❌ Custom encounter table builder
    - ❌ Quick NPC personality/motivation generator
    - ❌ Location-appropriate monster filtering
    - 🔜 LLM-generated random encounters based on terrain, difficulty, and party composition
    - 🔜 LLM-generated quick NPCs with personality, motivation, and voice
    - 🔜 LLM-assisted monster selection with contextual filtering

Treasure Generation
    - ❌ Custom loot table builder
    - ❌ Hoard generation by CR
    - ❌ Individual treasure generation
    - ❌ Magic item generation with rarity filtering
    - ❌ Custom item integration
    - 🔄 LLM-generated unique magic items with backstories
    - 🔄 LLM-generated treasure hoards contextual to location and monsters

World Building Tools
    - ❌ Settlement generator
    - ❌ Shop inventory generator
    - ❌ Quick NPC name/trait generator
    - ❌ Location description generator
    - ❌ Plot hook generator
    - 🔄 LLM-generated immersive location descriptions
    - 🔄 LLM-generated shop inventories with unique items
    - 🔄 LLM-generated interactive shopkeeper and bartender personalities
    - 🔄 LLM-generated plot hooks tied to campaign themes and party background

4. Campaign Management
    - ✅ Session notes with searchable tags
    - ✅ Initiative tracker with HP/status management
    - ✅ Player character quick reference
    - ⚠️ Custom monster/NPC storage (basic version implemented)
    - ✅ Bookmark system for frequent references (implemented in Rules panel)
    - ❌ Session timer with break reminders
    - 🔄 LLM-assisted session note summarization and organization
    - 🔄 LLM-generated session recap for players

5. Advanced Features
    - ✅ Dice roller with custom formulas
    - ❌ Sound effect/ambient music integration
    - ✅ Weather system with effects on gameplay
    - ❌ Calendar system with moon phases/festivals
    - ❌ Combat difficulty calculator
    - ❌ Experience point calculator
    - ❌ Encounter balancing tools
    - ❌ Custom table builder for any content
    - 🔄 LLM-generated custom tables based on text prompts
    - 🔄 LLM-assisted combat narration based on actions and results
    - 🔄 LLM-generated weather effects and descriptions
    - 🔄 LLM-resolved fast combat with narrative results

6. Data Management
    - ✅ Local storage for custom content
    - ❌ Optional cloud sync
    - ❌ Regular auto-save
    - ❌ Data export in common formats
    - 🔜 Enhanced data structure for LLM content storage

Technical Requirements

Performance
    - ✅ Instant response for common lookups (<100ms)
    - ✅ Smooth scrolling and panel transitions
    - ✅ Efficient memory usage for long sessions
    - ✅ Offline functionality for core features
    - 🔜 Efficient LLM API usage with response caching
    - 🔄 Fallback options when offline for LLM-dependent features
    - 🔄 Optimized campaign context processing for faster, more relevant LLM responses

Data Storage
    - ✅ Local storage for custom content
    - ❌ Optional cloud sync
    - ❌ Regular auto-save
    - ❌ Data export in common formats
    - 🔜 Structured storage for all LLM-generated content
    - 🔜 Campaign-specific LLM content organization
    - 🔄 Comprehensive knowledge graph connecting campaign elements for context-aware LLM access
    - 🔄 Privacy-preserving campaign data indexing for LLM processing

Security
    - ❌ User authentication for cloud features
    - ❌ Encrypted data storage
    - ❌ Regular backup prompts
    - 🔜 Secure API key management for LLM services

Extensibility
    - ❌ Plugin system for custom modules
    - ❌ API for custom content generation
    - ❌ Import/export of custom rulesets
    - 🔜 Custom prompt templates for LLM generation
    - 🔜 User-definable generation parameters and constraints

User Interface Guidelines
    - ✅ Minimalist design with focus on readability
    - ✅ High contrast options for low-light gaming
    - ✅ Touch-friendly for tablet users
    - ⚠️ Keyboard shortcuts for common actions (implemented for Combat Tracker)
    - ❌ Context-sensitive help system
    - ❌ Unified search across all content
    - ✅ Visual panel state indicators (active panel highlighting)
    - 🔜 Intuitive LLM prompt interface with suggestions
    - 🔜 Clear visual indicators for LLM-generated vs manual content

Next Implementation Steps:
1. 🔜 Implement core LLM API integration framework with provider selection
2. 🔜 Develop persistent storage system for LLM-generated content
3. 🔜 Create campaign context management for effective LLM prompting
4. 🔜 Build basic UI for LLM interactions and content generation
5. 🔜 Implement secure API key management for LLM services
6. 🔜 Develop initial NPC generator using LLM
7. 🔜 Create rules clarification module using LLM
8. 🔜 Implement monster stat block extraction and formatting
9. 🔜 Add font size adjustment for accessibility
10. 🔜 Enhance Monster panel with custom monster creation

Layout Save/Load Feature Specification:
- ✅ Allow users to save current panel layout configuration
- ✅ Provide named presets (Combat Focus, Exploration, Social, etc.)
- ✅ Save panel visibility, position, and size
- ✅ Include user-created custom layouts with custom names
- ✅ Quick-switch between layouts via dropdown menu
- ✅ Export/import layouts for sharing between installations
- 🔄 LLM-suggested layouts based on campaign type and DM preferences

Player Character Quick Reference Specification:
- ✅ Store basic character information (name, race, class, level)
- ✅ Track key stats (AC, HP, ability scores, saving throws)
- ✅ Note special abilities, features, and equipment
- ✅ Quick access to character spell lists (for spellcasters)
- ✅ Visual indicators for conditions and status effects
- ✅ Integration with combat tracker for initiative and effects
- ✅ Support for multiple party members
- ⚠️ Basic character sheet import functionality (planned but not fully implemented)
- 🔄 LLM-generated character insights and hooks based on background
- 🔄 LLM-suggested character-specific plot elements

LLM Framework Technical Specification:

Core LLM Framework Components:
- Provider-agnostic API integration layer supporting multiple LLM services
- Context management system with efficient token usage
- Content storage and indexing system
- User interface for prompt creation and result management
- Template system for consistent outputs across different content types
- Feedback and refinement mechanism for generated content
- Caching system to minimize API costs and improve response time
- Fallback functionality for offline operation

Content Generation:
- Stateful prompting system preserving context between generations
- Content tagging system for organization and retrieval
- Campaign association for all generated content
- Version history for iterative content refinement
- Export options for generated content (PDF, text, etc.)
- Template system for consistent generation results
- Rating system for generated content quality
- Regeneration options with modified parameters
- Contextual awareness system providing LLMs with access to:
  * Complete campaign notes and history
  * Character sheets and background stories
  * Previous session summaries and key events
  * NPC relationships and faction information
  * World lore and setting specifics
  * Party inventory and resources
  * Ongoing quests and plot threads
  * Custom rules and homebrew content

NPC Generation:
- Complete stat blocks based on CR/level requirements
- Personality traits with consistent voice and mannerisms
- Background and motivation generation
- Relationship generator connecting NPCs to world and party
- Voice and speech pattern suggestions for roleplaying
- Optional portrait generation or selection
- Inventory and equipment generation
- Special ability suggestions

Location Generation:
- Detailed descriptions with sensory elements
- Location-appropriate NPCs and encounters
- Point-of-interest suggestions
- Secrets and hidden elements
- Environment-specific challenges and obstacles
- Mapping integration or suggestions
- Atmosphere and mood descriptors

Monster Integration:
- Pull complete stat blocks from 5e SRD
- Custom monster generation balancing
- Suggested tactics based on monster intelligence and abilities
- Personality traits for intelligent monsters
- Lair and environment descriptions
- Custom monster variants with balanced abilities
- Monster ecology and societal role descriptions

Magic Item Generation:
- Balanced mechanics based on rarity
- Unique visual descriptions
- Backstory and history
- Previous owners and legacy
- Quirks and side effects
- Attunement requirements and processes
- Hidden abilities revealed over time
- Integration with campaign themes

Encounter Generation:
- Balanced challenge rating for party
- Terrain-appropriate monsters and challenges
- Dynamic encounter elements (weather, terrain features)
- Narrative context for encounter
- Initiative and positioning suggestions
- Tactical possibilities and monster behaviors
- XP and treasure calculation
- Encounter aftermath suggestions

Fast Combat Resolution:
- Single-click resolution of entire combat encounters
- Automatic tracking of character abilities, spells, and resources
- Tactical decision-making based on character/monster intelligence and abilities
- Round-by-round narrative breakdown with key moments highlighted
- Detailed roll results for attacks, saves, and damage
- Critical hit and fumble narrative descriptions
- Spell effects with appropriate saving throws and consequences
- Resource tracking (spell slots, class features, consumables)
- Status effect application and duration tracking
- Healing and recovery tracking
- Death saving throw management
- Detailed aftermath summary with remaining resources and conditions
- XP and loot calculation
- Options to customize resolution speed (quick, standard, detailed)
- Manual override options for key decision points
- Character-specific combat style recognition in narration
- Tactical positioning and movement descriptions
- Environmental interaction during combat
- Option to slow-motion specific rounds or actions of interest
- Save points to allow for retroactive changes or alternate paths

Interactive Elements:
- Shopkeeper interactions with negotiation capabilities
- Tavern conversations with rumors and information
- NPC reactions based on party actions and history
- Dynamic dialogue options based on character backgrounds
- Faction representative interactions
- Quest-giver interactions with branching possibilities
- Information source interactions (sages, libraries, etc.)

Campaign Integration:
- Content generation informed by campaign history
- Recurring themes and elements
- NPC memory of past interactions
- Development of world state based on party actions
- Consequences of previous decisions
- Foreshadowing of upcoming plot points
- Consistent tone and atmosphere
- Deep integration with DM notes and planning documents
- Character arc awareness and progression suggestions
- Thematic consistency with campaign style and setting
- Sensitivity to table preferences and game tone
- Awareness of mechanical challenges appropriate for party level and composition

Planned Integrations

    Virtual tabletop system compatibility
    Digital character sheet integration
    Custom content marketplaces
    Community content sharing
    🔜 LLM API integration with multiple providers
    🔄 Content sharing system for LLM-generated material

Development Priorities

    1. 🔜 LLM integration framework and core functionality
    2. 🔜 Persistent storage for generated content 
    3. 🔜 Basic content generation modules (NPCs, rules clarification)
    4. Core reference functionality enhancements
    5. Advanced LLM generation features
    6. Additional dynamic generation systems
    7. Campaign management tools expansion
    8. Integration capabilities
    9. 🔄 Fast combat resolution system

Success Metrics

    Reduced lookup time vs. physical DM screen
    Increased encounter/treasure generation speed
    Positive user feedback on customization
    Active community content creation
    Regular user engagement
    🔜 Quality and usability of LLM-generated content
    🔜 Time saved using AI-assisted content generation
    🔄 Reduction in combat resolution time while maintaining narrative quality

Future Considerations

    AI-powered NPC interactions
    AR/VR compatibility
    Multi-user collaboration
    Campaign analytics
    Advanced automation options
    🔄 Voice-to-text for hands-free LLM prompting
    🔄 Fine-tuning LLM models for D&D-specific generation
    🔄 Integration with image generation for visual assets
    🔄 LLM-powered storytelling assistance during gameplay

Accessibility Requirements

    Screen reader compatibility
    Keyboard navigation
    Color blind friendly design
    Font size/contrast adjustments
    Multi-language support
    🔄 Voice-controlled LLM prompting for accessibility

This specification will be regularly updated based on user feedback and emerging needs in the D&D community.