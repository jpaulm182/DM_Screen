# Database Integration Plan for DM Screen

## Overview
This document outlines a step-by-step plan to consolidate all program data sources (session notes, LLM content, monsters, NPCs, etc.) into a single unified SQLite database. The goal is to simplify data management, improve maintainability, and enable richer cross-feature integrations.

---

## Note on Existing Database Files
- During investigation, the following database files were found:
  - `data/app.db`: Present but **empty and unused** (0 bytes, no tables or data).
  - `data/app.db.bak_*`: Backup of the above, also empty.
  - `test_data/data/dm_screen.db`: Contains LLM-related tables (`llm_conversations`, `llm_messages`, `llm_generated_content`), but appears to be for **testing purposes only** and is not used by the main application.
- **Conclusion:**
  - The actual runtime database is likely determined by the configuration in `app/core/config.py` (see `get_database_path()`), which defaults to `dm_screen.db` in the main app directory.
  - Only the unified database file (e.g., `dm_screen.db`) should be used for production data after integration.

---

## 1. Reasoning and Goals
- **Current State:**
  - Data is spread across multiple tables and possibly multiple database files (e.g., session_notes, llm_generated_content, monsters, npcs, etc.).
  - Some features (like LLM content and session notes) are isolated, making cross-referencing and advanced queries difficult.
- **Goals:**
  - Store all core data in a single, well-structured SQLite database.
  - Enable easy linking between entities (e.g., notes referencing monsters, LLM content linked to notes).
  - Simplify backup, migration, and future feature development.
  - Maintain clear, modular, and well-documented schema.

---

## 2. Unified Schema Design
- **Single Database File:** All tables reside in one file (e.g., `dm_screen.db`).
- **Core Tables:**
  - `session_notes`: Stores all session notes, with support for origin links.
  - `llm_generated_content`: Stores all LLM-generated content (NPCs, locations, items, etc.).
  - `monsters`, `npcs`, `encounters`, `custom_monsters`, etc.: Store reference and custom content.
  - `users`, `campaigns`, `settings` (optional, for future expansion).
- **Foreign Keys:** Use integer or text foreign keys to link related records (e.g., `origin_note_id`, `llm_content_id`).
- **Example Table Relationships:**
  - `session_notes.origin_note_id` → `session_notes.id`
  - `llm_generated_content.note_id` → `session_notes.id` (optional, for generated notes)
  - `monsters.llm_content_id` → `llm_generated_content.id` (optional, for LLM-generated monsters)

---

## 3. Migration Steps
1. **Inventory Existing Data:**
   - List all current tables and their schemas in all database files.
   - Identify duplicate or overlapping data.
2. **Design Unified Schema:**
   - Draft the new schema, ensuring all required fields and relationships are present.
   - Add migration fields (e.g., `legacy_id`, `source_table`) if needed for traceability.
3. **Create Migration Scripts:**
   - For each table, write a script to copy data into the new unified schema.
   - Handle ID remapping and foreign key updates.
   - Ensure all data is migrated, including timestamps and tags.
4. **Test Migration:**
   - Run migration scripts on a copy of the data.
   - Validate row counts, field values, and relationships.
   - Fix any issues and rerun as needed.
5. **Switch Application to Unified DB:**
   - Update all code to use the new database file and schema.
   - Remove or archive old database files.

---

## 4. Example Unified Schema (SQLite)
```sql
CREATE TABLE session_notes (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    origin_note_id INTEGER,
    FOREIGN KEY(origin_note_id) REFERENCES session_notes(id)
);

CREATE TABLE llm_generated_content (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content TEXT NOT NULL,
    model_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    tags TEXT,
    created_at TEXT NOT NULL,
    note_id INTEGER,
    FOREIGN KEY(note_id) REFERENCES session_notes(id)
);

CREATE TABLE monsters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    cr TEXT NOT NULL,
    size TEXT NOT NULL,
    alignment TEXT NOT NULL,
    ac INTEGER NOT NULL,
    hp TEXT NOT NULL,
    speed TEXT NOT NULL,
    str INTEGER NOT NULL,
    dex INTEGER NOT NULL,
    con INTEGER NOT NULL,
    int INTEGER NOT NULL,
    wis INTEGER NOT NULL,
    cha INTEGER NOT NULL,
    skills TEXT,
    senses TEXT,
    languages TEXT,
    traits TEXT,
    actions TEXT,
    legendary_actions TEXT,
    description TEXT,
    source TEXT NOT NULL,
    llm_content_id TEXT,
    FOREIGN KEY(llm_content_id) REFERENCES llm_generated_content(id)
);
-- Add other tables as needed
```

---

## 5. Application Code Integration
- **DatabaseManager:**
  - Update to use the unified schema and handle all new relationships.
  - Add helper methods for cross-table queries (e.g., get all notes generated from a specific LLM content).
- **UI Panels:**
  - Update all panels to use the unified database.
  - Add UI for linking and displaying related entities (e.g., show LLM-generated NPCs in notes).
- **Testing:**
  - Add tests for all CRUD operations and cross-entity queries.
  - Test migration on real user data.

---

## 6. Testing & Validation
- **Unit Tests:** For all new DB methods and migration scripts.
- **Manual QA:**
  - Verify all data is present and correct after migration.
  - Check that all links and references work in the UI.
- **Backup:** Always back up all data before running migrations.

---

## 7. Comments & Documentation
- Document all schema changes and migration steps in code and in this file.
- Add comments to all migration scripts explaining each step.
- Keep this document updated as the integration progresses.

---

## 8. Future-Proofing
- Design schema to allow for future expansion (e.g., campaigns, user accounts, more entity types).
- Use foreign keys and indexes for performance and data integrity.

---

# End of Plan 