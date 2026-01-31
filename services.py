import os
import time
import random
import requests
import json
from dotenv import load_dotenv
from openai import OpenAI
from notion_client import Client
from mastodon import Mastodon
from models import BusinessKeywords, SocialMediaPost, ReplyBatch
from database import SessionLocal, FeedbackMemory


load_dotenv()

# --- 1. DEBUG CHECK (Your Original Code) ---
key = os.getenv("OPENROUTER_API_KEY")
if not key:
    print("❌ ERROR: OPENROUTER_API_KEY not found in .env file!")
    print(f"Current Working Directory: {os.getcwd()}")
else:
    print("✅ API Key loaded successfully.")

# --- 2. Client Initializations ---
openai_client = OpenAI(
    api_key=key, 
    base_url="https://openrouter.ai/api/v1"
)
notion = Client(auth=os.getenv("NOTION_TOKEN"))
mastodon = Mastodon(
    access_token=os.getenv("MASTODON_ACCESS_TOKEN"),
    api_base_url=os.getenv("MASTODON_INSTANCE_URL")
)

# --- 3. Goal-Specific Functions ---

def get_notion_content(page_id):
    """Goal 1: Pulls text from Notion."""
    response = notion.blocks.children.list(block_id=page_id)
    text = ""
    for block in response.get("results", []):
        if block["type"] == "paragraph":
            rich_text = block["paragraph"].get("rich_text", [])
            if rich_text:
                text += rich_text[0]["plain_text"] + "\n"
    return text

def retrieve_relevant_feedback(current_context, limit=3, threshold=0.15):
    """Searches for past feedback relevant to the current task."""
    db = SessionLocal()
    try:
        # 1. Embed a STATIC query for feedback (solves asymmetry)
        # Instead of embedding the random doc content, we ask for "rules"
        query_embedding = generate_embedding("social media style guide rules, user preferences, and critical feedback to follow")
        
        if not query_embedding:
            return []
        
        # 2. Fetch all memories (In production, use a Vector DB like Pinecone/pgvector for speed)
        memories = db.query(FeedbackMemory).all()
        
        # 3. Calculate Cosine Similarity manually (since SQLite doesn't support vector math)
        import numpy as np
        
        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        
        scored_memories = []
        print("\n🔍 DEBUG: Memory Scores:")
        for m in memories:
            if m.embedding:
                score = cosine_similarity(query_embedding, m.embedding)
                print(f"   - Score: {score:.4f} | Content: {m.feedback_text[:50]}...")
                if score >= threshold:  # Only keep relevant matches
                    scored_memories.append((score, m.feedback_text))
        
        # 4. Sort and return top matches
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [f"- {feedback} (Score: {score:.2f})" for score, feedback in scored_memories[:limit]]
        
    except Exception as e:
        print(f"⚠️ Retrieval failed: {e}")
        return []
    finally:
        db.close()

def generate_social_post(docs):
    """Goal 2: Generates the content using LLM with RAG Memory."""
    
    # 1. Retrieve past feedback
    past_feedback = retrieve_relevant_feedback(docs)
    feedback_context = ""
    if past_feedback:
        feedback_context = "\n\n🧠 CRITICAL USER FEEDBACK (YOU MUST OBEY THIS): \n" + "\n".join(past_feedback)
    
    # 2. Generate Prompt
    prompt = (
        f"CONTEXT: You are a social media manager for a valuation tech brand.\n"
        f"SOURCE MATERIAL: {docs}\n\n"
        f"{feedback_context}\n\n"
        "TASK: Generate a professional Mastodon post based on the source material. "
        "You MUST incorporate the 'CRITICAL USER FEEDBACK' above. If the feedback says to be funny, be funny. If it says to avoid something, avoid it."
    )
    
    resp = None
    for attempt in range(3):
        try:
            resp = openai_client.responses.parse(
                model="nvidia/nemotron-3-nano-30b-a3b:free",
                input=prompt,
                text_format=SocialMediaPost,
            )
            break
        except Exception as e:
            print(f"⚠️ Generation failed (Attempt {attempt+1}/3): {e}")
            time.sleep(2)
    
    if not resp:
        raise Exception("Failed to generate post after 3 attempts.")
        
    return resp.output_parsed, past_feedback

def publish_to_mastodon(post_object):
    """Goal 3: RESTORED - Publishes with signature."""
    full_text = (
        f"{post_object.content}\n\n"
        f"{' '.join(post_object.hashtags)}\n\n"
        "🤖 Prepared by the Valuation Engine AI"
    )
    status = mastodon.status_post(full_text)
    print(f"✅ Post Published! URL: {status['url']}")
    return status

def extract_keywords(docs):
    """Goal 4: Identifies search terms."""
    resp = openai_client.responses.parse(
        model="nvidia/nemotron-3-nano-30b-a3b:free",
        input=f"Analyze these docs and give me 5 search keywords: {docs}",
        text_format=BusinessKeywords,
    )
    return resp.output_parsed.primary_keywords

def fetch_and_reply_batch(keyword, branding_context):
    """Goal 4: Searches and replies in a batch."""
    results = mastodon.search_v2(keyword, result_type="statuses")
    posts = results['statuses'][:5]
    if not posts: 
        print(f"No recent posts found for keyword: {keyword}")
        return
    
    prompt = f"Branding context: {branding_context}. Reply to these 5 posts: {posts}"
    resp = openai_client.responses.parse(
        model="nvidia/nemotron-3-nano-30b-a3b:free",
        input=prompt,
        text_format=ReplyBatch,
    )
    
    for r in resp.output_parsed.all_replies:
            # Wait between 30 to 90 seconds (human-like behavior)
            wait_time = random.randint(30, 90)
            print(f"⏳ Waiting {wait_time}s before next reply...")
            
            time.sleep(wait_time) # This will work now!
            
            try:
                final_reply = f"{r.reply_text}\n\n— Prepared by the Valuation Engine AI"
                mastodon.status_post(status=final_reply, in_reply_to_id=r.post_id)
                print(f"✅ Replied to post {r.post_id}")
            except Exception as e:
                print(f"⚠️ Could not reply: {e}")

# Add Telegram Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ... existing code ...

def generate_embedding(text):
    """Generates a vector embedding for the given text."""
    try:
        response = openai_client.embeddings.create(
            model="openai/text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"⚠️ Embedding failed: {e}")
        return []

def send_telegram_preview(message, callback_id, allow_feedback=True, used_feedback=None):
    """Sends preview with Accept/Reject buttons."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # Define the buttons
    buttons = [{"text": "✅ Accept", "callback_data": f"yes_{callback_id}"}]
    if allow_feedback:
        buttons.append({"text": "❌ Reject & Teach", "callback_data": f"teach_{callback_id}"})
    else:
        buttons.append({"text": "❌ Reject", "callback_data": f"no_{callback_id}"})

    keyboard = {
        "inline_keyboard": [buttons]
    }
    
    full_message = f"🔔 *HITL Review Required*\n\n{message}"
    
    if used_feedback:
        full_message += "\n\n🧠 *Memory Used:*\n" + "\n".join(used_feedback)
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": full_message,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(keyboard)
    }
    requests.post(url, json=payload)

def wait_for_telegram_approval(callback_id):
    """Polls for button press AND feedback if rejected."""
    print(f"⏳ Waiting for Telegram button press ({callback_id})...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    
    last_update_id = 0
    
    # 1. Wait for Button Click
    while True:
        try:
            response = requests.get(url, params={"offset": last_update_id + 1}).json()
            for update in response.get("result", []):
                last_update_id = update["update_id"]
                
                if "callback_query" in update:
                    data = update["callback_query"]["data"]
                    
                    if data == f"yes_{callback_id}":
                        print("✅ Approval received!")
                        # Clear buttons
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageReplyMarkup", 
                                      json={"chat_id": TELEGRAM_CHAT_ID, "message_id": update["callback_query"]["message"]["message_id"], "reply_markup": None})
                        return True, None
                        
                    elif data == f"teach_{callback_id}":
                        print("❌ Rejected. Waiting for feedback...")
                        # Acknowledge and ask for feedback
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                      json={"chat_id": TELEGRAM_CHAT_ID, "text": "📝 I'm listening. What should I change? (Reply in text)"})
                        
                        # 2. Enter Feedback Polling Loop (Wait for Text)
                        start_time = time.time()
                        while time.time() - start_time < 120: # 2 minute timeout
                            resp = requests.get(url, params={"offset": last_update_id + 1}).json()
                            for upd in resp.get("result", []):
                                last_update_id = upd["update_id"]
                                if "message" in upd and "text" in upd["message"]:
                                    feedback = upd["message"]["text"]
                                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                                  json={"chat_id": TELEGRAM_CHAT_ID, "text": "✅ Got it. I've saved this rule for next time."})
                                    return False, feedback
                            time.sleep(2)
                        
                        return False, None # Timeout

                    elif data == f"no_{callback_id}":
                        print("❌ Rejected (No feedback).")
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageReplyMarkup", 
                                      json={"chat_id": TELEGRAM_CHAT_ID, "message_id": update["callback_query"]["message"]["message_id"], "reply_markup": None})
                        return False, None
        except Exception as e:
            print(f"Error checking Telegram: {e}")
        
        time.sleep(3)

def get_all_scored_memories():
    """Returns ALL memories with their current relevance score."""
    db = SessionLocal()
    try:
        # Standard query for "General Rules"
        query_embedding = generate_embedding("social media style guide rules, user preferences, and critical feedback to follow")
        
        if not query_embedding:
            return []
        
        memories = db.query(FeedbackMemory).all()
        
        import numpy as np
        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        
        results = []
        for m in memories:
            score = 0.0
            if m.embedding:
                score = cosine_similarity(query_embedding, m.embedding)
            
            results.append({
                "id": m.id,
                "created_at": m.created_at.isoformat() if m.created_at else "",
                "feedback_text": m.feedback_text,
                "original_content": m.original_content,  # <--- Added this field
                "score": float(score) # Convert numpy float to python float
            })
            
        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
        
    except Exception as e:
        print(f"⚠️ Scoring failed: {e}")
        return []
    finally:
        db.close()
