# main.py

import sys
from PyQt5.QtWidgets import QApplication
from modbusx.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(750, 500)
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()