
import requests
import os
from openai import OpenAI

SECURE_PROMPT = os.getenv("SECURE_PROMPT", "")

def generate_post(context, history):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

    response = client.chat.completions.create(
        model="openrouter/free",
        messages=[
            {"role": "user", "content":f"{SECURE_PROMPT} context-{context}, history-{history}"}
        ],
        # Optional metadata headers for OpenRouter app attribution
        extra_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", ""),
            "X-Title": "Elucid"
        }
    )

    # Print the response content
    post = response.choices[0].message.content
    print(post)

    # Print which underlying model processed your request
    print(f"\n[Served by: {response.model}]")
    return post
