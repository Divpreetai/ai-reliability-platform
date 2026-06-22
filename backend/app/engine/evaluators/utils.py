import json
import logging
from openai import AsyncOpenAI
from backend.app.config import settings

logger = logging.getLogger(__name__)

async def call_llm_judge(prompt: str, system_prompt: str = "You are an expert AI evaluator.") -> dict:
    """
    Helper to invoke OpenAI gpt-4o-mini as a judge.
    Enforces a JSON return format with 'score' (float) and 'explanation' (string).
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-openai-api-key-here":
        logger.warning("OPENAI_API_KEY is not set or using default placeholder. Mocking judge evaluation.")
        return {
            "score": 0.8,
            "explanation": "Mocked evaluation result: OpenAI API key is not configured in .env."
        }

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        f"{system_prompt}\n"
                        "CRITICAL: You must return a valid JSON object. Do not wrap in markdown code blocks. "
                        "The JSON object must have exactly these keys:\n"
                        "- 'score': a float value (e.g. between 0.0 and 1.0 or 1.0 and 5.0, depending on instructions)\n"
                        "- 'explanation': a brief, concise string explanation detailing the justification for the score."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return {
            "score": float(data.get("score", 0.0)),
            "explanation": str(data.get("explanation", ""))
        }
    except Exception as e:
        logger.error(f"Error calling LLM judge: {str(e)}")
        return {
            "score": 0.0,
            "explanation": f"Evaluator Error: Failed to invoke or parse LLM judge response. {str(e)}"
        }
