import tkinter as tk
from dwca_welcome import WelcomeFrame
from dwca_viewer import ViewerFrame
from dwca_eml_viewer import EMLViewer


def main():
    root = tk.Tk()
    root.title("Visor DwC-A GBIF.ES")
    root.geometry("1200x800")

    # Crear visor principal DwC-A
    viewer = ViewerFrame(root)

    # Crear pantalla de bienvenida
    welcome = WelcomeFrame(root, viewer)

    # Conectar visor EML
    welcome.set_eml_viewer_class(EMLViewer)

    # Conectar viewer con welcome
    viewer.set_welcome(welcome)

    # Mostrar bienvenida
    welcome.pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()
