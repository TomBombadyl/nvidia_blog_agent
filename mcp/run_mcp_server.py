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

# Find the directory containing this script (mcp/)
script_dir = Path(__file__).resolve().parent

# Find the project root (parent of mcp/)
project_root = script_dir.parent

# Change to the project root directory
os.chdir(project_root)

# Add project root to Python path (in case imports are needed)
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Now import and run the actual MCP server
if __name__ == "__main__":
    # Import using direct file path since mcp is not a package
    import importlib.util
    mcp_server_path = script_dir / "nvidia_blog_mcp_server.py"
    spec = importlib.util.spec_from_file_location("nvidia_blog_mcp_server", mcp_server_path)
    mcp_server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp_server)
    
    import asyncio
    asyncio.run(mcp_server.main())

