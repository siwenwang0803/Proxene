#!/usr/bin/env python
"""Run the Proxene dashboard"""

import subprocess
import sys
import os

def main():
    # Get the dashboard directory
    dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dashboard')
    dashboard_app = os.path.join(dashboard_dir, 'app.py')
    
    if not os.path.exists(dashboard_app):
        print("❌ Dashboard app not found!")
        sys.exit(1)
    
    print("🚀 Starting Proxene Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:8501")
    print("🛑 Press Ctrl+C to stop")
    
    try:
        subprocess.run([
            sys.executable, '-m', 'streamlit', 'run', 
            dashboard_app,
            '--server.port', '8501',
            '--server.address', '0.0.0.0',
            '--theme.base', 'dark'
        ], cwd=dashboard_dir)
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped")
    except Exception as e:
        print(f"❌ Failed to start dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()