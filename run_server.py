"""
RailBlock AI - Single-Command Launcher
Runs the Railway Block Planning & Optimization Web Control Center.
"""

import sys
import os
import webbrowser

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    print("=" * 75)
    print("  RAILBLOCK AI: INTEGRATED AUTOMATIC BLOCK PLANNING & OPTIMIZATION SYSTEM")
    print("=" * 75)
    print(f"  Corridor: Delhi - Aligarh - Tundla (150 KM Trunk HDN Line)")
    print(f"  Departments: TMS (Engineering) | SMMS (Signalling) | TDMS (TRD/OHE)")
    print(f"  Operations: COA Timetable & Goods Freight Forecast Integration")
    print(f"  Server starting at: http://{host}:{port}")
    print("=" * 75)
    
    app.run(host=host, port=port, debug=False)
