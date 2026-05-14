"""
Chat page module for Roomz.

Registers the chat component and route with baseweb.
"""

import logging
import os

from ... import server

logger = logging.getLogger(__name__)

# Register the Vue component for the UI
server.register_component("chat.js", os.path.dirname(__file__))
server.register_app_route("/", endpoint="chat")
