# API Notes

## OpenAI Integration

### Current State
`OPENAI_API_KEY` is read from the `OPENAI_API_KEY` environment variable (empty string default — no placeholder in code).

**What IS already live:**
- `career/engine.py` — dispatches to real pathway functions (`match_degree_courses`, `match_diploma_courses`, etc.); no longer returns hardcoded stubs
- Document scanner (`degree_upload` view in `career/views.py`) — GPT-4o vision; accepts JPG/PNG/PDF; detects KCSE slips vs cluster point docs; extracts grades with subject alias resolution; returns structured JSON. Falls back to manual entry if key is absent.
- CareerNext AI chat — in-career-engine AI chat with full KUCCPS system prompt, `AIChatCredit` paywall, `AIKnowledgeEntry` knowledge base, per-user rate limiting
- **Model/temperature are now admin-configurable, not hardcoded.** `CareerConfig.ai_model_name` (default `gpt-4o-mini`) and `CareerConfig.ai_temperature` (default `0.6`) drive every CareerNext AI call — `_generate_quiz_ai_summary`, `ajax_ai_insight`, `ajax_ai_chat` in `career/views.py`, and `generate_ai_recommendation()` in `career/models.py` all call `CareerConfig.get()` rather than hardcoding the model string. Change the model or temperature from `/cn-staff/` with no deploy needed.

**What is still stubbed:**
- `generate_ai_recommendation()` in `career/engine.py` — returns placeholder text; the full results AI recommendation (not the chat) is not yet live

### Setup (already done)
- Key reads from `OPENAI_API_KEY` env var — set this on Render to enable OCR and AI features
- `python-dotenv` installed; `.env` for local dev
- `openai` SDK installed

### Recommended Model
- Short recommendation text: `claude-haiku-4-5-20251001` (Anthropic, cheapest) or `gpt-4o-mini` (OpenAI)
- Richer reasoning / AI chat: `claude-sonnet-4-6`
- OCR / vision: `gpt-4o` (OpenAI vision; Anthropic models also support vision via `claude-sonnet-4-6`)
See CLAUDE.md for full model ID list.

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
