import json
from pathlib import Path
from rest_framework.response import Response
import requests
import re


class SolarServiceHandler:
    """Handler class for managing solar service related interactions"""
    
    _instance = None  # Class variable for singleton pattern
    
    def __new__(cls):
        # Implement singleton pattern to avoid multiple initializations
        if cls._instance is None:
            print("[INFO] Creating new SolarServiceHandler instance")
            cls._instance = super(SolarServiceHandler, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not self.initialized:
            print("[INFO] Initializing SolarServiceHandler")
            self.nodes = {}
            try:
                self._load_nodes()
                self.initialized = True
            except Exception as e:
                print(f"[ERROR] Initialization failed: {e}")
                self.initialized = False
        else:
            print("[DEBUG] Using existing SolarServiceHandler instance")
    
    def _load_nodes(self):
        """Load conversation flow nodes from JSON files (English and Sinhala)"""
        print("[INFO] Loading node data")
        base_path = Path(__file__).parent.parent / "categories" / "solar_service"
        try:
            with open(base_path / "en_solar_service.json", encoding='utf-8') as f:
                data = json.load(f)
                self.nodes["solar_service"] = data["solar_service"]
                self.nodes.update(data)
            
            try:
                with open(base_path / "si_solar_service.json", encoding='utf-8') as f:
                    data = json.load(f)
                    self.nodes["solar_service_si"] = data["solar_service_si"]
                    self.nodes.update(data)
            except FileNotFoundError:
                print("[WARN] Sinhala solar service file not found. Proceeding without it.")
            
            print("[INFO] Successfully loaded node data")
        except Exception as e:
            print(f"[ERROR] Error loading solar service nodes: {e}")
            raise

    def handle_solar_service(self, chat_session, user_message, current_node):
        """Handle solar service with improved logging"""
        print(f"\n[INFO] ====== New Solar Service Request ======")
        print(f"[INFO] Session ID: {chat_session.id}")
        print(f"[INFO] Current State: {chat_session.state}")
        print(f"[INFO] User Message: {user_message}")
        print(f"[INFO] Language: {chat_session.selected_language}")

        try:
            current_node_key = chat_session.state if isinstance(chat_session.state, str) else "solar_service"
            current_solar_node = self.nodes.get(current_node_key, self.nodes["solar_service"])
            if chat_session.selected_language == "Sinhala":
                current_solar_node = self.nodes.get(current_node_key, self.nodes["solar_service_si"])
            
            if current_solar_node["type"] == "menu":
                return self._handle_menu(chat_session, user_message, current_solar_node)
            
            elif current_solar_node["type"] == "form":
                return self._handle_form_input(chat_session, user_message, current_solar_node)
        
        except Exception as e:
            print(f"[ERROR] ====== Error in solar service handler ======")
            print(f"[ERROR] Error type: {type(e).__name__}")
            print(f"[ERROR] Error message: {str(e)}")
            
            return Response({
                "message": "An error occurred. Returning to menu.",
                "type": "menu",
                "options": self.nodes["solar_service"]["options"]
            })

    def _handle_menu(self, chat_session, user_message, current_solar_node):
        """Handle menu type nodes"""
        print(f"[DEBUG] Node type: Menu")
        print(f"[DEBUG] Available options: {current_solar_node['options']}")
        print(f"[DEBUG] User selected: {user_message}")
        
        if user_message in current_solar_node["options"]:
            next_node_key = current_solar_node["next"][user_message]
            next_node = self.nodes.get(next_node_key)
            
            if next_node:
                chat_session.state = next_node_key
                chat_session.chat_history.append({
                    "user": user_message,
                    "bot": next_node["message"]
                })
                chat_session.save()
                
                return Response({
                    "message": next_node["message"],
                    "type": next_node["type"],
                    "options": next_node.get("options", []),
                    "fields": next_node.get("fields", [])
                })
        
        return Response({
            "message": "Invalid option. Please select from the menu.",
            "type": "menu",
            "options": current_solar_node["options"]
        })

    def _handle_form_input(self, chat_session, user_message, current_node):
        """Handle form input for solar service"""
        print(f"\n[INFO] ====== Form Input Handler ======")
        print(f"[INFO] Current state: {chat_session.state}")
        print(f"[INFO] User input: {user_message}")
        
        if not hasattr(chat_session, 'temp_data'):
            chat_session.temp_data = {}

        chat_session.chat_history.append({
            "user": user_message,
            "bot": "Processing your request..."
        })

        try:
            if chat_session.state == "verification":
                return self._verify_account_number(chat_session, user_message)
            
            elif chat_session.state == "contact_verification":
                return self._verify_contact_number(chat_session, user_message)
            
            elif chat_session.state == "solar_details":
                chatbot_response = self.fetch_chatbot_response(user_message, chat_session)
                chat_session.chat_history[-1]["bot"] = chatbot_response
                chat_session.save()
                return Response({
                    "message": chatbot_response,
                    "type": "message"
                })
            
        except Exception as e:
            print(f"[ERROR] Form input processing error: {str(e)}")
            return self._handle_error(chat_session, user_message)

    def fetch_chatbot_response(self, user_message, session):
        """Fetch response from the chatbot API"""
        api_url = "http://localhost:8001/chat/"
        payload = {
            "question": user_message,
            "session_id": session.get("session_id", "default")  # Default session if not provided
        }
        
        try:
            # Send POST request to the FastAPI server
            response = requests.post(api_url, json=payload)
            
            # Check if the response is successful
            if response.status_code == 200:
                response_data = response.json()
                
                # Update session with the new session_id if returned
                if 'session_id' in response_data:
                    session["session_id"] = response_data["session_id"]
                
                # Return the chatbot's response
                return response_data.get("response", "I'm sorry, I couldn't understand that.")
            else:
                return f"Error: {response.status_code}, Unable to get response from the chatbot."
        
        except Exception as e:
            return f"An error occurred while fetching the chatbot response: {str(e)}"

    def _verify_account_number(self, chat_session, user_message):
        """Verify the account number provided by the user"""
        print("[DEBUG] Processing account verification")
        
        if not re.match(r'^\d{10}$', user_message):
            return Response({
                "message": "Please enter a valid 10-digit account number.",
                "type": "form",
                "fields": ["account_number"]
            })

        chat_session.temp_data['account'] = user_message
        chat_session.save()

        result = self.validate_account_number_with_api(user_message)
        print(f"[DEBUG] API validation result: {result}")
        
        if result['valid']:
            print(f"[INFO] Account {user_message} validated successfully")
            chat_session.temp_data['balance'] = result['balance']
            chat_session.save()
            
            chat_session.state = "contact_verification"
            next_message = self.nodes["contact_verification"]["message"]
            chat_session.chat_history[-1]["bot"] = next_message
            chat_session.save()
            
            return Response({
                "message": next_message,
                "type": "form",
                "fields": ["contact_number"]
            })
        else:
            print(f"[WARN] Invalid account number: {user_message}")
            chat_session.temp_data.pop('account', None)
            chat_session.save()
            
            error_message = "Invalid account number. Please try again."
            chat_session.chat_history[-1]["bot"] = error_message
            chat_session.save()
            return Response({
                "message": error_message,
                "type": "form",
                "fields": ["account_number"]
            })

    def _verify_contact_number(self, chat_session, user_message):
        """Verify the contact number provided by the user"""
        print("[DEBUG] Verifying contact number")
        
        if not re.match(r'^\d{10}$', user_message):
            return Response({
                "message": "Invalid contact number format. Please enter a 10-digit number (e.g., 0714445598)",
                "type": "form",
                "fields": ["contact_number"]
            })

        contact_result = self.validate_contact_number_with_api(user_message)
        api_account = contact_result.get('account_number', '') if contact_result else ''
        
        print(f"[DEBUG] Contact validation result: {contact_result}")
        
        if api_account:
            response_message = (
                "Contact Number Verified Successfully\n\n"
                f"• Contact Number: {user_message}\n"
                f"• Associated Account: {api_account}"
            )
            chat_session.state = "display_balance"
            chat_session.save()
            
            return Response({
                "message": response_message,
                "type": "menu",
                "options": self.nodes["display_balance"]["options"]
            })
        else:
            mismatch_details = (
                f"Contact Number Verification Failed\n\n"
                f"• Contact Number: {user_message}\n"
                f"• No associated account found.\n\n"
                f"Please check and try again with the correct contact number."
            )
            
            print(f"[DEBUG] Mismatch detected: {mismatch_details}")
            
            chat_session.state = "account_comparison"
            chat_session.chat_history[-1]["bot"] = mismatch_details
            chat_session.save()
            
            return Response({
                "message": mismatch_details,
                "type": "menu",
                "options": ["Try Again", "Exit"]
            })

    def _handle_error(self, chat_session, user_message):
        """Handle errors during form input processing"""
        error_message = (
            f"An error occurred while processing your request.\n"
            f"Please try again later."
        )
        
        chat_session.state = "solar_service"
        chat_session.chat_history[-1]["bot"] = error_message
        chat_session.save()
        
        return Response({
            "message": error_message,
            "type": "menu",
            "options": self.nodes["solar_service"]["options"]
        })

    def validate_account_number_with_api(self, account_number):
        """Validate the account number with the external API"""
        print(f"\n[INFO] ====== Account Validation Request ======")
        print(f"[INFO] Account number: {account_number}")
        
        try:
            api_url = f"http://example.com/api/validate_account?accountNumber={account_number}"
            print(f"[DEBUG] Calling API: {api_url}")
            
            response = requests.get(api_url, timeout=10)
            print(f"[DEBUG] API Response: Status={response.status_code}, Content={response.text}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("valid"):
                    balance = float(data.get("balance", 0))
                    print(f"[INFO] Account {account_number} is valid with balance: {balance}")
                    return {'valid': True, 'balance': balance}
                else:
                    print(f"[WARN] API response indicates invalid account: {data}")
            else:
                print(f"[ERROR] Unexpected status code: {response.status_code}")
        
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"[ERROR] API error: {str(e)}")
        
        return {'valid': False}

    def validate_contact_number_with_api(self, contact_number):
        """Validate the contact number with the external API"""
        print(f"[INFO] Validating contact number: {contact_number}")
        try:
            api_url = f"http://example.com/api/validate_contact?contactNumber={contact_number}"
            print(f"[DEBUG] Calling API: {api_url}")
            
            response = requests.get(api_url, timeout=10)
            print(f"[DEBUG] API Response: Status={response.status_code}, Content={response.text}")
            
            if response.status_code == 200:
                data = response.json()
                return {'account_number': data.get("account_number")}
        except (requests.exceptions.RequestException, IndexError) as e:
            print(f"[ERROR] Contact API error: {str(e)}")
        return {'account_number': None}
