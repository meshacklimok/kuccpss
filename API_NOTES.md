# API Notes

## OpenAI Integration

### Current State
`OPENAI_API_KEY` is read from the `OPENAI_API_KEY` environment variable (empty string default — no placeholder in code). The career guidance engine in `career/engine.py` is a stub that returns hardcoded placeholder matches and a dummy AI message.

**What IS already live:** The document scanner (`degree_upload` view in `career/views.py`) uses GPT-4o vision. When `OPENAI_API_KEY` is set it accepts JPG/PNG/PDF uploads, detects whether it's a KCSE grade slip or a cluster points document, extracts grades with subject alias resolution, and returns structured JSON. Falls back to manual entry if key is absent.

### Setup (already done)
- Key reads from `OPENAI_API_KEY` env var — set this on Render to enable OCR and AI features
- `python-dotenv` installed; `.env` for local dev
- `openai` SDK installed

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
