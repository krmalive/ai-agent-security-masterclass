#!/bin/bash

# Startup script for MCP Tool Allowlisting Demo App

echo "🚀 Starting MCP Tool Allowlisting Demo App..."
echo ""
echo "Server will be available at:"
echo "  - Insecure Route: http://localhost:8443/"
echo "  - Secure Route:   http://localhost:8443/secure"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uv run python main.py

