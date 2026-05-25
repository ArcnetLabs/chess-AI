# Phase 3: AI Chess Coaching Chatbot - Implementation Plan

**Goal:** Conversational chess coach that combines Stockfish analysis with LLM natural language understanding

---

## Architecture Overview

```
User Message → Chat Service → Intent Classifier
                                    ↓
                    ┌───────────────┴───────────────┐
                    ↓                               ↓
            Chess-Related                    General Chat
                    ↓                               ↓
        ┌───────────┴───────────┐                 LLM
        ↓                       ↓                   ↓
   Position Analysis      Move Question         Response
        ↓                       ↓
   Stockfish              Stockfish
        ↓                       ↓
   LLM Explanation        LLM Explanation
        ↓                       ↓
        └───────────────┬───────────────┘
                        ↓
                  Final Response
```

---

## Components to Build

### 1. Chat Service
**File:** `app/services/chat/chess_coach.py`

**Features:**
- Intent classification (position analysis, move question, general chat)
- Context management (conversation history)
- User profile integration (skill level, recent games)
- Hybrid Stockfish + LLM responses

### 2. Intent Classifier
**File:** `app/services/chat/intent_classifier.py`

**Intents:**
- `analyze_position` - User wants position analyzed
- `explain_move` - User asks about a specific move
- `compare_moves` - User wants to compare options
- `general_question` - General chess questions
- `small_talk` - Non-chess conversation

### 3. Context Manager
**File:** `app/services/chat/context_manager.py`

**Features:**
- Store conversation history
- Track current position/game
- Remember user preferences
- Maintain coaching context

### 4. Response Generator
**File:** `app/services/chat/response_generator.py`

**Features:**
- Format Stockfish analysis for users
- Generate educational explanations
- Adapt language to user skill level
- Include follow-up suggestions

### 5. Chat API
**File:** `app/api/chat.py`

**Endpoints:**
- `POST /api/chat/message` - Send message, get response
- `POST /api/chat/session` - Start new chat session
- `GET /api/chat/history/{session_id}` - Get chat history
- `DELETE /api/chat/session/{session_id}` - End session

### 6. Database Models
**File:** `app/models/chat.py`

**Models:**
- `ChatSession` - Chat session metadata
- `ChatMessage` - Individual messages
- `ChatContext` - Current position/game state

---

## Implementation Steps

### Step 1: Create Chat Service Core
- Build ChessCoach class
- Implement intent classification
- Add context management
- Integrate with existing AIClient

### Step 2: Implement Hybrid Analysis
- Route chess questions to Stockfish
- Format analysis for LLM explanation
- Generate conversational responses
- Add skill-level adaptation

### Step 3: Add Context Management
- Store conversation history
- Track current position
- Remember user preferences
- Maintain coaching state

### Step 4: Build API Endpoints
- Chat message endpoint
- Session management
- History retrieval
- Context updates

### Step 5: Database Integration
- Create chat tables
- Store messages
- Track sessions
- Cache analyses

### Step 6: Testing
- Unit tests for intent classification
- Integration tests for hybrid responses
- Conversation flow tests
- Performance testing

---

## Data Structures

### ChatMessage
```python
{
    "id": "msg_123",
    "session_id": "session_456",
    "role": "user" | "assistant",
    "content": "What's the best move here?",
    "position_fen": "rnbqkbnr/...",  # Optional
    "intent": "explain_move",
    "timestamp": "2026-03-28T22:50:00Z",
    "metadata": {
        "analysis_used": true,
        "stockfish_depth": 18
    }
}
```

### ChatSession
```python
{
    "id": "session_456",
    "user_id": 1,
    "started_at": "2026-03-28T22:45:00Z",
    "last_activity": "2026-03-28T22:50:00Z",
    "current_position": "rnbqkbnr/...",
    "context": {
        "skill_level": "intermediate",
        "focus_areas": ["tactics", "endgame"],
        "recent_topics": ["italian_game", "forks"]
    }
}
```

---

## Intent Classification

### Pattern Matching
```python
intents = {
    "analyze_position": [
        "analyze this position",
        "what should I do here",
        "evaluate this position",
        "how good is this position"
    ],
    "explain_move": [
        "why is [move] good",
        "explain [move]",
        "what does [move] do",
        "is [move] better than [move]"
    ],
    "compare_moves": [
        "compare [move] and [move]",
        "which is better",
        "[move] or [move]"
    ],
    "general_question": [
        "how do I improve",
        "what should I study",
        "tips for [topic]"
    ]
}
```

### LLM-Based Classification (Fallback)
```python
prompt = f"""
Classify this chess coaching question:
"{user_message}"

Intent options:
- analyze_position: User wants position analyzed
- explain_move: User asks about a move
- compare_moves: User wants to compare moves
- general_question: General chess question
- small_talk: Non-chess conversation

Intent:
"""
```

---

## Response Templates

### Position Analysis Response
```
I've analyzed this position for you!

📊 Evaluation: {evaluation}
🎯 Best Move: {best_move}

{explanation}

The key ideas here are:
• {tactical_theme_1}
• {tactical_theme_2}

Would you like me to explain any specific move in detail?
```

### Move Explanation Response
```
Great question about {move}!

{move} is {evaluation_description} because:
✓ {pro_1}
✓ {pro_2}
⚠️ {con_1}

{stockfish_analysis}

This move demonstrates {tactical_theme}. {educational_insight}

Want to see what happens after {move}?
```

### General Question Response
```
{personalized_greeting}

{answer_based_on_user_data}

Based on your recent games, I'd recommend:
1. {recommendation_1}
2. {recommendation_2}

{follow_up_question}
```

---

## Hybrid Stockfish + LLM Flow

### Example: "What's the best move here?"

1. **Intent Classification:** `analyze_position`
2. **Extract FEN:** From context or user message
3. **Stockfish Analysis:**
   ```python
   analysis = await move_recommender.analyze_position(fen, num_moves=3)
   best_move = analysis.candidate_moves[0]
   ```
4. **LLM Explanation:**
   ```python
   prompt = f"""
   You're a friendly chess coach. Explain this analysis to a {skill_level} player:
   
   Position: {fen}
   Best move: {best_move.move}
   Evaluation: {best_move.evaluation}
   Themes: {best_move.tactical_themes}
   Explanation: {best_move.explanation}
   
   Make it conversational and educational.
   """
   response = await ai_client.chat_completion(prompt)
   ```
5. **Return Response:** Formatted, conversational answer

---

## Context-Aware Features

### User Skill Level Adaptation
- **Beginner:** Simple language, basic concepts, encourage learning
- **Intermediate:** Tactical patterns, strategic ideas, variations
- **Advanced:** Deep analysis, subtle nuances, opening theory
- **Master:** Complex evaluations, engine lines, theoretical discussions

### Conversation Memory
- Remember previous positions discussed
- Reference earlier questions
- Track learning progress
- Suggest related topics

### Personalization
- Use user's name
- Reference their recent games
- Adapt to their weaknesses (from Phase 1 insights)
- Celebrate improvements

---

## API Examples

### Send Chat Message
```bash
POST /api/v1/chat/message
{
    "session_id": "session_456",
    "message": "What's the best move in this position?",
    "position_fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
}

Response:
{
    "success": true,
    "response": {
        "message": "Great question! I've analyzed this position...",
        "intent": "analyze_position",
        "analysis": {
            "best_move": "Nf6",
            "evaluation": 0.2,
            "explanation": "..."
        },
        "suggestions": [
            "Would you like to see what happens after Nf6?",
            "Want to compare Nf6 with other moves?"
        ]
    }
}
```

### Start Chat Session
```bash
POST /api/v1/chat/session
{
    "user_id": 1
}

Response:
{
    "success": true,
    "session_id": "session_789",
    "message": "Hi! I'm your chess coach. What would you like to work on today?"
}
```

---

## Success Criteria

- ✅ Chatbot understands chess-related questions
- ✅ Integrates Stockfish analysis seamlessly
- ✅ Provides conversational, educational responses
- ✅ Maintains conversation context
- ✅ Adapts to user skill level
- ✅ Response time < 5 seconds
- ✅ Handles edge cases gracefully

---

## Timeline

**Estimated Time:** 4-6 hours

- **Step 1:** Chat service core (1.5 hours)
- **Step 2:** Hybrid analysis (1 hour)
- **Step 3:** Context management (1 hour)
- **Step 4:** API endpoints (1 hour)
- **Step 5:** Database models (0.5 hour)
- **Step 6:** Testing (1 hour)

---

## Dependencies

- ✅ Stockfish engine (Phase 2)
- ✅ Move recommender (Phase 2)
- ✅ AIClient (existing)
- ✅ User insights (Phase 1)
- ⚠️ LLM API key (OpenAI/OpenRouter) - optional for now

---

**Ready to implement!** Starting with the chess coach service.
