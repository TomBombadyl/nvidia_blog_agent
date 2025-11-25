#!/usr/bin/env python3
"""Wrapper script for nvidia_blog_mcp_server.py that finds the project root automatically.

This script:
1. Finds its own location (using __file__)
2. Determines the project root directory
3. Changes to that directory
4. Runs nvidia_blog_mcp_server.py

This ensures the MCP server always runs from the correct directory, regardless of
where Python is invoked from.
"""

import os
import sys
from pathlib import Path

# Find the directory containing this script
script_dir = Path(__file__).resolve().parent

# Change to the project root directory
os.chdir(script_dir)

# Add project root to Python path (in case imports are needed)
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Now import and run the actual MCP server
if __name__ == "__main__":
    # Import the main function from the MCP server
    from nvidia_blog_mcp_server import main
    import asyncio
    
    asyncio.run(main())

