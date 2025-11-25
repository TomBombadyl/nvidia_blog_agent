"""Test MCP configuration and validate the setup."""
import json
import os
import sys
from pathlib import Path

def test_mcp_config():
    """Validate .cursor/mcp.json configuration."""
    print("=" * 60)
    print("MCP CONFIGURATION TEST")
    print("=" * 60)
    
    # Check 1: Config file exists
    config_path = Path(".cursor/mcp.json")
    if not config_path.exists():
        print(f"[ERROR] {config_path} not found")
        return False
    
    print(f"[OK] Config file exists: {config_path}")
    
    # Check 2: Valid JSON
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}")
        return False
    
    print("[OK] Valid JSON format")
    
    # Check 3: Required structure
    if "mcpServers" not in config:
        print("[ERROR] Missing 'mcpServers' key")
        return False
    
    print("[OK] Has 'mcpServers' key")
    
    # Check 4: Server entry exists
    if "nvidia-blog-agent" not in config["mcpServers"]:
        print("[ERROR] Missing 'nvidia-blog-agent' server entry")
        return False
    
    server_config = config["mcpServers"]["nvidia-blog-agent"]
    print("[OK] Server entry 'nvidia-blog-agent' found")
    
    # Check 5: Command
    if "command" not in server_config:
        print("[ERROR] Missing 'command' field")
        return False
    
    if server_config["command"] != "python":
        print(f"[WARN] Command is '{server_config['command']}', expected 'python'")
    else:
        print("[OK] Command: python")
    
    # Check 6: Args
    if "args" not in server_config:
        print("[ERROR] Missing 'args' field")
        return False
    
    if server_config["args"] != ["nvidia_blog_mcp_server.py"]:
        print(f"[WARN] Args are {server_config['args']}, expected ['nvidia_blog_mcp_server.py']")
    else:
        print("[OK] Args: ['nvidia_blog_mcp_server.py']")
    
    # Check 7: Env vars
    if "env" not in server_config:
        print("[WARN] Missing 'env' field (environment variables)")
    else:
        env = server_config["env"]
        print("[OK] Environment variables configured:")
        
        if "NVIDIA_BLOG_SERVICE_URL" in env:
            url = env["NVIDIA_BLOG_SERVICE_URL"]
            if "..." in url or "YOUR" in url.upper():
                print(f"  - NVIDIA_BLOG_SERVICE_URL: {url} [NEEDS UPDATE]")
            else:
                print(f"  - NVIDIA_BLOG_SERVICE_URL: {url} [OK]")
        else:
            print("  - NVIDIA_BLOG_SERVICE_URL: [MISSING]")
        
        if "INGEST_API_KEY" in env:
            key = env["INGEST_API_KEY"]
            if "YOUR" in key.upper() or "HERE" in key.upper():
                print(f"  - INGEST_API_KEY: [NEEDS UPDATE]")
            else:
                print(f"  - INGEST_API_KEY: [SET]")
        else:
            print("  - INGEST_API_KEY: [OPTIONAL - not set]")
    
    # Check 8: Server file exists
    server_file = Path("nvidia_blog_mcp_server.py")
    if not server_file.exists():
        print(f"[ERROR] Server file not found: {server_file}")
        return False
    
    print(f"[OK] Server file exists: {server_file}")
    
    # Check 9: Python can be found
    import shutil
    python_cmd = shutil.which("python")
    if python_cmd:
        print(f"[OK] Python found: {python_cmd}")
    else:
        print("[WARN] Python command not found in PATH")
    
    print("\n" + "=" * 60)
    print("CONFIGURATION TEST COMPLETE")
    print("=" * 60)
    
    return True

def test_smoke_payload():
    """Validate smoke test payload."""
    print("\n" + "=" * 60)
    print("SMOKE TEST PAYLOAD VALIDATION")
    print("=" * 60)
    
    payload_path = Path("smoke_test_payload.json")
    if not payload_path.exists():
        print(f"[WARN] {payload_path} not found")
        return False
    
    try:
        with open(payload_path, 'r') as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}")
        return False
    
    print(f"[OK] Payload file exists: {payload_path}")
    print("[OK] Valid JSON format")
    
    # Validate structure
    if "question" not in payload:
        print("[ERROR] Missing 'question' field")
        return False
    
    if not isinstance(payload["question"], str) or not payload["question"].strip():
        print("[ERROR] 'question' must be a non-empty string")
        return False
    
    print(f"[OK] Question: '{payload['question'][:50]}...'")
    
    if "top_k" in payload:
        if not isinstance(payload["top_k"], int) or payload["top_k"] < 1 or payload["top_k"] > 20:
            print(f"[WARN] top_k should be integer 1-20, got: {payload['top_k']}")
        else:
            print(f"[OK] top_k: {payload['top_k']}")
    else:
        print("[OK] top_k: [optional, will use default 8]")
    
    print("\n" + "=" * 60)
    print("PAYLOAD VALIDATION COMPLETE")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    config_ok = test_mcp_config()
    payload_ok = test_smoke_payload()
    
    if config_ok and payload_ok:
        print("\n[OK] All tests passed!")
        sys.exit(0)
    else:
        print("\n[ERROR] Some tests failed")
        sys.exit(1)

