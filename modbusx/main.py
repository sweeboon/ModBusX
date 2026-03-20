#!/usr/bin/env python3
"""
ModBusX Application Entry Point

Main entry point for the ModBusX ModBus register management application.
Uses SOA (Service-Oriented Architecture) with managers coordinating services.
"""

import sys
import os

# Ensure the project root is in the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modbusx.application import main as modbusx_main

def main():
    """Main entry point for the application."""
    return modbusx_main(sys.argv)

if __name__ == "__main__":
    sys.exit(main())