import sys
import os

# Add api directory to sys.path
api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api"))
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)
