"""
Auth page module for Roomz.

Registers the auth component (dialog) with baseweb.
This component is embedded in the chat page.
"""

import logging
import os

from ... import server

logger = logging.getLogger(__name__)

# Register the Vue component for the UI
server.register_component("auth.js", os.path.dirname(__file__))  # type: ignore[no-untyped-call]
