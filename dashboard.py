import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import FeedbackMemory
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page Config
st.set_page_config(page_title="Sundai Agent Admin", page_icon="🤖", layout="wide")

# Database Connection
SQLALCHEMY_DATABASE_URL = "sqlite:///./sundai_iap.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Ensure tables exist
from database import Base
Base.metadata.create_all(bind=engine)

def get_feedback_data():
    """Fetches feedback data from the Cloud API (Server-Side Logic)."""
    api_key = os.getenv("API_KEY")
    headers = {"X-API-Key": api_key}
    # Cloud VM Public IP
    api_url = "http://104.198.235.165:8000/memories"
    
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        else:
            st.error(f"Failed to fetch data: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Connection error: {e}")
        return pd.DataFrame()

def delete_feedback(feedback_id):
    session = SessionLocal()
    try:
        record = session.query(FeedbackMemory).filter(FeedbackMemory.id == feedback_id).first()
        if record:
            session.delete(record)
            session.commit()
            return True
        return False
    except Exception as e:
        st.error(f"Error deleting: {e}")
        return False
    finally:
        session.close()

def trigger_automation():
    api_key = os.getenv("API_KEY")
    headers = {"X-API-Key": api_key}
    # Cloud VM Public IP
    api_url = "http://104.198.235.165:8000/run-automation"
    
    try:
        response = requests.post(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "error", "detail": f"HTTP {response.status_code}: {response.text}"}
    except Exception as e:
        return {"error": str(e)}

# --- UI Layout ---

st.title("🤖 Sundai Social Agent Admin")

# Simple Authentication
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    password = st.text_input("Enter Admin Password", type="password")
    if st.button("Login"):
        if password == os.getenv("API_KEY", "admin"): # Use API_KEY as password
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop() # Stop execution here if not authenticated

# Sidebar for Actions
with st.sidebar:
    st.header("🚀 Actions")
    if st.button("Run Daily Automation", type="primary"):
        with st.spinner("Triggering automation..."):
            result = trigger_automation()
            if "status" in result and result["status"] == "success":
                st.success("✅ Automation Started!")
                st.json(result)
            else:
                st.error("❌ Failed to start")
                st.json(result)
    
    st.divider()
    st.info("Ensure the FastAPI server is running locally on port 8000.")

# Main Content: Memory Management
st.subheader("🧠 Knowledge Base (Feedback Memory)")
st.caption("Manage the rules and feedback your agent has learned.")

# Refresh Data
if st.button("🔄 Refresh Data"):
    st.rerun()

df = get_feedback_data()

if not df.empty:
    # Display as a data editor (editable table)? 
    # For now, let's just show it and offer a delete button per row logic or a selector.
    
    # Let's use a simpler approach: Select to Delete
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.dataframe(
            df[["id", "feedback_text", "original_content", "created_at"]],
            use_container_width=True,
            hide_index=True
        )
        
    with col2:
        st.write("### 🗑️ Delete Memory")
        memory_to_delete = st.selectbox("Select ID to delete:", df["id"].tolist())
        
        if st.button(f"Delete ID {memory_to_delete}", type="secondary"):
            if delete_feedback(int(memory_to_delete)):
                st.success(f"Deleted Memory ID {memory_to_delete}")
                st.rerun()
            else:
                st.error("Failed to delete.")

else:
    st.warning("No memory entries found in the database.")

# Footer
st.markdown("---")
st.caption("Sundai IAP 2026 | Built with Streamlit")