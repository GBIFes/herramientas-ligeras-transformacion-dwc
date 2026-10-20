"""
Generador de UUID para Darwin Core Archive

Punto de entrada de la aplicación.
"""

from gui.main_window import MainWindow


def main():
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()