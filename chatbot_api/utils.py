import joblib
import os
from rest_framework.response import Response

MODEL_PATH = os.path.join("models", "best_rf_classifier_model_V_5.joblib")
VECTORIZER_PATH = os.path.join("models", "tfidf_vectorizer_V_5.joblib")

def load_intent_model():
    return joblib.load(MODEL_PATH)

def load_vectorizer():
    return joblib.load(VECTORIZER_PATH)

# Load models
intent_model = load_intent_model()
vectorizer = load_vectorizer()

def handle_english_message(chat_session, user_message, categories, tree_structure):
    try:
        print(f"Processing message: {user_message}")
        message_vect = vectorizer.transform([user_message])
        predictions = intent_model.predict(message_vect)
        pred_array = predictions[0]
        predicted_labels = [
            categories[i] for i in range(len(categories)) if pred_array[i] == 1
        ]
        print(f"Predicted labels: {predicted_labels}")

        if predicted_labels:
            category = predicted_labels[0]
            print(f"Selected category: {category}")
            chat_session.mistake_count = 0
            chat_session.save()
            if category == 'greetings':
                chat_session.chat_history.append({
                    "user": user_message,
                    "bot": "Hello! How can I assist you today?"
                })
                chat_session.save()
                return Response({
                    "message": "Hello! How can I assist you today?",
                    "type": "message"
                })
            node_mapping = get_category_node_mapping()
            next_node_key = node_mapping.get(category)
            if next_node_key:
                next_node = tree_structure[next_node_key]
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
        chat_session.mistake_count += 1
        if chat_session.mistake_count >= 3:
            chat_session.state = "english_menu"
            chat_session.mistake_count = 0
            chat_session.save()
            return Response({
                "message": "I'm having trouble understanding. Let me show you the available options:",
                "type": "menu",
                "options": tree_structure["english_menu"]["options"]
            })
        chat_session.save()
        return Response({
            "message": "Sorry, I couldn't understand that. Please try again.",
            "type": "message"
        })
    except Exception as e:
        print(f"Error in intent classification: {str(e)}")
        return Response({
            "message": f"Sorry, something went wrong: {str(e)}",
            "type": "error"
        })

def get_category_node_mapping():
    return {
        'Fault Reporting': 'fault_reporting',
        'Bill Inquiries': 'bill_inquiries',
        'New Connection Requests': 'new_connection',
        'Incident Reports': 'fault_reporting',
        'Solar Services': 'solar_service'
    }
