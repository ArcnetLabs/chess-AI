# Frontend Chatbot - Implementation Plan

**Goal:** Build a minimalist floating chatbot UI for the AI Chess Coach

---

## 📋 Quick Summary

**Design:** Discord-style floating chatbot icon → Fixed popup window (380x600px)

**Tech Stack:**
- React + TypeScript
- TailwindCSS for styling
- Zustand for state management
- Framer Motion for animations
- Axios for API calls

**Key Features:**
- Floating icon (bottom-right, 60x60px)
- Notification badge
- Chat popup (non-fullscreen)
- Message history
- Typing indicators
- Analysis cards
- Suggestion chips
- Auto-detect chess position

---

## 🎯 Components to Build (8 Total)

### 1. **ChatbotIcon** - Floating button
- Circular icon with chess knight/robot
- Notification badge
- Pulse animation
- Click to open/close

### 2. **ChatWindow** - Main popup container
- 380x600px fixed window
- Slide-up animation
- Header + Messages + Input

### 3. **ChatHeader** - Title bar
- "Chess Coach" title
- Online status
- Minimize/Close buttons

### 4. **MessageList** - Messages container
- Auto-scroll to bottom
- User vs Assistant messages
- Timestamps
- Loading skeleton

### 5. **ChatInput** - Text input
- Auto-resize textarea
- Send button
- Enter to send
- Loading state

### 6. **TypingIndicator** - Animated dots
- Shows when coach is "thinking"

### 7. **SuggestionChips** - Quick actions
- Clickable suggestion buttons
- From backend responses

### 8. **AnalysisCard** - Position analysis display
- Evaluation, best move, themes
- Formatted nicely

---

## 🔌 API Integration

**Endpoints to Use:**
```typescript
POST /api/v1/chat/session          // Create session
POST /api/v1/chat/message          // Send message
GET  /api/v1/chat/session/{id}/history  // Get history
DELETE /api/v1/chat/session/{id}   // End session
```

**Flow:**
1. User opens chat → Create session
2. User sends message → POST to /message
3. Display response with analysis
4. Show suggestions as chips
5. Auto-include current board position (FEN)

---

## 📁 File Structure

```
frontend/src/
├── components/
│   └── chat/
│       ├── ChatbotIcon.tsx
│       ├── ChatWindow.tsx
│       ├── ChatHeader.tsx
│       ├── MessageList.tsx
│       ├── Message.tsx
│       ├── ChatInput.tsx
│       ├── TypingIndicator.tsx
│       ├── SuggestionChips.tsx
│       └── AnalysisCard.tsx
│
├── services/
│   └── chatService.ts
│
├── store/
│   └── chatStore.ts
│
├── hooks/
│   ├── useChat.ts
│   └── useChatSession.ts
│
└── types/
    └── chat.types.ts
```

---

## 🎨 Visual Design

**Colors:**
- Primary: `#3B82F6` (Blue)
- Background: `#FFFFFF` (White)
- Text: `#111827` (Dark)
- Border: `#E5E7EB` (Light Gray)

**Layout:**
```
Closed:                    Open:
                          ┌──────────────┐
                          │ Chess Coach  │
                          ├──────────────┤
                          │ Messages...  │
                          │              │
                          ├──────────────┤
        ┌────┐            │ Type here... │
        │ 🤖 │            └──────────────┘
        └────┘
```

---

## 🚀 Implementation Steps

### Step 1: Setup & Types (30 min)
- [ ] Create types/chat.types.ts
- [ ] Define interfaces (Message, ChatResponse, etc.)
- [ ] Setup TailwindCSS config

### Step 2: State Management (30 min)
- [ ] Create chatStore.ts (Zustand)
- [ ] Define state (isOpen, messages, sessionId)
- [ ] Add actions (openChat, sendMessage, etc.)

### Step 3: API Service (30 min)
- [ ] Create chatService.ts
- [ ] Implement API calls
- [ ] Error handling

### Step 4: Core Components (2 hours)
- [ ] ChatbotIcon.tsx
- [ ] ChatWindow.tsx
- [ ] ChatHeader.tsx
- [ ] MessageList.tsx
- [ ] ChatInput.tsx

### Step 5: Enhanced Components (1 hour)
- [ ] TypingIndicator.tsx
- [ ] SuggestionChips.tsx
- [ ] AnalysisCard.tsx

### Step 6: Integration (1 hour)
- [ ] Connect to backend API
- [ ] Test message flow
- [ ] Handle errors

### Step 7: Polish (1 hour)
- [ ] Animations
- [ ] Responsive design
- [ ] Accessibility

**Total Time:** ~6-7 hours

---

## 🎯 Success Criteria

- ✅ Floating icon appears bottom-right
- ✅ Click opens chat popup (380x600px)
- ✅ Can send messages to backend
- ✅ Displays responses with analysis
- ✅ Suggestion chips work
- ✅ Typing indicator shows
- ✅ Auto-scrolls to new messages
- ✅ Responsive on mobile
- ✅ Smooth animations

---

## 📝 Next Steps

1. Review this plan
2. Start with Step 1 (Types & Setup)
3. Build components incrementally
4. Test each component
5. Integrate with backend
6. Polish and deploy

**Ready to start building!** 🚀
