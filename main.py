import os
from services import (
    get_notion_content, generate_social_post, 
    publish_to_mastodon, extract_keywords, 
    fetch_and_reply_batch, send_telegram_preview, 
    wait_for_telegram_approval, generate_embedding
)
from database import SessionLocal, FeedbackMemory

def run_daily_automation():
    page_id = os.getenv("NOTION_PAGE_ID")
    docs = get_notion_content(page_id)

    # --- GOAL 3: BRAND POST ---
    print("🤖 Generating brand post...")
    post_draft, used_feedback = generate_social_post(docs)
    
    preview_text = f"📝 *DRAFT POST:*\n{post_draft.content}"
    send_telegram_preview(preview_text, "brand_post", used_feedback=used_feedback)
    
    # Wait for approval OR feedback
    approved, feedback = wait_for_telegram_approval("brand_post")
    
    if approved:
        publish_to_mastodon(post_draft)
    elif feedback:
        print(f"📝 Saving feedback: {feedback}")
        # Save to RAG Memory
        db = SessionLocal()
        try:
            embedding = generate_embedding(f"Post: {post_draft.content}\nFeedback: {feedback}")
            memory = FeedbackMemory(
                original_content=post_draft.content,
                feedback_text=feedback,
                embedding=embedding
            )
            db.add(memory)
            db.commit()
            print("✅ Feedback saved to memory!")
        except Exception as e:
            print(f"⚠️ Failed to save memory: {e}")
        finally:
            db.close()
    else:
        print("Skipping brand post (Rejected without feedback).")

    # --- GOAL 4: ENGAGEMENT ---
    print("🔎 Analyzing keywords...")
    keywords = extract_keywords(docs)
    
    if keywords:
        keyword = keywords[0]
        send_telegram_preview(f"🎯 *Engagement Check*\nKeyword: `{keyword}`\nShould I find and reply to posts?", "engagement", allow_feedback=False)
        
        approved, _ = wait_for_telegram_approval("engagement")
        if approved:
            fetch_and_reply_batch(keyword, docs)
        else:
            print("Skipping engagement.")

if __name__ == "__main__":
    run_daily_automation()