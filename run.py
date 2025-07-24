#!/usr/bin/env python
"""Run the Proxene proxy server"""

import uvicorn
from proxene.main import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )