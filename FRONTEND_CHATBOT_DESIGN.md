# Chess Coaching Chatbot - Frontend Design Document

**Date:** April 9, 2026  
**Purpose:** Minimalist floating chatbot UI for AI Chess Coach

---

## 🎯 Design Goals

- **Minimalist & Non-Intrusive** - Floating icon like Discord/Intercom
- **Fixed Popup Window** - Not fullscreen, positioned bottom-right
- **Responsive & Smooth** - Animations, typing indicators, smooth UX
- **Context-Aware** - Integrates with chess board, game analysis
- **Mobile-Friendly** - Works on all screen sizes

---

## 🎨 UI/UX Design

### Visual Style
```
Design Language: Modern, Clean, Chess-Themed
Colors:
  - Primary: #3B82F6 (Blue)
  - Secondary: #1F2937 (Dark Gray)
  - Accent: #10B981 (Green for success)
  - Background: #FFFFFF (White)
  - Text: #111827 (Almost Black)
  - Border: #E5E7EB (Light Gray)

Typography:
  - Font: Inter, system-ui, sans-serif
  - Sizes: 14px (body), 12px (metadata), 16px (headings)

Spacing:
  - Consistent 8px grid system
  - Padding: 12px, 16px, 24px
  - Gaps: 8px, 12px, 16px
```

---

## 📐 Layout Structure

### 1. Floating Chat Icon (Closed State)
```
┌─────────────────────────────────────┐
│                                     │
│                                     │
│                                     │
│                                     │
│                              ┌────┐ │
│                              │ 🤖 │ │ ← Floating Icon
│                              └────┘ │    (60x60px)
│                                  ↑  │    Bottom-right
└──────────────────────────────────┼──┘    24px from edges
                                   │
                              Notification
                                 Badge
```

**Features:**
- 60x60px circular button
- Chess knight icon or robot emoji
- Pulse animation on new messages
- Notification badge (red dot with count)
- Fixed position: `bottom: 24px, right: 24px`
- Shadow: `0 4px 12px rgba(0,0,0,0.15)`
- Hover: Scale up to 1.05, deeper shadow

---

### 2. Chat Popup Window (Open State)
```
┌─────────────────────────────────────┐
│                                     │
│                  ┌────────────────┐ │
│                  │  Chat Header   │ │ ← Header (60px)
│                  ├────────────────┤ │
│                  │                │ │
│                  │   Messages     │ │ ← Message Area
│                  │   Container    │ │   (400px height)
│                  │                │ │   Scrollable
│                  │                │ │
│                  ├────────────────┤ │
│                  │  Input Box     │ │ ← Input (80px)
│                  └────────────────┘ │
│                              ┌────┐ │
│                              │ × │ │ ← Close Icon
└──────────────────────────────└────┘─┘
```

**Dimensions:**
- Width: 380px (mobile: 100vw - 32px)
- Height: 600px (mobile: 80vh)
- Position: Fixed bottom-right
- Offset: 24px from bottom, 24px from right
- Border radius: 16px
- Shadow: `0 8px 24px rgba(0,0,0,0.2)`

---

## 🧩 Component Breakdown

### Component 1: ChatbotIcon
**File:** `components/ChatbotIcon.tsx`

```typescript
interface ChatbotIconProps {
  onClick: () => void;
  unreadCount: number;
  isOpen: boolean;
}

Features:
- Circular floating button
- Notification badge
- Pulse animation
- Smooth open/close transition
- Accessibility (ARIA labels)
```

**Visual States:**
- **Default:** Blue background, white icon
- **Hover:** Scale 1.05, deeper shadow
- **Active:** Slightly pressed effect
- **With Notifications:** Red badge with count

---

### Component 2: ChatWindow
**File:** `components/ChatWindow.tsx`

```typescript
interface ChatWindowProps {
  isOpen: boolean;
  onClose: () => void;
  sessionId?: string;
  currentPosition?: string; // FEN
}

Sections:
1. Header (ChatHeader)
2. Messages (MessageList)
3. Input (ChatInput)
```

**Layout:**
```
┌──────────────────────────────────┐
│ 🤖 Chess Coach          [−] [×] │ ← Header
├──────────────────────────────────┤
│ ┌──────────────────────────────┐ │
│ │ Coach: Hi! I'm your chess... │ │ ← Assistant Message
│ └──────────────────────────────┘ │
│                                  │
│           ┌────────────────────┐ │
│           │ User: Analyze e4   │ │ ← User Message
│           └────────────────────┘ │
│                                  │
│ ┌──────────────────────────────┐ │
│ │ Coach: Great question! ...   │ │ ← Assistant Message
│ │ 📊 Evaluation: +0.4          │ │   with Analysis
│ │ 🎯 Best Move: e4             │ │
│ └──────────────────────────────┘ │
│                                  │
│ [Typing indicator...]           │ ← Typing State
├──────────────────────────────────┤
│ 💡 Suggestions:                 │ ← Quick Actions
│ [Analyze position] [Explain...] │
├──────────────────────────────────┤
│ Type your message...        [→] │ ← Input
└──────────────────────────────────┘
```

---

### Component 3: ChatHeader
**File:** `components/chat/ChatHeader.tsx`

```typescript
Features:
- Coach avatar/icon
- Title: "Chess Coach"
- Status indicator (online/typing)
- Minimize button
- Close button
```

**Layout:**
```
┌────────────────────────────────────┐
│ 🤖  Chess Coach  ●Online  [−] [×] │
└────────────────────────────────────┘
```

---

### Component 4: MessageList
**File:** `components/chat/MessageList.tsx`

```typescript
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  analysis?: PositionAnalysis;
  suggestions?: string[];
}

Features:
- Auto-scroll to bottom
- Timestamp display
- Message grouping
- Analysis cards
- Suggestion chips
- Loading skeleton
```

**Message Types:**

**1. User Message:**
```
                    ┌──────────────────┐
                    │ What's the best  │
                    │ move here?       │
                    └──────────────────┘
                           11:23 PM
```

**2. Assistant Text Message:**
```
┌────────────────────────────────────┐
│ 🤖 I've analyzed this position!    │
│                                    │
│ The best move is e4 because...    │
└────────────────────────────────────┘
11:23 PM
```

**3. Assistant with Analysis:**
```
┌────────────────────────────────────┐
│ 🤖 I've analyzed this position!    │
│                                    │
│ 📊 Evaluation: +0.4                │
│ 🎯 Best Move: e4                   │
│ 🎲 Phase: Opening                  │
│                                    │
│ Key ideas:                         │
│ • Controls the center              │
│ • Develops pieces                  │
│                                    │
│ ┌────────────┐ ┌────────────┐     │
│ │ Explain e4 │ │ Compare... │     │ ← Suggestion Chips
│ └────────────┘ └────────────┘     │
└────────────────────────────────────┘
```

---

### Component 5: ChatInput
**File:** `components/chat/ChatInput.tsx`

```typescript
Features:
- Auto-resize textarea
- Send button
- Loading state
- Character limit (500)
- Enter to send (Shift+Enter for new line)
- Disabled during loading
```

**Layout:**
```
┌────────────────────────────────────┐
│ Type your message...          [→] │
└────────────────────────────────────┘
```

**States:**
- **Empty:** Placeholder visible, send button disabled
- **Typing:** Send button enabled (blue)
- **Sending:** Loading spinner, input disabled
- **Error:** Red border, error message below

---

### Component 6: TypingIndicator
**File:** `components/chat/TypingIndicator.tsx`

```
┌──────────────────┐
│ ● ● ●  Typing... │ ← Animated dots
└──────────────────┘
```

---

### Component 7: SuggestionChips
**File:** `components/chat/SuggestionChips.tsx`

```typescript
interface Suggestion {
  text: string;
  action: () => void;
}

Layout:
┌────────────┐ ┌────────────┐ ┌────────────┐
│ Analyze    │ │ Explain e4 │ │ Compare... │
└────────────┘ └────────────┘ └────────────┘
```

---

### Component 8: AnalysisCard
**File:** `components/chat/AnalysisCard.tsx`

```typescript
interface AnalysisCardProps {
  evaluation: number;
  bestMove: string;
  phase: string;
  themes: string[];
  alternatives?: Move[];
}

Layout:
┌────────────────────────────────────┐
│ 📊 Position Analysis               │
├────────────────────────────────────┤
│ Evaluation: +0.4 (Slight edge)     │
│ Best Move: e4                      │
│ Phase: Opening                     │
│                                    │
│ Tactical Themes:                   │
│ • Center Control                   │
│ • Development                      │
│                                    │
│ Top Alternatives:                  │
│ 1. e4 (+0.4)                       │
│ 2. d4 (+0.3)                       │
│ 3. Nf3 (+0.3)                      │
└────────────────────────────────────┘
```

---

## 🔄 User Flows

### Flow 1: First Time User
```
1. User logs in
2. Sees floating chatbot icon (pulsing)
3. Clicks icon
4. Chat window opens with welcome message:
   "Hi! I'm your AI chess coach. I can help you with:
    🔍 Position Analysis
    📚 Move Explanations
    ⚖️ Move Comparisons
    💡 General Advice
    
    What would you like to work on today?"
5. User types question or clicks suggestion
6. Coach responds with analysis
```

### Flow 2: Position Analysis
```
1. User is viewing a game/position
2. Clicks chatbot icon
3. Types: "What's the best move here?"
4. System auto-detects current board position (FEN)
5. Coach analyzes and responds:
   - Evaluation
   - Best move
   - Tactical themes
   - Suggestions
6. User can click suggestions for follow-up
```

### Flow 3: Move Explanation
```
1. User types: "Why is e4 good?"
2. System extracts move "e4"
3. Coach explains:
   - Evaluation
   - Pros/cons
   - Tactical themes
   - Sample variations
4. Suggestions: "Compare with d4", "Show continuation"
```

### Flow 4: Conversation Context
```
1. User: "Analyze this position" + FEN
2. Coach: [Full analysis]
3. User: "Why is e4 better than d4?"
   (System remembers previous position)
4. Coach: [Comparison using stored context]
5. User: "Show me the continuation"
   (System remembers e4 was discussed)
6. Coach: [Variation after e4]
```

---

## 🎬 Animations & Transitions

### Icon Animations
```css
/* Pulse on new message */
@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

/* Hover effect */
.chat-icon:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 16px rgba(0,0,0,0.2);
}

/* Open/Close */
.chat-icon.open {
  transform: rotate(90deg);
  opacity: 0;
}
```

### Window Animations
```css
/* Slide up from bottom */
@keyframes slideUp {
  from {
    transform: translateY(100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* Fade in */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
```

### Message Animations
```css
/* Message appear */
@keyframes messageAppear {
  from {
    transform: translateY(10px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* Typing dots */
@keyframes typingDots {
  0%, 20% { opacity: 0.3; }
  50% { opacity: 1; }
  100% { opacity: 0.3; }
}
```

---

## 🔌 API Integration

### Chat Service
**File:** `services/chatService.ts`

```typescript
class ChatService {
  private baseUrl = 'http://localhost:8000/api/v1/chat';
  private sessionId: string | null = null;

  async createSession(userId?: number): Promise<Session>;
  async sendMessage(message: string, positionFen?: string): Promise<ChatResponse>;
  async getHistory(limit?: number): Promise<Message[]>;
  async deleteSession(): Promise<void>;
}

// API Endpoints Used:
POST /api/v1/chat/session
POST /api/v1/chat/message
GET /api/v1/chat/session/{id}/history
DELETE /api/v1/chat/session/{id}
```

### State Management
**File:** `store/chatStore.ts` (Zustand/Redux)

```typescript
interface ChatState {
  isOpen: boolean;
  sessionId: string | null;
  messages: Message[];
  isTyping: boolean;
  unreadCount: number;
  currentPosition: string | null;
  
  // Actions
  openChat: () => void;
  closeChat: () => void;
  sendMessage: (content: string) => Promise<void>;
  setCurrentPosition: (fen: string) => void;
  markAsRead: () => void;
}
```

---

## 📱 Responsive Design

### Desktop (> 768px)
```
- Popup: 380px × 600px
- Position: Fixed bottom-right
- Icon: 60px × 60px
- Offset: 24px from edges
```

### Tablet (768px - 1024px)
```
- Popup: 360px × 550px
- Position: Fixed bottom-right
- Icon: 56px × 56px
- Offset: 20px from edges
```

### Mobile (< 768px)
```
- Popup: Full width - 32px, 80vh height
- Position: Fixed bottom-center
- Icon: 56px × 56px
- Offset: 16px from edges
- Popup slides up from bottom
```

---

## ♿ Accessibility

### ARIA Labels
```html
<button aria-label="Open chess coach chat">
<div role="log" aria-live="polite" aria-label="Chat messages">
<input aria-label="Type your message">
```

### Keyboard Navigation
- **Tab:** Navigate through elements
- **Enter:** Send message / Click button
- **Escape:** Close chat window
- **Arrow keys:** Navigate suggestions

### Screen Reader Support
- Message announcements
- Typing indicator announcements
- Analysis results read aloud

---

## 🎨 Component File Structure

```
frontend/
├── components/
│   ├── chat/
│   │   ├── ChatbotIcon.tsx          # Floating icon
│   │   ├── ChatWindow.tsx           # Main popup container
│   │   ├── ChatHeader.tsx           # Header with title/controls
│   │   ├── MessageList.tsx          # Messages container
│   │   ├── Message.tsx              # Individual message
│   │   ├── ChatInput.tsx            # Input field
│   │   ├── TypingIndicator.tsx      # Typing animation
│   │   ├── SuggestionChips.tsx      # Quick action buttons
│   │   ├── AnalysisCard.tsx         # Position analysis display
│   │   └── WelcomeMessage.tsx       # Initial greeting
│   │
├── services/
│   ├── chatService.ts               # API calls
│   └── positionDetector.ts          # Auto-detect board FEN
│
├── store/
│   └── chatStore.ts                 # State management
│
├── hooks/
│   ├── useChat.ts                   # Chat logic hook
│   ├── useChatSession.ts            # Session management
│   └── useAutoScroll.ts             # Auto-scroll messages
│
├── types/
│   └── chat.types.ts                # TypeScript interfaces
│
└── styles/
    └── chat.css                     # Chat-specific styles
```

---

## 🎯 Key Features Implementation

### 1. Auto-Detect Current Position
```typescript
// When user is viewing a chess board
const currentFEN = useChessBoard().getFEN();

// Auto-include in chat context
chatService.sendMessage(
  "What's the best move?",
  currentFEN  // Automatically attached
);
```

### 2. Suggestion Chips
```typescript
// Backend returns suggestions
{
  "suggestions": [
    "Explain e4 in detail",
    "Compare the top moves",
    "Show me the continuation"
  ]
}

// Frontend renders as clickable chips
<SuggestionChips 
  suggestions={suggestions}
  onSelect={(text) => sendMessage(text)}
/>
```

### 3. Typing Indicator
```typescript
// Show when waiting for response
const [isTyping, setIsTyping] = useState(false);

const sendMessage = async (text) => {
  setIsTyping(true);
  const response = await chatService.sendMessage(text);
  setIsTyping(false);
  addMessage(response);
};
```

### 4. Notification Badge
```typescript
// Track unread messages
const [unreadCount, setUnreadCount] = useState(0);

// Increment when chat is closed and new message arrives
useEffect(() => {
  if (!isOpen && newMessage) {
    setUnreadCount(prev => prev + 1);
  }
}, [newMessage, isOpen]);

// Reset when chat opens
const openChat = () => {
  setIsOpen(true);
  setUnreadCount(0);
};
```

---

## 🚀 Implementation Priority

### Phase 1: Core UI (Day 1)
- ✅ ChatbotIcon component
- ✅ ChatWindow container
- ✅ Basic message display
- ✅ ChatInput component

### Phase 2: Functionality (Day 2)
- ✅ API integration
- ✅ Message sending/receiving
- ✅ Session management
- ✅ State management

### Phase 3: Enhanced Features (Day 3)
- ✅ AnalysisCard component
- ✅ SuggestionChips
- ✅ TypingIndicator
- ✅ Auto-scroll

### Phase 4: Polish (Day 4)
- ✅ Animations
- ✅ Responsive design
- ✅ Accessibility
- ✅ Error handling

---

## 📊 Success Metrics

- **Load Time:** < 1 second
- **Message Send:** < 100ms to show in UI
- **API Response:** 2-5 seconds (Stockfish analysis)
- **Smooth Animations:** 60fps
- **Mobile Performance:** No lag on scroll
- **Accessibility Score:** 100/100

---

## 🎨 Design Mockups

### Closed State
```
┌─────────────────────────────────────┐
│                                     │
│   [Chess Board or Game View]        │
│                                     │
│                              ┌────┐ │
│                              │ 🤖 │ │
│                              │  3 │ │ ← Badge
│                              └────┘ │
└─────────────────────────────────────┘
```

### Open State
```
┌─────────────────────────────────────┐
│                                     │
│   [Chess Board]  ┌────────────────┐ │
│                  │ 🤖 Chess Coach │ │
│                  ├────────────────┤ │
│                  │ Hi! I'm your   │ │
│                  │ chess coach... │ │
│                  │                │ │
│                  │ What's best?   │ │
│                  │                │ │
│                  │ I've analyzed  │ │
│                  │ 📊 Eval: +0.4  │ │
│                  │ 🎯 Move: e4    │ │
│                  ├────────────────┤ │
│                  │ Type here... → │ │
│                  └────────────────┘ │
└─────────────────────────────────────┘
```

---

**Ready to implement!** This design provides a clean, minimalist chatbot experience that integrates seamlessly with the chess coaching backend.
