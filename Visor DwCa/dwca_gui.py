import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from dwca_reader import DwcaReader
from dwca_model import DwcaModel
from dwca_editor import DwcaEditor

class WelcomeWindow(tk.Frame):
    def __init__(self, master, callback):
        super().__init__(master)
        self.callback = callback
        self.pack(fill="both", expand=True)

        self.label = tk.Label(self, text="GBIF.ES - Visor DwC-A", font=("Segoe UI", 18))
        self.label.pack(pady=20)

        self.button = tk.Button(self, text="Seleccionar DwC-A (ZIP)", command=self.select_zip)
        self.button.pack(pady=10)

    def select_zip(self):
        path = filedialog.askopenfilename(
            title="Seleccionar DwC-A (ZIP)",
            filetypes=[("DwC-A ZIP", "*.zip"), ("Todos los archivos", "*.*")]
        )
        if path:
            self.callback(path)

class DwcaViewer(tk.Frame):
    def __init__(self, master, model):
        super().__init__(master)
        self.model = model
        self.editor = DwcaEditor(model)
        self.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(self, columns=self.model.core_fields, show="headings")
        for f in self.model.core_fields:
            self.tree.heading(f, text=f)
            self.tree.column(f, width=150)
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="left", fill="y")

        for idx in self.model.get_indices():
            row = self.model.get_record(idx)
            values = [row[i] if i < len(row) else "" for i in range(len(self.model.core_fields))]
            self.tree.insert("", "end", iid=str(idx), values=values)

        right = tk.Frame(self)
        right.pack(side="right", fill="y")

        self.export_button = tk.Button(right, text="Exportar registro a JSON", command=self.export_selected)
        self.export_button.pack(pady=10)

    def export_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecciona un registro.")
            return
        idx = int(sel[0])
        path = filedialog.asksaveasfilename(
            title="Guardar JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        self.editor.export_record(idx, path)
        messagebox.showinfo("OK", "Registro exportado.")
