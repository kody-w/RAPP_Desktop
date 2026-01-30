"""RAPP OS Bridges - External system integrations."""

import sys

# Platform-specific imports
if sys.platform == "darwin":
    try:
        from .imessage_bridge import iMessageBridge, create_imessage_context
    except ImportError:
        iMessageBridge = None
        create_imessage_context = None

# Cross-platform
try:
    from .whatsapp_bridge import WhatsAppBridge, create_whatsapp_context
except ImportError:
    WhatsAppBridge = None
    create_whatsapp_context = None

__all__ = [
    "iMessageBridge",
    "create_imessage_context",
    "WhatsAppBridge",
    "create_whatsapp_context",
]
