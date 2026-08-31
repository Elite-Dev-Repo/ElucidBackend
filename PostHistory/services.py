
import requests
import os
from openai import OpenAI

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

def generate_post(context, history):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

    response = client.chat.completions.create(
        model="openrouter/free",
        messages=[
            {"role": "user", "content":f"{SECURE_PROMPT} context-{context}, posts_history-{history}"}
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


def upload_image_to_linkedin(image_file, user):
    """
    Uploads an in-memory image to LinkedIn and returns the image URN.

    3-step LinkedIn flow:
      1. POST /rest/images?action=initializeUpload -> { value: { uploadUrl, image } }
      2. PUT uploadUrl with binary
      3. Caller attaches URN to /rest/posts payload

    Args:
        image_file: Django UploadedFile (InMemoryUploadedFile / TemporaryUploadedFile)
        user: Auth user with access_token and linkedin_sub
    Returns:
        str: image URN e.g. urn:li:image:C4E10AQ...
    Raises:
        Exception with descriptive message on failure
    """
    from django.utils import timezone
    version = os.getenv("LINKEDIN_API_VERSION", timezone.now().strftime("%Y%m"))
    if not version:
        version = "202401"
    author_urn = f"urn:li:person:{user.linkedin_sub}"
    headers = {
        "Authorization": f"Bearer {user.access_token}",
        "LinkedIn-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }

    # Step 1: Initialize the upload request
    init_url = "https://api.linkedin.com/rest/images?action=initializeUpload"
    init_payload = {
        "initializeUploadRequest": {
            "owner": author_urn
        }
    }

    try:
        init_res = requests.post(init_url, json=init_payload, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise Exception(f"Failed to reach LinkedIn initializeUpload: {str(e)}")

    if init_res.status_code != 200:
        # try to surface JSON error if available
        try:
            detail = init_res.json()
        except Exception:
            detail = init_res.text
        raise Exception(f"Failed to initialize image upload ({init_res.status_code}): {detail}")

    init_data = init_res.json().get("value", {})
    upload_url = init_data.get("uploadUrl")
    image_urn = init_data.get("image")  # e.g. urn:li:image:C4E10AQ...

    if not upload_url or not image_urn:
        raise Exception(f"LinkedIn init response missing uploadUrl/image: {init_data}")

    # Step 2: Upload image binary to the designated uploadUrl
    # Validate file
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp", "image/gif"}
    content_type = getattr(image_file, "content_type", "image/jpeg") or "image/jpeg"
    if content_type not in ALLOWED_TYPES:
        # fallback: let LinkedIn reject if unsupported, but warn
        pass

    # File size guard: LinkedIn allows up to ~ 5MB per image for posts; enforce 10MB max
    if hasattr(image_file, "size") and image_file.size > 10 * 1024 * 1024:
        raise Exception(f"Image too large ({image_file.size} bytes). Max 10MB.")

    # Ensure file pointer at start
    try:
        image_file.seek(0)
    except Exception:
        pass

    binary = image_file.read()

    upload_headers = {
        "Authorization": f"Bearer {user.access_token}",
        "Content-Type": content_type,
    }

    try:
        upload_res = requests.put(upload_url, data=binary, headers=upload_headers, timeout=30)
    except requests.RequestException as e:
        raise Exception(f"Failed to upload binary to LinkedIn: {str(e)}")

    if upload_res.status_code not in [200, 201]:
        raise Exception(f"Failed to upload image binary ({upload_res.status_code}): {upload_res.text}")

    return image_urn


def upload_images_to_linkedin(image_files, user):
    """
    Upload multiple images sequentially. Returns list of image URNs.
    Stops on first failure and raises.
    """
    urns = []
    for f in image_files:
        urn = upload_image_to_linkedin(f, user)
        urns.append(urn)
    return urns