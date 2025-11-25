"""Pytest configuration for NVIDIA Blog Agent tests.

This conftest ensures that the project root is in the Python path
so that nvidia_blog_agent imports work correctly.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

