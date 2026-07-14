import os

import pytest


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") == "test-key", reason="Gemini API key not configured")
def test_gemini_smoke_test() -> None:
    from google import genai

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(model="gemini-3.5-flash", contents="Say Hello")
    assert response.text