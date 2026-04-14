# Coaching Services

Advanced pattern-based recommendation system for chess improvement.

## Overview

The coaching services module provides intelligent, data-driven recommendations to help chess players improve their game. It analyzes performance metrics across multiple dimensions and generates prioritized, actionable coaching advice.

## Components

### RecommendationEngine

The core recommendation engine that analyzes user performance and generates coaching recommendations.

**Location:** `app/services/coaching/recommendation_engine.py`

### Usage

```python
from app.services.coaching.recommendation_engine import RecommendationEngine

engine = RecommendationEngine()
recommendations = engine.generate_recommendations(
    user_data={
        "user_id": 1,
        "rating_change": -20,
        "performance_trend": "declining"
    },
    analysis_data={
        "average_acpl": 85.0,
        "opening_performance": {"acpl": 35.0, "games_count": 10},
        "middlegame_performance": {"acpl": 40.0, "games_count": 10},
        "endgame_performance": {"acpl": 45.0, "games_count": 10},
        "move_quality_stats": {...},
        "total_games": 10
    },
    max_recommendations=5
)

for rec in recommendations:
    print(f"{rec.title} (Priority: {rec.priority}, Score: {rec.priority_score})")
    print(f"  {rec.description}")
    print(f"  Steps: {rec.actionable_steps}")
```

## Pattern Rules

The recommendation engine implements 10+ pattern-based rules:

### 1. Endgame Weakness
- **Trigger:** Endgame ACPL > 40
- **Category:** Endgame
- **Recommendation:** Study fundamental endgames (King & Pawn, Rook endgames, etc.)

### 2. Opening Weakness
- **Trigger:** Opening ACPL > 30
- **Category:** Opening
- **Recommendation:** Review opening repertoire and learn key principles

### 3. Low Overall Accuracy
- **Trigger:** Accuracy < 70%
- **Category:** Tactics
- **Recommendation:** Focus on tactical training and puzzle solving

### 4. Middlegame Blunders
- **Trigger:** Middlegame ACPL > 35 AND mistake rate > 15%
- **Category:** Calculation
- **Recommendation:** Improve calculation and candidate move selection

### 5. Time Pressure
- **Trigger:** Blunders per game > 1.5
- **Category:** Time Management
- **Recommendation:** Better time allocation and avoiding panic moves

### 6. Opening-Specific Issues
- **Trigger:** Specific opening with ACPL > 50
- **Category:** Opening
- **Recommendation:** Study or switch the problematic opening

### 7. Poor Conversion Rate
- **Trigger:** High endgame ACPL + declining rating
- **Category:** Technique
- **Recommendation:** Learn how to convert winning positions

### 8. Hanging Pieces
- **Trigger:** Estimated hanging pieces > 0.5 per game
- **Category:** Visualization
- **Recommendation:** Board awareness and visualization training

### 9. Tactical Blindness
- **Trigger:** Best move rate < 30%
- **Category:** Pattern Recognition
- **Recommendation:** Study tactical motifs and patterns

### 10. Endgame Knowledge Gaps
- **Trigger:** Endgame ACPL > 60
- **Category:** Endgame
- **Recommendation:** Master fundamental endgame positions

## Priority Scoring

Recommendations are prioritized using a weighted scoring algorithm:

```
priority_score = (
    severity_weight * 0.4 +      # How bad is the issue? (0-1)
    frequency_weight * 0.3 +      # How often does it occur? (0-1)
    impact_weight * 0.2 +         # Rating impact potential (0-1)
    recency_weight * 0.1          # Recent games weighted higher (0-1)
) * 100
```

### Priority Levels

- **Critical:** Score >= 80 (Urgent attention needed)
- **High:** Score >= 60 (Important to address soon)
- **Medium:** Score >= 40 (Should work on this)
- **Low:** Score < 40 (Minor improvement area)

## Data Structures

### Recommendation

```python
@dataclass
class Recommendation:
    category: str                    # "tactics", "endgame", "opening", etc.
    priority: str                    # "critical", "high", "medium", "low"
    priority_score: float            # 0-100
    title: str                       # Short title
    description: str                 # Detailed explanation
    actionable_steps: List[str]      # Concrete steps to improve
    related_games: Optional[List[int]]  # Game IDs showing the pattern
    resources: Optional[List[str]]   # Learning resources
    pattern_match: Optional[PatternMatch]  # Evidence for the pattern
```

### PatternMatch

```python
@dataclass
class PatternMatch:
    pattern_name: str    # Identifier for the pattern
    severity: float      # 0-1 scale
    frequency: int       # Number of occurrences
    evidence: Dict       # Supporting data
```

## Integration

The recommendation engine is integrated with the insights generation system:

1. User analyzes games → Performance metrics calculated
2. Insights background task runs → Calls recommendation engine
3. Engine analyzes patterns → Generates prioritized recommendations
4. Recommendations stored in `user_insights` table
5. API endpoints expose recommendations to frontend

### Database Schema

Enhanced fields in `user_insights` table:

```sql
-- Priority scores for each recommendation (array of floats)
recommendation_scores JSONB

-- Granular weakness breakdown
focus_areas_detailed JSONB

-- Detected patterns with evidence
pattern_matches JSONB
```

## API Endpoints

### Get Coaching Plan

```http
GET /api/insights/{user_id}/coaching-plan
```

Returns detailed coaching plan with:
- Prioritized recommendations
- Priority scores
- Pattern matches
- Performance summary
- Analysis period

**Response:**
```json
{
  "recommendations": [...],
  "priority_scores": [85.5, 72.3, 68.1],
  "pattern_matches": [...],
  "focus_areas": {...},
  "performance_summary": {
    "average_acpl": 75.0,
    "performance_trend": "declining",
    "rating_change": -25,
    "games_analyzed": 10
  },
  "period": {
    "start": "2026-03-14T00:00:00Z",
    "end": "2026-03-21T00:00:00Z",
    "type": "weekly"
  }
}
```

## Testing

Comprehensive test suite in `tests/test_recommendation_engine.py`:

- Pattern detection tests (all 10+ rules)
- Priority scoring validation
- Edge cases (insufficient data, excellent performance)
- Data structure serialization
- Integration with insights system

Run tests:
```bash
pytest tests/test_recommendation_engine.py -v
```

## Future Enhancements

- Machine learning-based pattern detection
- Personalized learning paths
- Integration with practice drills
- Historical progress tracking
- Comparative analysis (vs. similar-rated players)

## Notes

- Minimum 3 games required for most pattern detection
- Graceful fallback to basic recommendations if engine fails
- All recommendations include actionable steps
- Resources provided when available
- Pattern evidence stored for transparency
