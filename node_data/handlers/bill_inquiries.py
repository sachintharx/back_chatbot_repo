import json
from pathlib import Path
from rest_framework.response import Response
import requests
import re

class BillInquiriesHandler:
    """Handler class for managing bill inquiry related interactions"""
    
    _instance = None  # Class variable for singleton pattern
    account_numbers = {}  # Dictionary to store account numbers with session IDs
    account_balances = {}  # Dictionary to store account balances with session IDs
    
    def __new__(cls):
        # Implement singleton pattern to avoid multiple initializations
        if cls._instance is None:
            print("[INFO] Creating new BillInquiriesHandler instance")
            cls._instance = super(BillInquiriesHandler, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not self.initialized:
            print("[INFO] Initializing BillInquiriesHandler")
            self.nodes = {}
            try:
                self._load_nodes()
                self.initialized = True
            except Exception as e:
                print(f"[ERROR] Initialization failed: {e}")
                self.initialized = False
        else:
            print("[DEBUG] Using existing BillInquiriesHandler instance")
    
    def _load_nodes(self):
        """Load conversation flow nodes from JSON files (English and Sinhala)"""
        print("[INFO] Loading node data")
        base_path = Path(__file__).parent.parent / "categories" / "bill_inquiries"
        try:
            with open(base_path / "en_bill_inquiries.json", encoding='utf-8') as f:
                data = json.load(f)
                self.nodes["bill_inquiries"] = data["bill_inquiries"]
                self.nodes.update(data)
            
            with open(base_path / "si_bill_inquiries.json", encoding='utf-8') as f:
                data = json.load(f)
                self.nodes["bill_inquiries_si"] = data["bill_inquiries_si"]
                self.nodes.update(data)
            print("[INFO] Successfully loaded node data")
        except Exception as e:
            print(f"[ERROR] Error loading bill inquiry nodes: {e}")
            raise

    def handle_bill_inquiry(self, chat_session, user_message, current_node):
        """Handle bill inquiry with improved logging"""
        print(f"\n[INFO] ====== New Bill Inquiry Request ======")
        print(f"[INFO] Session ID: {chat_session.id}")
        print(f"[INFO] Current State: {chat_session.state}")
        print(f"[INFO] User Message: {user_message}")
        print(f"[INFO] Language: {chat_session.selected_language}")

        try:
            if chat_session.state in ["verification", "contact_verification", "display_balance"]:
                return self._handle_form_input(chat_session, user_message, self.nodes[chat_session.state])
            
            current_bill_node = self.nodes.get(chat_session.state, self.nodes["bill_inquiries"])
            if chat_session.selected_language == "Sinhala":
                current_bill_node = self.nodes.get(chat_session.state, self.nodes["bill_inquiries_si"])
            
            if current_bill_node["type"] == "menu":
                return self._handle_menu(chat_session, user_message, current_bill_node)
            
            elif current_bill_node["type"] == "form":
                return self._handle_form_input(chat_session, user_message, current_bill_node)
        
        except Exception as e:
            print(f"[ERROR] ====== Error in bill inquiry handler ======")
            print(f"[ERROR] Error type: {type(e).__name__}")
            print(f"[ERROR] Error message: {str(e)}") 
            
            return Response({
                "message": "An error occurred. Returning to menu.",
                "type": "menu",
                "options": self.nodes["bill_inquiries"]["options"]
            })

    def _handle_menu(self, chat_session, user_message, current_bill_node):
        """Handle menu type nodes"""
        print(f"[DEBUG] Node type: Menu")
        print(f"[DEBUG] Available options: {current_bill_node['options']}")
        print(f"[DEBUG] User selected: {user_message}")
        
        if user_message in current_bill_node["options"]:
            next_node_key = current_bill_node["next"][user_message]
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
            "options": current_bill_node["options"]
        })

    def _handle_form_input(self, chat_session, user_message, current_node):
        """Handle form input for account and contact verification"""
        print(f"\n[INFO] ====== Form Input Handler ======")
        print(f"[INFO] Current state: {chat_session.state}")
        print(f"[INFO] User input: {user_message}")
        
        stored_account = ''
        
        if not hasattr(chat_session, 'temp_data'):
            chat_session.temp_data = {}

        chat_session.chat_history.append({
            "user": user_message,
            "bot": "Processing your request..."
        })

        try:
            stored_account = self.account_numbers.get(chat_session.id, '')
            print(f"[DEBUG] Retrieved stored account number: {stored_account}")

            if chat_session.state == "verification":
                return self._verify_account_number(chat_session, user_message)
            
            elif chat_session.state == "contact_verification":
                return self._verify_contact_number(chat_session, user_message, stored_account)
            
            elif chat_session.state == "account_comparison":
                return self._handle_account_comparison(chat_session, user_message)

        except Exception as e:
            print(f"[ERROR] Form input processing error: {str(e)}")
            return self._handle_error(chat_session, user_message, stored_account)

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
        self.account_numbers[chat_session.id] = user_message
        print(f"[DEBUG] Stored account number: {chat_session.temp_data['account']}")
        chat_session.save()

        result = self.validate_account_number_with_api(user_message)
        print(f"[DEBUG] API validation result: {result}")
        
        if result['valid']:
            print(f"[INFO] Account {user_message} validated successfully")
            chat_session.temp_data['balance'] = result['balance']
            self.account_balances[chat_session.id] = result['balance']
            print(f"[DEBUG] Stored balance: {chat_session.temp_data['balance']}")
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
            self.account_numbers.pop(chat_session.id, None)
            self.account_balances.pop(chat_session.id, None)
            chat_session.save()
            
            error_message = "Invalid account number. Please try again."
            chat_session.chat_history[-1]["bot"] = error_message
            chat_session.save()
            return Response({
                "message": error_message,
                "type": "form",
                "fields": ["account_number"]
            })

    def _verify_contact_number(self, chat_session, user_message, stored_account):
        """Verify the contact number provided by the user"""
        print("[DEBUG] Verifying contact number")
        
        if not stored_account:
            print("[WARN] No stored account found")
            return Response({
                "message": "Session expired. Please start over.",
                "type": "menu",
                "options": self.nodes["bill_inquiries"]["options"]
            })

        if not re.match(r'^\d{10}$', user_message):
            return Response({
                "message": "Invalid contact number format. Please enter a 10-digit number (e.g., 0714445598)",
                "type": "form",
                "fields": ["contact_number"]
            })

        contact_result = self.validate_contact_number_with_api(user_message)
        api_account = contact_result.get('account_number', '') if contact_result else ''
        
        print(f"[DEBUG] Contact validation result: {contact_result}")
        print(f"[DEBUG] Stored account: {stored_account}")
        print(f"[DEBUG] API returned account: {api_account}")
        
        if api_account and api_account == stored_account:
            stored_balance = self.account_balances.get(chat_session.id, 0)
            response_message = (
                "Account Balance Information\n\n"
                f"• Account Number: {stored_account}\n"
                f"• Current Balance: Rs. {stored_balance:.2f}"
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
                f"• Your Account: {stored_account}\n"
                f"• Found Account: {api_account or 'No account found'}\n\n"
                f"Error: This contact number is not associated with account {stored_account}.\n"
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

    def _handle_account_comparison(self, chat_session, user_message):
        """Handle the account comparison response"""
        if user_message == "Try Again":
            chat_session.state = "contact_verification"
            chat_session.save()
            return Response({
                "message": self.nodes["contact_verification"]["message"],
                "type": "form",
                "fields": ["contact_number"]
            })
        elif user_message == "Exit":
            chat_session.state = "bill_inquiries"
            chat_session.save()
            return Response({
                "message": self.nodes["bill_inquiries"]["message"],
                "type": "menu",
                "options": self.nodes["bill_inquiries"]["options"]
            })

    def _handle_error(self, chat_session, user_message, stored_account):
        """Handle errors during form input processing"""
        comparison_details = (
            f"Contact Number Verification Failed\n\n"
            f"• Entered Contact Number: {user_message}\n"
            f"• Your Account Number: {stored_account}\n"
            f"• Account Number Found: No account found\n\n"
            f"This contact number is not registered with the account number you provided.\n"
            f"Please verify that you are using the correct contact number registered with your account."
        )
        
        chat_session.state = "account_comparison"
        chat_session.chat_history[-1]["bot"] = comparison_details
        chat_session.save()
        
        return Response({
            "message": comparison_details,
            "type": "display",
            "options": self.nodes["account_comparison"]["options"]
        })

    def validate_account_number_with_api(self, account_number):
        """Validate the account number with the external API"""
        print(f"\n[INFO] ====== Account Validation Request ======")
        print(f"[INFO] Account number: {account_number}")
        
        try:
            api_url = f"http://124.43.163.177:8080/CCLECO/Main/GetAccountBalance?accountNumber={account_number}"
            print(f"[DEBUG] Calling API: {api_url}")
            
            response = requests.get(api_url, timeout=10)
            print(f"[DEBUG] API Response: Status={response.status_code}, Content={response.text}")
            
            if response.status_code == 200:
                data = response.text.split(',')
                if len(data) >= 2 and data[0] == "YES":
                    balance = float(data[1])
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
            api_url = f"http://124.43.163.177:8080/CCLECO/Main/GetAccountNumber?contactNumber={contact_number}"
            print(f"[DEBUG] Calling API: {api_url}")
            
            response = requests.get(api_url, timeout=10)
            print(f"[DEBUG] API Response: Status={response.status_code}, Content={response.text}")
            
            if response.status_code == 200:
                data = response.text.strip()
                return {'account_number': data}
        except (requests.exceptions.RequestException, IndexError) as e:
            print(f"[ERROR] Contact API error: {str(e)}")
        return {'account_number': None}

    @staticmethod
    def extract_account_number(message):
        """Extract a 10-digit account number from a message"""
        match = re.search(r'\b\d{10}\b', message)
        return match.group() if match else None

    @staticmethod
    def extract_mobile_number(message):
        """Extract a 10-digit mobile number from a message"""
        cleaned_message = re.sub(r'[^0-9]', '', message)
        match = re.search(r'\b\d{10}\b', cleaned_message)
        return match.group() if match else None

    @staticmethod
    def extract_payment_amount(message):
        """Extract a payment amount from a message"""
        match = re.search(r'\d+(\.\d{2})?', message)
        return float(match.group()) if match else None