"""Main entry point for Proxene"""

import logging
from proxene.core.proxy import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Export the FastAPI app
__all__ = ["app"]