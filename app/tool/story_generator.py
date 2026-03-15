import re
from html import unescape

from openai import OpenAI


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def sanitize_provider_error(raw_error: Exception) -> str:
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


def render_story_prompt(story_template: str, edu_content: str) -> str:
    normalized_template = (
        story_template
        .replace("{{EducationMaterial}}", "{EducationMaterial}")
        .replace("{{eduContent}}", "{eduContent}")
    )

    return normalized_template.format(
        eduContent=edu_content,
        EducationMaterial=edu_content,
    )


def generate_story_content(
    *,
    token: str,
    model: str,
    story_template: str,
    edu_content: str,
    temperature: float = 0.7,
    request_timeout: int = 180,
) -> str:
    prompt = render_story_prompt(story_template=story_template, edu_content=edu_content)

    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=token,
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        timeout=request_timeout,
    )

    if not completion.choices:
        raise RuntimeError("LLM provider returned no choices")

    message = completion.choices[0].message
    return message.content or ""
