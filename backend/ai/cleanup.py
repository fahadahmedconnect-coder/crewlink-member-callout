import os
import json
from openai import OpenAI

# 8 second timeout as per design
TIMEOUT_SECONDS = 8


def cleanup_announcement_text(messy_text: str) -> dict | None:
    """
    Use AI to clean up messy announcement text into structured format.

    Returns:
        {
            'title': 'Clean title',
            'body': 'Clean body text',
            'push_preview': 'Max 120 char preview'
        }
        or None if AI service is unavailable/timeout
    """
    api_key = os.getenv('OPENAI_API_KEY')

    if not api_key:
        # Fallback: simple cleanup without AI
        return _fallback_cleanup(messy_text)

    try:
        client = OpenAI(api_key=api_key, timeout=TIMEOUT_SECONDS)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are helping union leadership write clear announcements.
Convert the messy input into a structured announcement with:
1. title: Clear, professional title (max 100 chars)
2. body: Well-formatted body text with all relevant details
3. push_preview: A concise preview for push notification (max 120 chars)

Respond ONLY with valid JSON in this format:
{"title": "...", "body": "...", "push_preview": "..."}"""
                },
                {
                    "role": "user",
                    "content": f"Clean up this announcement:\n\n{messy_text}"
                }
            ],
            temperature=0.3,
            max_tokens=500
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON response
        result = json.loads(content)

        # Ensure push_preview is max 120 chars
        if len(result.get('push_preview', '')) > 120:
            result['push_preview'] = result['push_preview'][:117] + '...'

        return result

    except Exception as e:
        print(f"AI cleanup error: {e}")
        return _fallback_cleanup(messy_text)


def _fallback_cleanup(messy_text: str) -> dict:
    """
    Simple fallback when AI is unavailable.
    Just does basic formatting.
    """
    # Take first line as title, rest as body
    lines = messy_text.strip().split('\n')
    title = lines[0][:100] if lines else "Announcement"
    body = messy_text.strip()

    # Create simple preview
    preview = body[:117] + '...' if len(body) > 120 else body

    return {
        'title': title,
        'body': body,
        'push_preview': preview
    }
