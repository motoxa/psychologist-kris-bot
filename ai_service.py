import os
import json
import anthropic
import google.generativeai as genai
from dotenv import load_dotenv
from ai_prompts import questions, system_prompt

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER")

if not AI_PROVIDER:
    raise ValueError("AI_PROVIDER environment variable is not set")

AI_PROVIDER = AI_PROVIDER.lower()

if AI_PROVIDER == "gemini":
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
    MODEL_NAME = os.getenv("GEMINI_MODEL")
    if not MODEL_NAME:
        raise ValueError("GEMINI_MODEL environment variable is not set")
elif AI_PROVIDER == "claude":
    claude_api_key = os.getenv("CLAUDE_API_KEY")
    if claude_api_key:
        claude_client = anthropic.Anthropic(api_key=claude_api_key)
    MODEL_NAME = os.getenv("CLAUDE_MODEL")
    if not MODEL_NAME:
        raise ValueError("CLAUDE_MODEL environment variable is not set")
else:
    raise ValueError(f"Unsupported AI_PROVIDER: {AI_PROVIDER}")


def get_ai_analysis(request_type, answers):
    prompt_content = f"""
Вот анкета с вопросами:
{json.dumps(questions, ensure_ascii=False, indent=2)}

Вот ответы пользователя:
{json.dumps(answers, ensure_ascii=False, indent=2)}

вопросы и ответы брать если что из базовых и из {request_type}

Сгенерируй персонализированную рекомендацию и призыв к действию на основе этих данных.
"""

    if AI_PROVIDER == "gemini":
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=4096,
            temperature=0.2,
        )
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=system_prompt,
            generation_config=generation_config
        )
        response = model.generate_content(prompt_content)
        return response.text
    elif AI_PROVIDER == "claude":
        response = claude_client.messages.create(
            model=MODEL_NAME,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": prompt_content}
            ]
        )
        return response.content[0].text
