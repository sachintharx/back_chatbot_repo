from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import ChatSession
from .utils import handle_english_message, intent_model  # Add intent_model import
from .chat_history import save_chat_history, check_session_timeout  # Import methods from chat_history.py
import json
from pymongo import MongoClient 
import datetime
import os
from dotenv import load_dotenv
from node_data.handlers.bill_inquiries import BillInquiriesHandler
from node_data.handlers.solar_service import SolarServiceHandler  # Import SolarServiceHandler

# # Load environment variables
# load_dotenv()

# # Initialize MongoDB client and collection with environment variables
# MONGO_URI = os.getenv('MONGO_URI')
# MONGO_DB = os.getenv('MONGO_DB', 'default_db')
# MONGO_COLLECTION = os.getenv('MONGO_COLLECTION', 'default_collection')

# client = MongoClient(MONGO_URI)
# db = client[MONGO_DB]
# collection = db[MONGO_COLLECTION]

# Load the conversation tree
with open("node_data/tree_structure.json", encoding="utf-8") as f:
    tree_structure = json.load(f)

categories = [
    'greetings', 
    'Fault Reporting', 
    'Bill Inquiries', 
    'New Connection Requests', 
    'Incident Reports', 
    'Solar Services' 
]

class ChatbotAPI(APIView):
    def __init__(self):
        super().__init__()
        self.bill_handler = BillInquiriesHandler()
        self.solar_handler = SolarServiceHandler()  # Initialize SolarServiceHandler

    def get_category_node_mapping(self):
        return {
            'Fault Reporting': 'fault_reporting',
            'Bill Inquiries': 'bill_inquiries',
            'New Connection Requests': 'new_connection',
            'Incident Reports': 'fault_reporting',
            'Solar Services': 'solar_service'
        }

    # def get_selected_category(self, state):
    #     category_mapping = {
    #         'fault_reporting': 'Fault Reporting',
    #         'bill_inquiries': 'Bill Inquiries',
    #         'new_connection': 'New Connection Requests',
    #         'solar_service': 'Solar Services',
    #         'other_services': 'Other Services'
    #     }
    #     return category_mapping.get(state, "Unknown")

    def post(self, request):
        session_id = request.data.get("session_id")
        user_message = request.data.get("message")

        chat_session, created = ChatSession.objects.get_or_create(session_id=session_id)
        
        # Handle session timeout
        if not created and check_session_timeout(chat_session):
            return Response({
                "message": "Session has expired due to inactivity. Please start a new session.",
                "type": "timeout"
            }, status=status.HTTP_408_REQUEST_TIMEOUT)

        # Handle new session
        if created:
            current_node = tree_structure["start"]
            chat_session.state = "start"
            chat_session.save()
            return Response({
                "message": current_node["message"],
                "type": current_node["type"],
                "options": current_node["options"]
            })

        current_node = tree_structure.get(chat_session.state)
        
        # Preserve language selection through the entire session
        if chat_session.state == "start" and user_message in current_node["options"]:
            next_node_key = current_node["next"][user_message]
            next_node = tree_structure[next_node_key]
            chat_session.selected_language = user_message
            chat_session.state = next_node_key
            chat_session.chat_history.append({
                "user": user_message,
                "bot": next_node["message"],
                "timestamp": datetime.datetime.now().isoformat()
            })
            chat_session.save()
            return Response({
                "message": next_node["message"],
                "type": next_node["type"],
                "options": next_node.get("options", [])
            })

        if not current_node:
            # Don't reset to start if in bill inquiry flow
            if not chat_session.state.startswith(('verification', 'contact_verification', 'display_balance')):
                chat_session.state = "start"
                chat_session.save()
                return Response({
                    "message": tree_structure["start"]["message"],
                    "type": "menu",
                    "options": tree_structure["start"]["options"]
                })

        # Handle bill inquiries with state preservation
        if chat_session.state.startswith(('bill_', 'verification', 'contact_verification', 'display_balance')):
            return self.bill_handler.handle_bill_inquiry(chat_session, user_message, current_node)

        # Handle solar services with state preservation
        if chat_session.state.startswith('solar_service'):
            return self.solar_handler.handle_solar_service(chat_session, user_message, current_node)

        if chat_session.state == "solar_details":
            return self.solar_handler.handle_solar_service(chat_session, user_message, "solar_details")

        if current_node["type"] == "menu":
            if user_message in current_node["options"]:
                next_node_key = current_node["next"][user_message]
                next_node = tree_structure[next_node_key]
                if next_node_key == "bill_inquiries":
                    chat_session.state = "bill_inquiries"
                    chat_session.save()
                    return self.bill_handler.handle_bill_inquiry(chat_session, user_message, tree_structure[next_node_key])
                if next_node_key == "solar_service":
                    chat_session.state = "solar_service"
                    chat_session.save()
                    return self.solar_handler.handle_solar_service(chat_session, user_message, tree_structure[next_node_key])
                chat_session.state = next_node_key
                chat_session.chat_history.append({
                    "user": user_message,
                    "bot": next_node["message"]
                })
                chat_session.save()
                return Response({
                    "message": next_node["message"],
                    "type": next_node["type"],
                    "options": next_node.get("options", [])
                })
            return Response({
                "message": "Please select a valid option",
                "type": "menu",
                "options": current_node["options"]
            })

        if current_node["type"] == "message" or current_node["type"] == "classification":
            chat_session.chat_history.append({
                "user": user_message,
                "bot": None
            })
            if chat_session.state == "english_start":
                return handle_english_message(chat_session, user_message, categories, tree_structure)
            try:
                intent = intent_model.predict([user_message])[0]
                response_message = f"Identified intent: {intent}"
                next_node_key = current_node.get("next", {}).get(intent)
                if next_node_key:
                    chat_session.state = next_node_key
                    next_node_data = tree_structure[next_node_key]
                    chat_session.chat_history[-1]["bot"] = response_message
                    chat_session.save()
                    if next_node_key == "solar_service":
                        return self.solar_handler.handle_solar_service(chat_session, user_message, next_node_data)
                    return Response({
                        "message": response_message,
                        "type": "menu",
                        "options": next_node_data["options"]
                    })
            except Exception:
                return Response({
                    "message": "I couldn't understand. Would you like to:",
                    "type": "menu",
                    "options": ["Try Again", "Main Menu", "Exit"]
                })

        if current_node["type"] == "end":
            if save_chat_history(session_id, chat_session, user_message):
                chat_session.delete()
                return Response({
                    "message": current_node["message"],
                    "type": "end"
                })
            else:
                return Response({
                    "message": "Error saving chat history. Please try again.",
                    "type": "error"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if chat_session.state == "english_menu" and current_node["type"] == "message":
            return handle_english_message(chat_session, user_message, categories, tree_structure)

        return Response({"message": "Something went wrong"}, status=status.HTTP_400_BAD_REQUEST)


