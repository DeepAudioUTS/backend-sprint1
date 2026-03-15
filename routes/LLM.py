
import re
from html import unescape

from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

router = APIRouter()


class GenerateStoryRequest(BaseModel):
    storyTemplate: str
    eduContent: str
    model: str
    token: str
    request_timeout: int = 180
    temperature: float = 0.7


def _compact_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _sanitize_provider_error(raw_error: Exception) -> str:
    text = str(raw_error)
    lower_text = text.lower()

    if "<html" in lower_text or "<!doctype html" in lower_text:
        title_match = re.search(r"<title>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
        h1_match = re.search(r"<h1>(.*?)</h1>", text, flags=re.IGNORECASE | re.DOTALL)
        p_match = re.search(r"<p>(.*?)</p>", text, flags=re.IGNORECASE | re.DOTALL)

        parts = []
        for match in (title_match, h1_match, p_match):
            if match:
                parts.append(_compact_text(unescape(match.group(1))))

        if parts:
            return f"Provider returned HTML error page: {' | '.join(parts)}"
        return "Provider returned an HTML error page (likely gateway/proxy error)."

    cleaned = _compact_text(text)
    return cleaned if len(cleaned) <= 300 else cleaned[:297] + "..."


def _render_story_prompt(story_template: str, edu_content: str) -> str:
    normalized_template = (
        story_template
        .replace("{{EducationMaterial}}", "{EducationMaterial}")
        .replace("{{eduContent}}", "{eduContent}")
    )

    return normalized_template.format(
        eduContent=edu_content,
        EducationMaterial=edu_content,
    )


@router.post('/GenerateStory')
def GenerateStory(payload: GenerateStoryRequest):
    if not payload.token:
        raise HTTPException(status_code=400, detail="token is required")

    if not payload.model:
        raise HTTPException(status_code=400, detail="model is required")

    try:
        story_prompt = _render_story_prompt(
            story_template=payload.storyTemplate,
            edu_content=payload.eduContent,
        )
    except KeyError as exc:
        missing_key = str(exc).strip("'")
        raise HTTPException(
            status_code=400,
            detail=(
                f"storyTemplate contains unknown placeholder '{missing_key}'. "
                "Use '{eduContent}' or '{EducationMaterial}', or escape braces as '{{' and '}}'."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="storyTemplate has invalid format braces. Escape literal braces as '{{' and '}}'.",
        ) from exc

    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=payload.token,
    )

    try:
        completion = client.chat.completions.create(
            model=payload.model,
            messages=[
                {
                    "role": "user",
                    "content": story_prompt,
                }
            ],
            temperature=payload.temperature,
            timeout=payload.request_timeout,
        )
    except Exception as exc:
        safe_message = _sanitize_provider_error(exc)
        raise HTTPException(
            status_code=502,
            detail=f"LLM provider request failed: {safe_message}",
        ) from exc

    if not completion.choices:
        raise HTTPException(status_code=502, detail="LLM provider returned no choices")

    message = completion.choices[0].message
    return {
        "role": message.role,
        "content": message.content,
    }

    

