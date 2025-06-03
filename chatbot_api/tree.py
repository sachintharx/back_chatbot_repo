# # tree.py
# import json
# from typing import Optional, Dict, Any

# class Tree:
#     def __init__(self, tree_file: str):
#         with open(tree_file, "r") as f:
#             self.tree = json.load(f)

#     def get_node(self, node_key: str) -> Optional[Dict[str, Any]]:
#         """Get node information from the tree."""
#         return self.tree.get(node_key)

#     def get_next_node(self, current_node_key: str, user_input: str) -> Optional[str]:
#         """Get the next node key based on current node and user input."""
#         current_node = self.get_node(current_node_key)
#         if not current_node or "next" not in current_node:
#             return None
#         return current_node["next"].get(user_input)

#     def is_valid_option(self, node_key: str, user_input: str) -> bool:
#         """Check if user input is valid for the current node."""
#         node = self.get_node(node_key)
#         return bool(node and "options" in node and user_input in node["options"])


import json

class Tree:
    def __init__(self, tree_file):
        with open(tree_file, "r") as f:
            self.tree = json.load(f)

    def get_node(self, node_key):
        return self.tree.get(node_key)

    def get_next_node(self, current_node_key, user_input):
        current_node = self.get_node(current_node_key)
        if not current_node or current_node["type"] != "menu":
            return None
        next_node_key = current_node["next"].get(user_input)
        return next_node_key
