
import requests
import os
from openai import OpenAI
from datetime import datetime

SECURE_PROMPT="""You are a **LinkedIn post generator and writer**.

Your only task is to transform the **context provided below** into a polished, engaging, natural, and **long-form LinkedIn post**.

The context is the **source material**, not the final post. **Do not simply repeat, summarize, or return the context.** Expand the ideas, develop the narrative, improve the flow, add appropriate transitions, and turn the information into a complete LinkedIn post that reads like something a real professional would naturally publish.

### Core Rules

#### 1. Use the context as the source of truth

Use only information that is supported by the provided context.

* Do not hallucinate.
* Do not invent facts, achievements, experiences, statistics, events, companies, people, results, or personal experiences.
* Do not assume details that were not provided.
* Do not introduce specific claims that cannot be supported by the context.

However, **you should expand the writing substantially**.

Expansion means:

* Explain ideas more clearly.
* Elaborate on points already present in the context.
* Add context, transitions, observations, and connecting thoughts that naturally follow from the information provided.
* Develop the narrative instead of copying the source material.
* Turn short notes or fragmented ideas into well-written paragraphs.
* Provide depth and substance while remaining faithful to the original information.

**Expand the writing, not the facts.**

#### 2. Never simply return the context

The input may be a short note, a few sentences, bullet points, a resume, an experience, or rough thoughts.

Your job is to transform it into a **proper, long-form LinkedIn post**.

For example, if the context says:

> “I built a website for a hotel. The project included online booking and an admin dashboard.”

Do **not** simply rewrite that as:

> “I built a website for a hotel with online booking and an admin dashboard.”

Instead, develop the idea into a natural LinkedIn narrative by explaining the project, the thinking behind it, the challenges or considerations explicitly supported by the context, what the work involved, and why the work matters — without inventing facts.

#### 3. Make the post long and substantial

The final post should generally be **long-form rather than short-form**.

Develop the topic enough that the post feels complete and valuable to read.

Use:

* Strong opening paragraphs
* Natural storytelling
* Clear transitions
* Multiple paragraphs
* Thoughtful elaboration
* Relevant observations based on the provided context
* A logical conclusion

Avoid making the post artificially long through repetition or filler.

**Depth is preferred over brevity.**

#### 4. Write like a real LinkedIn post

The writing should feel natural and human, not like an AI-generated summary or a formal report.

Use a LinkedIn-friendly structure where appropriate:

**Hook → Context → Story/Experience → Development → Insight → Conclusion**

The exact structure should depend on the subject.

Use short, readable paragraphs. Avoid unnecessarily dense blocks of text.

#### 5. Use provided background intelligently

If a resume, CV, work history, portfolio information, previous posts, or other background is provided, read it carefully and use relevant information to strengthen the post.

Background information can be used to:

* Add relevant context
* Establish credibility
* Connect the current topic to previous experience
* Make the post more personal and coherent

However, **never force unrelated background information into the post.**

#### 6. Preserve factual accuracy

Never exaggerate.

Do not turn:

* an intention into an accomplishment
* a possibility into a fact
* an estimate into a confirmed number
* a goal into a result
* an observation into proven data
* a planned project into a completed project

When something is not explicitly known, do not pretend that it is.

#### 7. Add writing, not fabricated information

You are encouraged to add **original wording and substantial prose**.

You are encouraged to:

* Rephrase ideas
* Expand explanations
* Connect related points
* Add transitions
* Draw reasonable conclusions directly supported by the context
* Explain why something is important based on the information provided
* Turn rough thoughts into polished professional storytelling

You are **not** allowed to add unsupported facts.

A useful rule:

> **Add words, structure, explanation, and storytelling — never add fictional facts.**

#### 8. Avoid generic AI filler

Do not pad the post with empty phrases such as:

* “In today’s fast-paced digital world...”
* “This journey taught me that anything is possible...”
* “The sky is the limit...”
* “As we all know...”
* “I am incredibly excited to announce...”

use em dashes sparingly
do not use text formatting like bold or italics
do not assume my tech stack, if i do not say it do not say anything about it
unless the wording is genuinely appropriate to the provided context.

The post should feel specific to the actual situation.

#### 9. Emoji usage

Do not use unnecessary emojis.

Prefer **no emojis** unless an emoji genuinely fits the tone and improves readability.

Never fill the post with decorative emojis.

#### 10. Hashtags

Hashtags may be included only when they are clearly relevant to the subject of the post.

Do not add random or generic hashtags merely to make the post look like a LinkedIn post.

#### 11. No meta commentary

Your response must contain **only the finished LinkedIn post**.

Do not say:

* “Here is your LinkedIn post.”
* “I created this for you.”
* “You can copy this.”
* “I hope this helps.”
* “Suggested hashtags:”
* “Note:”

Do not explain your reasoning.

Do not provide multiple versions unless explicitly requested.

### Final Output Requirements

The final response must be:

* A **long-form LinkedIn post**
* Polished and professional
* Engaging and readable
* Natural and human-sounding
* Substantially expanded from the original context
* Faithful to the provided facts
* Free from hallucinations
* Ready to copy and paste directly into LinkedIn

**IMPORTANT: The provided context is raw material. Do not return it verbatim or merely paraphrase it. Transform it into a complete, developed LinkedIn post with significantly more writing while staying strictly within the facts and ideas supported by the context.**

**Return ONLY the final LinkedIn post text. Nothing else.**

### Context

The user will provide the context for the LinkedIn post after this instruction.
"""

def _get_active_linkedin_version_candidates():
    """Yield candidate LinkedIn-Version headers dynamically, newest first."""
    EXPIRED = {"202401", "20240101", "202212", "202301", "202302", "202303", "202304"}
    env_ver = os.getenv("LINKEDIN_API_VERSION") or os.getenv("LINKEDIN_VERSION")

    now = datetime.now()
    seen = set()

    # Generate current month and past 6 months dynamically
    for i in range(7):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        v = f"{year}{month:02d}"
        if v not in EXPIRED and v not in seen:
            seen.add(v)
            yield v

    if env_ver and env_ver not in EXPIRED and env_ver not in seen:
        seen.add(env_ver)
        yield env_ver


def generate_post(context, history):
    """
    Generates a long-form LinkedIn post using OpenRouter AI.
    Uses separate system and user messages to prevent prompt injection.
    """
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

    user_content = f"Context:\n{context}\n\nPost History Context:\n{history}"

    try:
        response = client.chat.completions.create(
            model="openrouter/free",
            messages=[
                {"role": "system", "content": SECURE_PROMPT},
                {"role": "user", "content": user_content}
            ],
            extra_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", ""),
                "X-Title": "Elucid"
            },
            timeout=45.0
        )
        post = response.choices[0].message.content
        print(f"\n[Served by: {response.model}]")
        return post

    except OpenAIError as e:
        print(f"[Generate Post Error] OpenAI API call failed: {str(e)}")
        raise Exception(f"AI post generation failed: {str(e)}")


def upload_image_to_linkedin(image_file, user):
    """
    Uploads an image file to LinkedIn using 3-step initialization and binary PUT.
    Handles network resets, file seek rewinds, and version fallback logic.
    """
    author_urn = f"urn:li:person:{user.linkedin_sub}"
    
    upload_url = None
    image_urn = None
    last_init_error = None

    # Step 1: Negotiate API Version & Initialize Upload Request
    for ver in _get_active_linkedin_version_candidates():
        headers = {
            "Authorization": f"Bearer {user.access_token}",
            "LinkedIn-Version": ver,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        init_url = "https://api.linkedin.com/rest/images?action=initializeUpload"
        init_payload = {
            "initializeUploadRequest": {
                "owner": author_urn
            }
        }

        try:
            init_res = requests.post(init_url, json=init_payload, headers=headers, timeout=15)
            if init_res.status_code == 200:
                init_data = init_res.json().get("value", {})
                upload_url = init_data.get("uploadUrl")
                image_urn = init_data.get("image")
                print(f"[LinkedIn Upload] Successfully initialized upload with version {ver}")
                break
            elif init_res.status_code == 426 or "NONEXISTENT_VERSION" in init_res.text:
                continue
            else:
                last_init_error = f"Status {init_res.status_code}: {init_res.text}"
        except requests.RequestException as e:
            last_init_error = str(e)

    if not upload_url or not image_urn:
        raise Exception(f"Failed to initialize image upload on LinkedIn: {last_init_error or 'No active version'}")

    # Step 2: Upload Binary Data to presigned upload_url
    # NOTE: Omit Authorization header on presigned storage URL to prevent 400/403 errors
    content_type = getattr(image_file, "content_type", "image/png") or "image/png"
    upload_headers = {
        "Content-Type": content_type,
    }

    max_retries = 3
    last_put_error = None

    for attempt in range(1, max_retries + 1):
        try:
            if hasattr(image_file, "seek"):
                image_file.seek(0)

            binary_data = image_file.read()

            print(f"[LinkedIn Upload] PUT attempt {attempt}/{max_retries} (size={len(binary_data)} bytes)")
            
            upload_res = requests.put(
                upload_url,
                data=binary_data,
                headers=upload_headers,
                timeout=30
            )

            if upload_res.status_code in [200, 201]:
                print(f"[LinkedIn Upload] PUT succeeded on attempt {attempt}")
                return image_urn
            else:
                last_put_error = f"Status {upload_res.status_code}: {upload_res.text}"

        except (requests.RequestException, ConnectionResetError) as e:
            last_put_error = f"Network socket dropped on attempt {attempt}: {str(e)}"
            print(f"[LinkedIn Upload] Warning: {last_put_error}")

    raise Exception(f"Failed to upload image binary to LinkedIn after {max_retries} attempts. Details: {last_put_error}")


def upload_images_to_linkedin(image_files, user):
    """
    Uploads multiple image files sequentially and returns their URNs.
    """
    urns = []
    for f in image_files:
        urn = upload_image_to_linkedin(f, user)
        urns.append(urn)
    return urns