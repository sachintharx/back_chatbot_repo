from pymongo import MongoClient
import datetime
from .models import ChatSession

# Initialize MongoDB client and collection with environment variables
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB = os.getenv('MONGO_DB', 'default_db')
MONGO_COLLECTION = os.getenv('MONGO_COLLECTION', 'default_collection')

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]

def get_selected_category(state):
    category_mapping = {
        'fault_reporting': 'Fault Reporting',
        'bill_inquiries': 'Bill Inquiries',
        'new_connection': 'New Connection Requests',
        'solar_service': 'Solar Services',
        'other_services': 'Other Services'
    }
    return category_mapping.get(state, "Unknown")

def save_chat_history(session_id, chat_session, user_message):
    try:
        chat_messages = []
        for msg in chat_session.chat_history:
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "user_message": msg.get("user", ""),
                "bot_response": msg.get("bot", ""),
                "message_type": "text"
            }
            if entry["user_message"] or entry["bot_response"]:
                chat_messages.append(entry)
        
        chat_data = {
            "session_id": session_id,
            "timestamp": datetime.datetime.now(),
            "selected_language": chat_session.selected_language,  # Save selected language
            "selected_category": get_selected_category(chat_session.state),  # Ensure selected category is saved
            "chat_messages": chat_messages,
            "session_start": chat_session.created_at,
            "session_end": datetime.datetime.now(),
            "final_state": chat_session.state
        }
        
        result = collection.insert_one(chat_data)
        print(f"Chat history saved with ID: {result.inserted_id}")
        return True
        
    except Exception as e:
        print(f"Error saving chat history: {e}")
        return False

def check_session_timeout(chat_session):
    if chat_session.is_session_expired():
        save_chat_history(chat_session.session_id, chat_session, "Session timeout")
        chat_session.delete()
        return True
    return False
