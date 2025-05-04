# Fast Resolve Feature - Program Flow Analysis

## Overview

The 'Fast Resolve' feature provides automated turn-by-turn combat resolution using an LLM (Large Language Model) to generate tactical decisions for combatants. This document traces the program flow from button click to completion, highlighting key components, potential bottlenecks, and failure points.

## Program Flow

### 1. Initialization and UI Trigger

1. **User Interface Setup**
   - The Fast Resolve button is initialized in `CombatTrackerPanel._setup_control_area`
   - Button is connected to the `_fast_resolve_combat` method

2. **Button Click Handling**
   - User clicks "Fast Resolve" button
   - `CombatTrackerPanel._handle_fast_resolve_click` is triggered
   - A safety timer is started (to reset the button if process hangs)
   - Button is disabled and text changed to "Resolving..."

### 2. Combat Resolution Setup

1. **Combat State Preparation**
   - Current combat state is copied from the tracker
   - `ImprovedCombatResolver.prepare_combat_data` validates monster abilities
   - Monster data validation removes invalid/mixed abilities using `validate_monster_abilities`

2. **Resolution Thread Initialization**
   - Combat resolver instance is obtained (either ImprovedCombatResolver or CombatResolver)
   - `setup_and_start_combat` creates a thread for asynchronous resolution
   - Inside `start_resolution`, the resolver initializes its state variables:
     - Sets `_running = True`, `_paused = False`, `_stop_requested = False`
     - Stores combat state, dice roller, and callback references

### 3. LLM-Based Turn Resolution Loop

1. **Resolution Thread Execution**
   - The `_run_resolution_thread` method is the main execution loop
   - For each turn, the following occurs:

2. **Turn Processing**
   - `_process_turn` handles a single combatant's turn
   - Combat state is analyzed for the active combatant
   
3. **LLM Prompt Creation**
   - `_create_decision_prompt` builds a detailed prompt describing:
     - Current combat state
     - Active combatant's abilities and position
     - Available targets and their conditions
     - Previous turn summaries (for context)
   - Prompt is validated using `validate_combat_prompt` to ensure accuracy
   - Abilities in the prompt are cleaned with `clean_abilities_in_prompt` and `fix_mixed_abilities_in_prompt`

4. **LLM API Call**
   - `LLMService.generate_completion` sends the prompt to the LLM
   - Wrapped by `logged_generate_completion` in monitor_llm_calls.py
   - Call is made with appropriate retry and timeout logic
   - Response is logged to LLM monitoring system

5. **Response Parsing**
   - `_parse_llm_json_response` attempts to extract structured JSON from LLM response
   - Complex error handling for malformed JSON, incomplete responses
   - JSON file artifacts are saved to llm_logs directory for debugging
   - If parsing fails, fallback actions are generated

6. **Action Execution**
   - Parsed actions are executed using the dice roller
   - Action results are applied to combat state via `_apply_turn_updates`
   - Combat log is updated with narrative descriptions
   - UI is updated through callback mechanism

7. **Loop Continuation**
   - Next combatant is determined via initiative order
   - End conditions are checked via `_check_combat_end_condition`
   - Loop continues until combat ends or user stops resolution

### 4. Resolution Completion

1. **Combat Resolution Finalization**
   - Final combat state is prepared
   - Results are sent via `resolution_update` signal
   - `_reset_resolve_button` is called to restore button state
   - UI is updated with final combat state and summary

2. **Error Handling**
   - If any exception occurs, error is logged and button reset
   - Safety timer ensures UI doesn't remain in "Resolving..." state

## Critical Components and Potential Failure Points

### LLM Integration Points

1. **LLM Service Interface**
   - `LLMService.generate_completion` is the primary interface for LLM calls
   - Failures here cascade throughout the resolution process
   - Timeouts or rate limits from the LLM provider can cause stalls

2. **JSON Parsing**
   - `_parse_llm_json_response` is highly sensitive to LLM output format
   - Malformed JSON or unexpected response structures can break resolution
   - Parsing logic contains extensive but potentially incomplete error handling

3. **Prompt Construction**
   - `_create_decision_prompt` must produce clear, consistent prompts
   - Validation layer attempts to catch ability mixing and invalid data
   - Monster ability validation can remove critical abilities if too strict

### Concurrency and State Management

1. **Thread Safety Mechanisms**
   - Threading lock (`_lock`) protects state variables
   - Events and signals coordinate between threads
   - Race conditions may occur during button reset or UI updates

2. **Safety Timeout**
   - Safety timer attempts to prevent UI lockup
   - May trigger prematurely for complex combats with many entities
   - Only resets button state but doesn't terminate hung resolution thread

### Error Recovery

1. **Fallback Actions**
   - When LLM responses fail, simple fallback actions are generated
   - These may lack tactical sophistication or rule compliance
   - Repeated fallbacks can make combat outcomes unrealistic

2. **Error Propagation**
   - Errors during resolution can cause inconsistent combat state
   - Combat log messages may not accurately reflect what happened
   - Partial updates can leave combat in unrecoverable state

## Performance Bottlenecks

1. **LLM Response Time**
   - Primary performance bottleneck is LLM API call latency
   - Each turn requires a separate LLM call with growing context
   - Previous turn summaries increase token count over time

2. **Context Management**
   - Maintaining previous turn context for LLM can cause memory growth
   - Large combat scenarios with many entities create verbose prompts
   - Token limits may be exceeded in extended combats

3. **Validation Overhead**
   - Extensive validation of monster abilities adds processing time
   - Multiple regex and string comparisons during prompt creation
   - Each validation layer adds incremental latency

## Improvement Opportunities

1. **Prompt Engineering**
   - Review prompt structure to reduce token count while maintaining context
   - Implement better summarization of previous turns
   - Add more explicit format instructions to reduce parsing failures

2. **Parallel Processing**
   - Pre-compute likely actions for next combatants while waiting for LLM
   - Batch process multiple turns when possible
   - Implement progressive rendering of turn results

3. **Robust Error Recovery**
   - Improve fallback action selection with rule-based tactics
   - Add combat state validation between turns
   - Implement transaction-like updates to prevent partial state changes

4. **Monitoring and Diagnostics**
   - Enhance LLM call monitoring with performance metrics
   - Add structured logging for turn resolution steps
   - Create visualization tools for resolution flow and decision points

By addressing these areas, the Fast Resolve feature could become more reliable, efficient, and provide better tactical decisions during combat resolution.
