from database import SessionLocal, FeedbackMemory

def check_feedback():
    db = SessionLocal()
    try:
        memories = db.query(FeedbackMemory).all()
        if not memories:
            print("📭 No feedback stored yet.")
        for m in memories:
            print(f"🆔 ID: {m.id}")
            print(f"📝 Feedback: {m.feedback_text}")
            print(f"📅 Date: {m.created_at}")
            print("-" * 30)
    except Exception as e:
        print(f"❌ Error reading database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_feedback()