# Recommendations for Fast Resolve Feature Improvement

Based on the analysis of `llm_trace.md`, here are recommendations to address identified flaws and enhance the 'Fast Resolve' feature for a best-in-class implementation:

1.  **Hybrid LLM + Rules Engine Approach:**
    *   **Concept:** Use the LLM for high-level strategy and intent (e.g., "Attack the Goblin Shaman with Fire Bolt"), and a deterministic rules engine for mechanical execution (rolls, damage, saves, conditions).
    *   **Flow:** LLM suggests strategic intent -> Parse intent -> Pass intent to Rules Engine -> Rules Engine executes mechanics according to 5e rules.
    *   **Benefits:** Reduces reliance on perfect LLM formatting, ensures rule compliance, improves speed for standard actions, potentially lowers LLM costs.

2.  **Robust Structured Output Handling:**
    *   Utilize LLM features for structured output (e.g., OpenAI Function Calling, JSON Mode).
    *   Use explicit prompt instructions and few-shot examples for the desired format.
    *   Implement resilient JSON parsing (handle minor errors, attempt repairs).
    *   Use validation schemas (e.g., Pydantic) to check parsed data structure and types.

3.  **Intelligent Context Summarization:**
    *   Replace raw turn-by-turn history in prompts with a structured, summarized combat log focusing on key events (significant damage, conditions applied/removed, enemies defeated, strategic shifts).
    *   Limit the lookback window or use relevance filtering to keep context concise.

4.  **Sophisticated, Multi-Tiered Fallback System:**
    *   If LLM interaction fails:
        *   **Tier 1:** Retry LLM call (perhaps with modified prompt).
        *   **Tier 2:** Engage a Rule-Based Tactical Engine (heuristics based on creature role, HP, resources, target priority).
        *   **Tier 3:** Simplest default action (Dodge, basic Attack) as a last resort.

5.  **Asynchronous Lookahead/Prefetching:**
    *   While awaiting the current turn's LLM response, prepare prompt data for the *next* combatant.
    *   Consider speculative LLM calls for the next turn if the state change is unlikely to be drastic (use with caution).

6.  **Transactional State Updates & Validation:**
    *   Snapshot combat state before applying a turn's actions.
    *   Apply actions.
    *   Validate the resulting state for inconsistencies (HP vs. status, positions).
    *   Roll back to the snapshot on error to prevent state corruption.

7.  **Effective Thread Management:**
    *   Ensure the safety timer or equivalent can reliably signal the resolution thread to terminate cleanly (`_stop_requested` flag) and join the thread properly. Avoid orphaned processes.

8.  **Refined Validation Logic:**
    *   Shift primary validation from *input* abilities/data to the *LLM's chosen action*. Validate the *selected action*, target, and parameters against 5e rules *after* parsing but *before* applying it to the combat state.

By implementing these changes, the 'Fast Resolve' feature can become significantly more reliable, performant, and tactically sound.
