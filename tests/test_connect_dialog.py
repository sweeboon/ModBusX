#!/usr/bin/env python3
"""
Test the ModBusX connect dialog COM port functionality.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt5.QtWidgets import QApplication
from modbusx.ui.connect_dialog import ConnectDialog

def test_dialog():
    """Test the connect dialog."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    print("Testing ModBusX Connect Dialog")
    print("=" * 40)
    
    # Create dialog
    dialog = ConnectDialog()
    
    print(f"Dialog created successfully")
    print(f"COM port dropdown has {dialog.com_port_combo.count()} items")
    
    # Show some sample entries
    print("\nFirst 10 COM port entries:")
    for i in range(min(10, dialog.com_port_combo.count())):
        text = dialog.com_port_combo.itemText(i)
        data = dialog.com_port_combo.itemData(i)
        
        if "Not Connected" not in text:
            print(f"  {i:3}: {text} → {data} [ACTIVE]")
        elif i < 5:  # Only show first few inactive
            print(f"  {i:3}: {text} → {data}")
    
    # Test protocol switching
    print(f"\nTesting protocol switching...")
    print(f"Current protocol: {dialog.protocol_combo.currentText()}")
    
    # Switch to Serial Port
    dialog.protocol_combo.setCurrentText("Serial Port")
    print(f"Switched to: {dialog.protocol_combo.currentText()}")
    
    # Test getting selected COM port
    selected_port = dialog._get_selected_com_port()
    print(f"Currently selected COM port: {selected_port}")
    
    app.quit()
    print("\nTest completed successfully!")

if __name__ == "__main__":
    test_dialog()