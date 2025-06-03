"""import json
from pathlib import Path
from rest_framework.response import Response
import requests
import re

class FaultReportingHandler:
    Handler class for managing fault reporting related interactions

    _instance = None  # Class variable for singleton pattern
    fault_reports = {}  # Dictionary to store fault reports with session IDs

    def __new__(cls):
        # Implement singleton pattern to avoid multiple initializations
        if cls._instance is None:
            print("[INFO] Creating new FaultReportingHandler instance")
            cls._instance = super(FaultReportingHandler, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not hasattr(self, 'initialized'):
            self.initialized = False
        if not self.initialized:
            print("[INFO] Initializing FaultReportingHandler")
            self.nodes = {}
            try:
                self._load_nodes()
                self.initialized = True
            except Exception as e:
                print(f"[ERROR] Initialization failed: {e}")
                self.initialized = False
        else:
            print("[DEBUG] Using existing FaultReportingHandler instance")

    def _load_nodes(self):
        Load conversation flow nodes from JSON files (English and Sinhala)
        print("[INFO] Loading node data")
        base_path = Path(__file__).parent.parent / "categories" / "fault_reporting"
        try:
            with open(base_path / "en_fault_reporting.json", encoding='utf-8') as f:
                data = json.load(f)
                self.nodes["fault_reporting"] = data["fault_reporting"]
                self.nodes.update(data)

            with open(base_path / "si_fault_reporting.json", encoding='utf-8') as f:
                data = json.load(f)
                self.nodes["fault_reporting_si"] = data["fault_reporting_si"]
                self.nodes.update(data)
            print("[INFO] Successfully loaded node data")
        except Exception as e:
            print(f"[ERROR] Error loading fault reporting nodes: {e}")
            raise

    def handle_fault_report(self, chat_session, user_message, current_node):
        Handle fault report with improved logging
        print(f"\n[INFO] ====== New Fault Report Request ======")
        print(f"[INFO] Session ID: {chat_session.id}")
        print(f"[INFO] Current State: {chat_session.state}")
        print(f"[INFO] User Message: {user_message}")
        print(f"[INFO] Language: {chat_session.selected_language}")

        try:
            if chat_session.state in ["awaiting_district", "awaiting_town", "awaiting_identifier", "awaiting_fault_type"]:
                return self._handle_form_input(chat_session, user_message, self.nodes[chat_session.state])

            current_fault_node = self.nodes.get(chat_session.state, self.nodes["fault_reporting"])
            if chat_session.selected_language == "Sinhala":
                current_fault_node = self.nodes.get(chat_session.state, self.nodes["fault_reporting_si"])

            if current_fault_node["type"] == "menu":
                return self._handle_menu(chat_session, user_message, current_fault_node)
            elif current_fault_node["type"] == "form":
                return self._handle_form_input(chat_session, user_message, current_fault_node)

        except Exception as e:
            print(f"[ERROR] ====== Error in fault report handler ======")
            print(f"[ERROR] Error type: {type(e).__name__}")
            print(f"[ERROR] Error message: {str(e)}")

            return Response({
                "message": "An error occurred. Returning to menu.",
                "type": "menu",
                "options": self.nodes["fault_reporting"]["options"]
            })

    def _handle_menu(self, chat_session, user_message, current_fault_node):
        Handle menu type nodes with state transition fixes
        print(f"[DEBUG] Node type: Menu")
        print(f"[DEBUG] Available options: {current_fault_node['options']}")
        print(f"[DEBUG] User selected: {user_message}")
        print(f"[DEBUG] Current state before transition: {chat_session.state}")

        if user_message in current_fault_node["options"]:
            next_node_key = current_fault_node["next"][user_message]
            print(f"[DEBUG] Transitioning to: {next_node_key}")
            
            # Update state before processing
            chat_session.state = next_node_key
            chat_session.save()

            next_node = self.nodes.get(next_node_key)
            if not next_node:
                print(f"[ERROR] Node {next_node_key} not found!")
                return Response({
                    "message": "System error. Please try again.",
                    "type": "error"
                }, status=500)

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
            "options": current_fault_node["options"]
        })

    def _handle_form_input(self, chat_session, user_message, current_node):
        Handle form input for fault reporting with robust validation
        print(f"\n[DEBUG] === Form Input Handler ===")
        print(f"[DEBUG] Current State: {chat_session.state}")
        print(f"[DEBUG] User Input: {user_message}")
        print(f"[DEBUG] Current Node: {current_node}")

        # Initialize temp_data if not exists
        if not hasattr(chat_session, 'temp_data'):
            chat_session.temp_data = {}
            print("[DEBUG] Initialized temp_data")

        # Validate current state
        valid_states = [
            "awaiting_district",
            "awaiting_town", 
            "awaiting_identifier",
            "awaiting_fault_type"
        ]
        
        if chat_session.state not in valid_states:
            error_msg = f"Invalid state '{chat_session.state}' for form input"
            print(f"[ERROR] {error_msg}")
            return Response({
                "message": "System error. Please start over.",
                "type": "error",
                "status": 500
            })

        # Add to chat history
        chat_session.chat_history.append({
            "user": user_message,
            "bot": "Processing your request..."
        })
        chat_session.save()

        try:
            # State machine for form processing
            if chat_session.state == "awaiting_district":
                print("[DEBUG] Processing district input")
                if not user_message.strip():
                    return Response({
                        "message": "District cannot be empty. Please try again.",
                        "type": "form",
                        "fields": ["district"]
                    })
                    
                chat_session.temp_data['district'] = user_message
                chat_session.state = "awaiting_town"
                chat_session.save()
                
                next_node = self.nodes["awaiting_town"]
                return Response({
                    "message": next_node["message"],
                    "type": next_node["type"],
                    "fields": ["town"]
                })

            elif chat_session.state == "awaiting_town":
                print("[DEBUG] Processing town input")
                if not user_message.strip():
                    return Response({
                        "message": "Town cannot be empty. Please try again.",
                        "type": "form", 
                        "fields": ["town"]
                    })
                    
                chat_session.temp_data['town'] = user_message
                chat_session.state = "awaiting_identifier"
                chat_session.save()
                
                next_node = self.nodes["awaiting_identifier"]
                return Response({
                    "message": next_node["message"],
                    "type": next_node["type"],
                    "fields": ["identifier"]
                })

            elif chat_session.state == "awaiting_identifier":
                print("[DEBUG] Processing identifier input")
                identifier = self.extract_identifier(user_message)
                if not identifier:
                    return Response({
                        "message": "Invalid format. Please enter a 10-digit account/contact number.",
                        "type": "form",
                        "fields": ["identifier"]
                    })
                    
                chat_session.temp_data['identifier'] = identifier
                chat_session.state = "awaiting_fault_type"
                chat_session.save()
                
                next_node = self.nodes["awaiting_fault_type"]
                return Response({
                    "message": next_node["message"],
                    "type": next_node["type"],
                    "options": next_node["options"]
                })

            elif chat_session.state == "awaiting_fault_type":
                print("[DEBUG] Processing fault type input")
                fault_type = self.extract_fault_type(user_message)
                if not fault_type:
                    return Response({
                        "message": "Invalid selection. Please choose from the options.",
                        "type": "menu",
                        "options": self.nodes["awaiting_fault_type"]["options"]
                    })
                    
                chat_session.temp_data['fault_type'] = fault_type
                chat_session.state = "confirm_details"
                chat_session.save()
                
                confirmation_msg = self._generate_confirmation_message(chat_session)
                return Response({
                    "message": confirmation_msg,
                    "type": "message"
                })

        except Exception as e:
            print(f"[CRITICAL] Form processing failed: {str(e)}", exc_info=True)
            return Response({
                "message": "A system error occurred. Please try again later.",
                "type": "error",
                "status": 500
            })

    def _process_district(self, chat_session, user_message):
        Process the district input
        print("[DEBUG] Processing district input")
        chat_session.temp_data['district'] = user_message
        chat_session.state = "awaiting_town"
        chat_session.save()

        next_message = self.nodes["awaiting_town"]["message"]
        chat_session.chat_history[-1]["bot"] = next_message
        chat_session.save()

        return Response({
            "message": next_message,
            "type": "form",
            "fields": ["town"]
        })

    def _process_town(self, chat_session, user_message):
        Process the town input
        print("[DEBUG] Processing town input")
        chat_session.temp_data['town'] = user_message
        chat_session.state = "awaiting_identifier"
        chat_session.save()

        next_message = self.nodes["awaiting_identifier"]["message"]
        chat_session.chat_history[-1]["bot"] = next_message
        chat_session.save()

        return Response({
            "message": next_message,
            "type": "form",
            "fields": ["identifier"]
        })

    def _process_identifier(self, chat_session, user_message):
        Process the identifier input (account number or contact number)
        print("[DEBUG] Processing identifier input")
        identifier = self.extract_identifier(user_message)
        if not identifier:
            return Response({
                "message": "Invalid identifier. Please provide a valid account number or contact number.",
                "type": "form",
                "fields": ["identifier"]
            })

        chat_session.temp_data['identifier'] = identifier
        chat_session.state = "awaiting_fault_type"
        chat_session.save()

        next_message = self.nodes["awaiting_fault_type"]["message"]
        chat_session.chat_history[-1]["bot"] = next_message
        chat_session.save()

        return Response({
            "message": next_message,
            "type": "menu",
            "options": self.nodes["awaiting_fault_type"]["options"]
        })

    def _process_fault_type(self, chat_session, user_message):
        Process the fault type input
        print("[DEBUG] Processing fault type input")
        fault_type = self.extract_fault_type(user_message)
        if not fault_type:
            return Response({
                "message": "Invalid fault type. Please select a valid option.",
                "type": "menu",
                "options": self.nodes["awaiting_fault_type"]["options"]
            })

        chat_session.temp_data['fault_type'] = fault_type
        chat_session.state = "confirm_details"
        chat_session.save()

        confirmation_message = self._generate_confirmation_message(chat_session)
        chat_session.chat_history[-1]["bot"] = confirmation_message
        chat_session.save()

        return Response({
            "message": confirmation_message,
            "type": "message"
        })

    def _generate_confirmation_message(self, chat_session):
        Generate a confirmation message for the fault report
        required_keys = ['district', 'town', 'identifier', 'fault_type']
        if not all(key in chat_session.temp_data for key in required_keys):
            return "Error: Missing details. Please restart the fault reporting process."

        return (
            f"Please confirm if these details are correct:\n"
            f"District: {chat_session.temp_data['district']}\n"
            f"Town: {chat_session.temp_data['town']}\n"
            f"Identifier: {chat_session.temp_data['identifier']}\n"
            f"Fault Type: {chat_session.temp_data['fault_type']}\n"
            f"Type 'yes' to confirm or 'no' to correct."
        )

    def _handle_error(self, chat_session, user_message):
        Handle errors during form input processing
        error_message = "An error occurred while processing your request. Please try again."
        chat_session.chat_history[-1]["bot"] = error_message
        chat_session.save()

        return Response({
            "message": error_message,
            "type": "menu",
            "options": self.nodes["fault_reporting"]["options"]
        })

    @staticmethod
    def extract_identifier(message):
        Extract an identifier (account number or contact number) from a message
        match = re.search(r'\b\d{10}\b', message)
        return match.group() if match else None

    @staticmethod
    def extract_fault_type(message):
        Extract fault type from a message
        fault_keywords = {
            "power failure": ["no power", "electricity out", "blackout"],
            "voltage issue": ["fluctuation", "dim lights", "voltage drop"],
            "broken line": ["fallen wire", "damaged line", "wire down"],
            "transformer problem": ["transformer", "explosion", "loud bang"],
            "electric shock": ["shock", "current leak", "earthing"]
        }

        for fault, keywords in fault_keywords.items():
            if any(keyword in message.lower() for keyword in keywords):
                return fault
        return None """


import json
from pathlib import Path
from rest_framework.response import Response
import re
from datetime import datetime
import random

class FaultReportingHandler:
    """Enhanced fault reporting handler with robust error handling"""

    _instance = None
    fault_reports = {}

    def __new__(cls):
        if cls._instance is None:
            print("[INFO] Creating new FaultReportingHandler instance")
            cls._instance = super(FaultReportingHandler, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = False
        if not self.initialized:
            print("[INFO] Initializing FaultReportingHandler")
            self.nodes = {}
            try:
                self._load_nodes()
                self.initialized = True
            except Exception as e:
                print(f"[CRITICAL] Initialization failed: {e}")
                self.initialized = False
        else:
            print("[DEBUG] Using existing FaultReportingHandler instance")

    def _load_nodes(self):
        """Load and validate conversation flow nodes"""
        print("[INFO] Loading node data")
        base_path = Path(__file__).parent.parent / "categories" / "fault_reporting"
        
        required_nodes = {
            "fault_reporting": {
                "type": "menu",
                "message": str,
                "options": list,
                "next": dict
            },
            "awaiting_district": {
                "type": "form",
                "message": str,
                "next": dict
            },
            "awaiting_town": {
                "type": "form", 
                "message": str,
                "next": dict
            },
            "awaiting_identifier": {
                "type": "form",
                "message": str,
                "next": dict
            },
            "awaiting_fault_type": {
                "type": "menu",
                "message": str,
                "options": list,
                "next": dict
            },
            "confirm_details": {
                "type": "message",
                "message": str,
                "next": dict
            },
            "exit": {
                "type": "message",
                "message": str,
                "next": dict
            }
        }

        try:
            # Load English nodes
            en_path = base_path / "en_fault_reporting.json"
            with open(en_path, encoding='utf-8') as f:
                data = json.load(f)
                self._validate_nodes(data, required_nodes)
                self.nodes.update(data)
                self.nodes["fault_reporting"] = data["fault_reporting"]
                print(f"[DEBUG] Loaded {len(data)} English nodes")

            # Load Sinhala nodes if available
            si_path = base_path / "si_fault_reporting.json"
            if si_path.exists():
                with open(si_path, encoding='utf-8') as f:
                    data = json.load(f)
                    self._validate_nodes(data, required_nodes)
                    self.nodes.update(data)
                    self.nodes["fault_reporting_si"] = data["fault_reporting_si"]
                    print(f"[DEBUG] Loaded {len(data)} Sinhala nodes")

            print(f"[INFO] Total nodes loaded: {len(self.nodes)}")
            
        except Exception as e:
            print(f"[CRITICAL] Node loading failed: {e}")
            raise

    def _validate_nodes(self, data, required_nodes):
        """Validate node structure and required fields"""
        for node_name, requirements in required_nodes.items():
            if node_name not in data:
                raise KeyError(f"Missing required node: {node_name}")
            
            node = data[node_name]
            for field, field_type in requirements.items():
                if field not in node:
                    raise KeyError(f"Missing field '{field}' in node '{node_name}'")
                
                if not isinstance(node[field], field_type):
                    raise TypeError(
                        f"Invalid type for {node_name}.{field}. "
                        f"Expected {field_type}, got {type(node[field])}"
                    )

    def handle_fault_report(self, chat_session, user_message, current_node):
        """Main request handler with comprehensive error handling"""
        print(f"\n[INFO] === New Request (Session: {getattr(chat_session, 'id', 'new')} ===")
        
        # Initialize session if needed
        chat_session.state = getattr(chat_session, 'state', 'fault_reporting')
        chat_session.temp_data = getattr(chat_session, 'temp_data', {})
        chat_session.chat_history = getattr(chat_session, 'chat_history', [])
        
        try:
            # Handle form states
            if chat_session.state in ["awaiting_district", "awaiting_town", 
                                    "awaiting_identifier", "awaiting_fault_type"]:
                return self._handle_form_input(chat_session, user_message)

            # Get appropriate node based on language
            base_node = "fault_reporting_si" if getattr(
                chat_session, 'selected_language', 'English') == "Sinhala" else "fault_reporting"
            current_node = self.nodes.get(chat_session.state, self.nodes[base_node])

            # Route based on node type
            if current_node["type"] == "menu":
                return self._handle_menu(chat_session, user_message, current_node)
            elif current_node["type"] == "form":
                return self._handle_form_input(chat_session, user_message)
            else:
                raise ValueError(f"Unknown node type: {current_node['type']}")

        except Exception as e:
            print(f"[ERROR] Handler failed: {type(e).__name__}: {str(e)}")
            return self._handle_error(chat_session)

    def _handle_menu(self, chat_session, user_message, current_node):
        """Handle menu selection with validation"""
        print(f"[DEBUG] Handling menu (state: {chat_session.state})")
        
        # Validate input
        if user_message not in current_node.get("options", []):
            return Response({
                "message": "Invalid option. Please select from the menu.",
                "type": "menu",
                "options": current_node["options"]
            })

        # Get next node key
        next_node_key = current_node["next"].get(user_message)
        if not next_node_key:
            print(f"[ERROR] No next node for option: {user_message}")
            return Response({
                "message": "Configuration error. Please try again.",
                "type": "error",
                "status": 500
            })

        # Verify next node exists
        if next_node_key not in self.nodes:
            print(f"[ERROR] Missing node: {next_node_key}")
            return Response({
                "message": "System error. Please contact support.",
                "type": "error",
                "status": 500
            })

        # Update session state
        chat_session.state = next_node_key
        chat_session.save()

        # Prepare response
        next_node = self.nodes[next_node_key]
        response_data = {
            "message": next_node["message"],
            "type": next_node["type"],
            "session_state": chat_session.state
        }

        # Add optional fields
        if "options" in next_node:
            response_data["options"] = next_node["options"]
        if "fields" in next_node:
            response_data["fields"] = next_node["fields"]

        # Update chat history
        chat_session.chat_history.append({
            "user": user_message,
            "bot": next_node["message"]
        })
        chat_session.save()

        return Response(response_data)

    def _handle_form_input(self, chat_session, user_message):
        """Process form input with validation"""
        print(f"[DEBUG] Processing form (state: {chat_session.state})")
        
        # Validate current state
        valid_states = ["awaiting_district", "awaiting_town", 
                       "awaiting_identifier", "awaiting_fault_type"]
        if chat_session.state not in valid_states:
            return Response({
                "message": "Invalid session state. Please start over.",
                "type": "error",
                "status": 400
            })

        # Update chat history
        chat_session.chat_history.append({
            "user": user_message,
            "bot": "Processing your input..."
        })
        chat_session.save()

        try:
            # Route to appropriate processor
            processor = {
                "awaiting_district": self._process_district,
                "awaiting_town": self._process_town,
                "awaiting_identifier": self._process_identifier,
                "awaiting_fault_type": self._process_fault_type
            }[chat_session.state]

            return processor(chat_session, user_message)

        except Exception as e:
            print(f"[ERROR] Form processing failed: {str(e)}")
            return self._handle_error(chat_session)

    def _process_district(self, chat_session, user_message):
        """Process district input"""
        district = self._extract_district(user_message)
        if not district:
            return Response({
                "message": "Please enter a valid district name.",
                "type": "form",
                "fields": ["district"]
            })

        chat_session.temp_data["district"] = district
        chat_session.state = "awaiting_town"
        chat_session.save()

        return self._prepare_response("awaiting_town")

    def _process_town(self, chat_session, user_message):
        """Process town input"""
        town = self._extract_town(user_message)
        if not town:
            return Response({
                "message": f"Please enter a town in {chat_session.temp_data.get('district', 'your district')}.",
                "type": "form",
                "fields": ["town"]
            }) 

        chat_session.temp_data["town"] = town
        chat_session.state = "awaiting_identifier"
        chat_session.save()

        return self._prepare_response("awaiting_identifier")

    def _process_identifier(self, chat_session, user_message):
        """Process account/contact number"""
        identifier = self._extract_identifier(user_message)
        if not identifier:
            return Response({
                "message": "Please enter a valid 10-digit account/contact number.",
                "type": "form",
                "fields": ["identifier"]
            })

        chat_session.temp_data["identifier"] = identifier
        chat_session.temp_data["identifier_type"] = "account" if identifier.isdigit() else "contact"
        chat_session.state = "awaiting_fault_type"
        chat_session.save()

        return self._prepare_response("awaiting_fault_type")

    def _process_fault_type(self, chat_session, user_message):
        """Process fault type selection"""
        fault_type = self._extract_fault_type(user_message)
        if not fault_type:
            return Response({
                "message": "Please select a valid fault type.",
                "type": "menu",
                "options": self.nodes["awaiting_fault_type"]["options"]
            })

        chat_session.temp_data["fault_type"] = fault_type
        chat_session.state = "confirm_details"
        chat_session.save()

        return Response({
            "message": self._generate_confirmation(chat_session),
            "type": "message"
        })

    def _prepare_response(self, node_key):
        """Prepare standardized response for a node"""
        node = self.nodes[node_key]
        response = {
            "message": node["message"],
            "type": node["type"],
            "session_state": node_key
        }
        
        if "options" in node:
            response["options"] = node["options"]
        if "fields" in node:
            response["fields"] = node["fields"]
            
        return Response(response)

    def _generate_confirmation(self, chat_session):
        """Generate confirmation message with collected data"""
        data = chat_session.temp_data
        required = ["district", "town", "identifier", "fault_type"]
        
        if any(key not in data for key in required):
            return "Error: Missing information. Please start over."

        return (
            f"Please confirm these details:\n"
            f"• District: {data['district']}\n"
            f"• Town: {data['town']}\n"
            f"• {data.get('identifier_type', 'ID')}: {data['identifier']}\n"
            f"• Fault Type: {data['fault_type']}\n\n"
            f"Reply 'yes' to confirm or 'no' to correct."
        )

    def _handle_error(self, chat_session):
        """Handle errors gracefully"""
        chat_session.state = "fault_reporting"
        chat_session.save()
        
        return Response({
            "message": random.choice([
                "We encountered an issue. Let's start over.",
                "Sorry about that. Let's try again.",
                "System error. Returning to main menu."
            ]),
            "type": "menu",
            "options": self.nodes["fault_reporting"]["options"]
        })

    # Utility methods
    @staticmethod
    def _extract_district(message):
        """Extract district from message"""
        districts = [
            "Colombo", "Gampaha", "Kalutara", "Kandy", "Matale",
            "Nuwara Eliya", "Galle", "Matara", "Hambantota"
        ]
        message = message.lower().strip()
        for district in districts:
            if district.lower() in message:
                return district
        return None

    @staticmethod
    def _extract_town(message):
        """Extract town from message"""
        towns = [
            "Colombo", "Dehiwala", "Moratuwa", "Kandy", "Galle",
            "Negombo", "Kurunegala", "Jaffna", "Anuradhapura"
        ]
        message = message.lower().strip()
        for town in towns:
            if town.lower() in message:
                return town
        return None

    @staticmethod
    def _extract_identifier(message):
        """Extract account/contact number"""
        # Account number (10 digits)
        account_match = re.search(r'\b\d{10}\b', message)
        if account_match:
            return account_match.group()
            
        # Phone number (local format)
        phone_match = re.search(r'(?:0|94)?[1-9]\d{8}', message.replace(" ", ""))
        return phone_match.group() if phone_match else None

    @staticmethod
    def _extract_fault_type(message):
        """Extract fault type from message"""
        fault_map = {
            "1": "power failure",
            "2": "voltage issue",
            "3": "broken line",
            "4": "transformer problem",
            "5": "electric shock",
            "power": "power failure",
            "outage": "power failure",
            "voltage": "voltage issue",
            "transformer": "transformer problem",
            "shock": "electric shock",
            "line": "broken line"
        }
        
        message = message.lower().strip()
        
        # Check for exact matches first
        if message in fault_map:
            return fault_map[message]
            
        # Check for partial matches
        for keyword, fault in fault_map.items():
            if len(keyword) > 1 and keyword in message:
                return fault
                
        return None

    def _generate_reference(self, identifier):
        """Generate report reference number"""
        timestamp = datetime.now().strftime('%y%m%d')
        return f"FR{timestamp}{identifier[-4:] if identifier else random.randint(1000,9999)}"