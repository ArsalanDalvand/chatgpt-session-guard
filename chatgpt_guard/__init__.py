"""ChatGPT Session Guard

Automated, browserless session monitoring and unauthorized device eviction for ChatGPT.
"""

from .client import ChatGPTClient
from .guard import ChatGPTGuard

__version__ = "1.0.0"
__all__ = ["ChatGPTClient", "ChatGPTGuard"]
