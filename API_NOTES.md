# API Notes

## OpenAI Integration

### Current State
`OPENAI_API_KEY` is set to a placeholder string in `kuccpss/settings.py`. The career guidance engine in `career/engine.py` is a stub that returns hardcoded placeholder matches and a dummy AI message.

### Before Integrating

1. Move the key to an environment variable:
   ```python
   # settings.py
   import os
   OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
   ```
2. Add `python-dotenv` or use a `.env` file (never commit the real key)
3. Install the SDK: `pip install openai`

### Recommended Model
Use `claude-haiku-4-5-20251001` (via Anthropic, cheapest) or `gpt-4o-mini` (via OpenAI) for short recommendation text. Use `claude-sonnet-4-6` if richer reasoning is needed. See full model IDs in CLAUDE.md.

### Planned AI Features

#### 1. Career Recommendation Text (`career/engine.py`)
Replace `generate_ai_recommendation()` stub with a real call:
```python
# Pseudocode
prompt = f"""
A Kenyan student has the following KCSE results: {kcse_grades}
Their calculated cluster points are: {cluster_points}
Their chosen pathway is: {pathway}
Top matched courses: {top_course_names}

Write a short, encouraging career guidance message (3–5 sentences) 
summarising their options and recommending next steps.
"""
```
- Model: `gpt-4o-mini` or `claude-haiku-4-5-20251001`
- Max tokens: 300
- Store result in `AIRecommendation.advice_text`

#### 2. Course Description Generation (Future)
Auto-generate friendly descriptions for courses that have empty description fields.

#### 3. Subject Gap Analysis (Future)
Tell a student which subjects they'd need to improve to qualify for a specific course.

### Cost Considerations
- Recommendations are short (300 tokens max) — very cheap per call
- Cache recommendations: if a student re-submits the same grades + pathway, reuse the stored `AIRecommendation` instead of calling the API again
- Do not call the API on every filter/search interaction — only on the main KCSE submission

### Rate Limiting
Add per-user rate limiting before enabling the live API:
- Max 3 AI recommendation calls per user per day
- Store call count in session or a simple DB counter
