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

LLM Integration (HIGH PRIORITY)
    - ✅ Core LLM API integration with provider selection
    - ✅ Persistent storage of all LLM-generated content
    - ⚠️ Campaign-specific content organization and retrieval
    - ✅ Context management system for effective prompting
    - ✅ Basic NPC generation with personality traits
    - ✅ Rules clarification and edge case interpretation
    - ⚠️ Contextual help and suggestions during gameplay
    - ✅ Secure API key management for LLM services
    - ✅ Efficient LLM API usage with response caching
    - ✅ Intuitive LLM prompt interface with suggestions
    - ⚠️ Clear visual indicators for LLM-generated vs manual content
    - 🔜 Content generation framework:
        * Monster stat block extraction and formatting
        * Spell lookup and interpretation
        * Location-appropriate random encounter generation
        * Custom magic item creation with balanced mechanics
        * Interactive tavern and shop scenes with dynamic NPCs
        * Session prep assistance with encounter and location planning
        * Fast combat resolution with detailed narrative results
    - 🔜 Context-aware generation utilizing:
        * Campaign history and notes
        * Player character data and backgrounds
        * Previous session outcomes
        * World information and lore
        * Party composition and capabilities

Core Features

1. Dynamic Layout System
    - ✅ Customizable multi-panel interface
    - ✅ Drag-and-drop organization of information panels
    - ✅ Save/load different layouts for different campaign types
    - ✅ Responsive design supporting multiple screen sizes
    - ✅ Dark/light mode support
    - ✅ Smart panel organization based on category
    - ✅ Simultaneous view of related panels (combat, reference, etc.)
    - ✅ Quick-switch between layouts via dropdown menu
    - ✅ Export/import layouts for sharing between installations
    - ❌ Font size adjustments for accessibility
    - 🔜 LLM-suggested layouts based on campaign type and DM preferences

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
    - ⚠️ LLM-powered rules lookup and interpretation panel

3. LLM-Powered Content Generation
    - ✅ LLM-generated weather effects and descriptions
    - 🔜 NPC Generation:
        * Complete stat blocks with CR-appropriate abilities
        * Personality traits, voice, and mannerisms
        * Background and motivation
        * Relationships to world elements and party
        * Inventory and equipment
    - 🔜 Location Generation:
        * Detailed sensory-rich descriptions
        * Points of interest and secrets
        * Appropriate NPCs and encounters
        * Environmental challenges
    - 🔜 Treasure Generation:
        * Magic items with backstories and mechanics
        * Treasure hoards contextual to location and monsters
        * Balanced rewards based on party level
    - 🔜 Encounter Generation:
        * Balanced for party composition
        * Terrain-appropriate challenges
        * Dynamic elements (weather, terrain features)
        * Narrative context and tactical suggestions
    - 🔜 Game Element Creation:
        * Custom monsters with balanced abilities
        * Plot hooks tied to campaign themes
        * Shop inventories with unique items
        * Interactive NPCs with consistent personalities

4. Campaign Management
    - ✅ Session notes with searchable tags
    - ✅ Initiative tracker with HP/status management
    - ✅ Player character quick reference
    - ⚠️ Custom monster/NPC storage (basic version implemented)
    - ✅ Bookmark system for frequent references (implemented in Rules panel)
    - ❌ Session timer with break reminders
    - 🔜 LLM-assisted features:
        * Session note summarization
        * Session recaps for players
        * Character insights based on background
        * Character-specific plot elements

5. Advanced Features
    - ✅ Dice roller with custom formulas
    - ✅ Weather system with effects on gameplay
    - 🔜 LLM-powered advanced functions:
        * Fast combat resolution with narrative results
        * Custom tables generated from text prompts
        * Combat narration based on actions and results

6. Data Management
    - ✅ Local storage for custom content
    - ✅ Enhanced data structure for LLM content storage
    - ⚠️ Campaign-specific LLM content organization
    - ⚠️ Fallback options when offline for LLM-dependent features
    - 🔜 Optimized campaign context processing for LLM responses
    - ❌ Optional cloud sync
    - ❌ Regular auto-save
    - ❌ Data export in common formats

Technical Framework

1. LLM Framework Components:
    - ✅ Provider-agnostic API integration layer
    - ✅ Context management system with efficient token usage
    - ✅ Content storage and indexing system
    - ✅ User interface for prompt creation and result management
    - ⚠️ Template system for consistent outputs
    - ⚠️ Feedback and refinement mechanism
    - ⚠️ Caching system to minimize API costs
    - ⚠️ Fallback functionality for offline operation

2. Content Generation System:
    - ✅ Stateful prompting preserving context between generations
    - ⚠️ Content tagging for organization and retrieval
    - ⚠️ Campaign association for all generated content
    - ⚠️ Version history for iterative content refinement
    - ⚠️ Template system for consistent results
    - ⚠️ Regeneration options with modified parameters
    - 🔜 Comprehensive contextual awareness system

3. Performance Requirements:
    - ✅ Instant response for common lookups (<100ms)
    - ✅ Smooth scrolling and panel transitions
    - ✅ Efficient memory usage for long sessions
    - ✅ Offline functionality for core features

4. User Interface Guidelines:
    - ✅ Minimalist design with focus on readability
    - ✅ High contrast options for low-light gaming
    - ✅ Touch-friendly for tablet users
    - ✅ Visual panel state indicators
    - ⚠️ Keyboard shortcuts for common actions (implemented for Combat Tracker)
    - ❌ Context-sensitive help system
    - ❌ Unified search across all content

Next Implementation Steps:
1. ✅ Implement core LLM API integration framework with provider selection
2. ✅ Develop persistent storage system for LLM-generated content
3. ✅ Create campaign context management for effective LLM prompting
4. ✅ Build basic UI for LLM interactions and content generation
5. ✅ Implement secure API key management for LLM services
6. ✅ Develop initial NPC generator using LLM
7. ✅ Create rules clarification module using LLM
8. 🔜 Implement monster stat block extraction and formatting
9. 🔜 Add font size adjustment for accessibility
10. 🔜 Enhance Monster panel with custom monster creation

Player Character Quick Reference Specification:
- ✅ Store basic character information (name, race, class, level)
- ✅ Track key stats (AC, HP, ability scores, saving throws)
- ✅ Note special abilities, features, and equipment
- ✅ Quick access to character spell lists (for spellcasters)
- ✅ Visual indicators for conditions and status effects
- ✅ Integration with combat tracker for initiative and effects
- ✅ Support for multiple party members
- ⚠️ Basic character sheet import functionality
- 🔜 LLM-generated character insights and plot elements

Fast Combat Resolution System (LLM-powered):
- 🔜 Single-click resolution of entire combat encounters
- 🔜 Round-by-round narrative breakdown with key moments
- 🔜 Tactical decision-making based on character/monster capabilities
- 🔜 Resource and status effect tracking
- 🔜 Detailed aftermath summary
- 🔜 Options to customize resolution detail level
- 🔜 Manual override for key decision points

Development Priorities
    1. ✅ LLM integration framework and core functionality
    2. ✅ Persistent storage for generated content 
    3. 🔜 Basic content generation modules (NPCs, rules clarification)
    4. 🔜 Fast combat resolution system
    5. Core reference functionality enhancements
    6. Campaign management tools expansion
    7. Advanced LLM generation features

Success Metrics
    - Reduced lookup time vs. physical DM screen
    - Increased encounter/treasure generation speed
    - Positive user feedback on customization
    - Regular user engagement
    - 🔜 Quality and usability of LLM-generated content
    - 🔜 Time saved using AI-assisted content generation
    - 🔜 Reduction in combat resolution time while maintaining narrative quality

Future Considerations
    - 🔜 Voice-to-text for hands-free LLM prompting
    - 🔜 Fine-tuning LLM models for D&D-specific generation
    - 🔜 Integration with image generation for visual assets
    - 🔜 LLM-powered storytelling assistance during gameplay
    - Virtual tabletop system compatibility
    - Digital character sheet integration
    - Content sharing system for LLM-generated material

Accessibility Requirements
    - Screen reader compatibility
    - Keyboard navigation
    - Color blind friendly design
    - Font size/contrast adjustments
    - Multi-language support
    - 🔜 Voice-controlled LLM prompting for accessibility

This specification will be regularly updated based on user feedback and emerging needs in the D&D community.