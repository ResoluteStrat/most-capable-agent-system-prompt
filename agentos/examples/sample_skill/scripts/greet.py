#!/usr/bin/env python3
"""Bundled skill script. Stdlib only. Prints a greeting; AgentOS captures stdout."""
import sys

name = sys.argv[1] if len(sys.argv) > 1 else "world"
print(f"hello, {name} — from hello-skill")
