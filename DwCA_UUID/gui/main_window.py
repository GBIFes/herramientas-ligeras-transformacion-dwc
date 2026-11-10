"""
main_window.py

Interfaz gráfica principal ajustable, con control de activación dinámico
para la Sección 4 según el modo de UUID seleccionado.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from pathlib import Path
import csv
import zipfile

from core.file_processor import process_single_file
from core.dwca_processor import process_dwca
from core.constants import (
    APP_TITLE,
    DEFAULT_WINDOW_WIDTH
)
from core.encoding_utils import detect_file_format


class MainWindow:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry(f"{DEFAULT_WINDOW_WIDTH}x950")
        self.root.resizable(True, True)

        # Variables de control
        self.input_type_var = tk.StringVar(value="dwca")  # "dwca" o "single"
        self.uuid_type_var = tk.StringVar(value="random") # "random" o "deterministic"
        
        self.input_path_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.output_name_var = tk.StringVar()

        # Variables para UUID Determinista directo
        self.selected_table_var = tk.StringVar(value="")
        self.prefix_var = tk.StringVar(value="")
        self.seed_var = tk.StringVar(value="1")
        
        self.col1_var = tk.StringVar(value="")
        self.col2_var = tk.StringVar(value="")
        self.col3_var = tk.StringVar(value="")

        self.tables_dict = {}
        self.available_tables = ["(Ninguna)"]
        self.available_columns = ["(Ninguna)"]

        self.create_widgets()

    def create_widgets(self):
        # Título
        title = tk.Label(
            self.root,
            text=APP_TITLE,
            font=("Arial", 15, "bold")
        )
        title.pack(pady=(10, 5))

        # --- INSTRUCCIONES DETALLADAS ---
        instructions = """
ℹ️ INFORMACIÓN Y FUNCIONAMIENTO:
• UUID Aleatorio (Agnóstico): Genera un código único e independiente para cada registro en cada ejecución.
• UUID Determinista: Une mediante guiones (-) los elementos de la Sección 4: [Prefijo]-[Semilla]-[Col1]-[Col2]-[Col3].
• Nomenclatura: Los campos originales conservan su nombre (con el nuevo UUID), los anteriores van con sufijo 'Old', 
  y se añade la columna 'UUID_textual' con la traza exacta. Los archivos originales NUNCA se modifican.
"""
        lbl_inst = tk.Label(
            self.root,
            text=instructions,
            justify="left",
            anchor="w",
            font=("Arial", 8),
            bg="#F5F5F5",
            relief="groove",
            padx=10,
            pady=5
        )
        lbl_inst.pack(padx=15, pady=5, fill="x")

        # --- SECCIÓN 1: ARCHIVOS Y RUTAS ---
        frame_paths = tk.LabelFrame(
            self.root,
            text=" 1. Archivo de Entrada y Destino ",
            font=("Arial", 9, "bold"),
            padx=10,
            pady=8
        )
        frame_paths.pack(padx=15, pady=5, fill="x")

        tk.Label(frame_paths, text="Archivo de entrada:", font=("Arial", 9)).grid(row=0, column=0, sticky="w", pady=2)
        self.entry_input = tk.Entry(frame_paths, textvariable=self.input_path_var, width=50, state="readonly")
        self.entry_input.grid(row=0, column=1, padx=5, pady=2)
        btn_browse_in = tk.Button(frame_paths, text="Explorar...", width=10, command=self.select_input_file)
        btn_browse_in.grid(row=0, column=2, padx=2, pady=2)

        tk.Label(frame_paths, text="Carpeta de salida:", font=("Arial", 9)).grid(row=1, column=0, sticky="w", pady=2)
        self.entry_outdir = tk.Entry(frame_paths, textvariable=self.output_dir_var, width=50)
        self.entry_outdir.grid(row=1, column=1, padx=5, pady=2)
        btn_browse_out = tk.Button(frame_paths, text="Cambiar...", width=10, command=self.select_output_dir)
        btn_browse_out.grid(row=1, column=2, padx=2, pady=2)

        tk.Label(frame_paths, text="Nombre archivo final:", font=("Arial", 9)).grid(row=2, column=0, sticky="w", pady=2)
        self.entry_outname = tk.Entry(frame_paths, textvariable=self.output_name_var, width=50)
        self.entry_outname.grid(row=2, column=1, padx=5, pady=2)

        # --- SECCIÓN 2: TIPO DE ENTRADA ---
        frame_input_type = tk.LabelFrame(
            self.root,
            text=" 2. Formato de los Datos ",
            font=("Arial", 9, "bold"),
            padx=10,
            pady=5
        )
        frame_input_type.pack(padx=15, pady=5, fill="x")

        tk.Radiobutton(
            frame_input_type,
            text="Darwin Core Archive (ZIP - Soporta con o sin meta.xml / eml.xml)",
            variable=self.input_type_var,
            value="dwca",
            font=("Arial", 9),
            command=self.on_input_type_changed
        ).pack(anchor="w", pady=2)

        tk.Radiobutton(
            frame_input_type,
            text="Archivo individual plano (CSV, TSV, TXT)",
            variable=self.input_type_var,
            value="single",
            font=("Arial", 9),
            command=self.on_input_type_changed
        ).pack(anchor="w", pady=2)

        # --- SECCIÓN 3: TIPO DE UUID ---
        frame_uuid = tk.LabelFrame(
            self.root,
            text=" 3. Modo de Generación de UUID ",
            font=("Arial", 9, "bold"),
            padx=10,
            pady=5
        )
        frame_uuid.pack(padx=15, pady=5, fill="x")

        tk.Radiobutton(
            frame_uuid,
            text="UUIDs Aleatorios (Agnósticos)",
            variable=self.uuid_type_var,
            value="random",
            font=("Arial", 9),
            command=self.toggle_deterministic_section
        ).pack(anchor="w", pady=2)

        tk.Radiobutton(
            frame_uuid,
            text="UUIDs Deterministas (Usa la configuración de la Sección 4)",
            variable=self.uuid_type_var,
            value="deterministic",
            font=("Arial", 9),
            command=self.toggle_deterministic_section
        ).pack(anchor="w", pady=2)

        # --- SECCIÓN 4: PARÁMETROS DETERMINISTAS Y SELECCIÓN DE TABLA ---
        self.frame_det = tk.LabelFrame(
            self.root,
            text=" 4. Configuración Determinista (Tabla, Prefijo, Semilla y Columnas) ",
            font=("Arial", 9, "bold"),
            padx=10,
            pady=8
        )
        self.frame_det.pack(padx=15, pady=5, fill="x")

        # Guardamos referencias a los widgets interactivos de la sección 4 para poder habilitar/deshabilitar
        self.lbl_table = tk.Label(self.frame_det, text="Seleccionar tabla (DwC-A):", font=("Arial", 9))
        self.combo_table = ttk.Combobox(self.frame_det, textvariable=self.selected_table_var, values=self.available_tables, width=35, state="readonly")
        self.combo_table.bind("<<ComboboxSelected>>", self.on_table_selected)

        self.lbl_table.grid(row=0, column=0, sticky="w", pady=3)
        self.combo_table.grid(row=0, column=1, sticky="w", padx=5, pady=3)

        self.lbl_prefix = tk.Label(self.frame_det, text="Prefijo manual:", font=("Arial", 9))
        self.entry_prefix = tk.Entry(self.frame_det, textvariable=self.prefix_var, width=25)
        self.lbl_prefix.grid(row=1, column=0, sticky="w", pady=3)
        self.entry_prefix.grid(row=1, column=1, sticky="w", padx=5, pady=3)

        self.lbl_seed = tk.Label(self.frame_det, text="Semilla numérica:", font=("Arial", 9))
        self.entry_seed = tk.Entry(self.frame_det, textvariable=self.seed_var, width=25)
        self.lbl_seed.grid(row=2, column=0, sticky="w", pady=3)
        self.entry_seed.grid(row=2, column=1, sticky="w", padx=5, pady=3)

        self.lbl_col1 = tk.Label(self.frame_det, text="Columna 1:", font=("Arial", 9))
        self.combo_col1 = ttk.Combobox(self.frame_det, textvariable=self.col1_var, values=self.available_columns, width=35, state="readonly")
        self.lbl_col1.grid(row=3, column=0, sticky="w", pady=3)
        self.combo_col1.grid(row=3, column=1, sticky="w", padx=5, pady=3)

        self.lbl_col2 = tk.Label(self.frame_det, text="Columna 2:", font=("Arial", 9))
        self.combo_col2 = ttk.Combobox(self.frame_det, textvariable=self.col2_var, values=self.available_columns, width=35, state="readonly")
        self.lbl_col2.grid(row=4, column=0, sticky="w", pady=3)
        self.combo_col2.grid(row=4, column=1, sticky="w", padx=5, pady=3)

        self.lbl_col3 = tk.Label(self.frame_det, text="Columna 3:", font=("Arial", 9))
        self.combo_col3 = ttk.Combobox(self.frame_det, textvariable=self.col3_var, values=self.available_columns, width=35, state="readonly")
        self.lbl_col3.grid(row=5, column=0, sticky="w", pady=3)
        self.combo_col3.grid(row=5, column=1, sticky="w", padx=5, pady=3)

        # --- BOTONES FINALES ---
        frame_action = tk.Frame(self.root)
        frame_action.pack(pady=10)

        btn_execute = tk.Button(
            frame_action,
            text="Ejecutar Transformación",
            width=30,
            height=2,
            font=("Arial", 10, "bold"),
            bg="#2E7D32",
            fg="white",
            command=self.execute_process
        )
        btn_execute.pack(side="left", padx=10)

        btn_exit = tk.Button(
            frame_action,
            text="Salir",
            width=15,
            height=2,
            command=self.root.destroy
        )
        btn_exit.pack(side="right", padx=10)

        self.update_table_visibility()
        self.toggle_deterministic_section()  # Estado inicial según el radio button por defecto

    def toggle_deterministic_section(self):
        is_deterministic = (self.uuid_type_var.get() == "deterministic")
        state = "normal" if is_deterministic else "disabled"

        # Habilitar o deshabilitar elementos interactivos de la sección 4
        self.combo_table.config(state="readonly" if is_deterministic else "disabled")
        self.entry_prefix.config(state=state)
        self.entry_seed.config(state=state)
        self.combo_col1.config(state="readonly" if is_deterministic else "disabled")
        self.combo_col2.config(state="readonly" if is_deterministic else "disabled")
        self.combo_col3.config(state="readonly" if is_deterministic else "disabled")

    def on_input_type_changed(self):
        self.update_table_visibility()
        if self.input_path_var.get():
            self.load_structure_from_input(self.input_path_var.get())

    def update_table_visibility(self):
        is_dwca = (self.input_type_var.get() == "dwca")
        if is_dwca:
            self.lbl_table.grid()
            self.combo_table.grid()
        else:
            self.lbl_table.grid_remove()
            self.combo_table.grid_remove()

    def select_input_file(self):
        filetypes = [("Darwin Core Archive", "*.zip"), ("Archivos delimitados", "*.csv *.tsv *.txt"), ("Todos los archivos", "*.*")]
        
        file_path = filedialog.askopenfilename(title="Seleccionar archivo de entrada", filetypes=filetypes)
        if not file_path:
            return

        self.input_path_var.set(file_path)
        
        path_obj = Path(file_path)
        self.output_dir_var.set(str(path_obj.parent))
        
        suggested_name = f"{path_obj.stem}_UUID{path_obj.suffix}"
        self.output_name_var.set(suggested_name)

        self.load_structure_from_input(file_path)

    def load_structure_from_input(self, file_path):
        self.tables_dict = {}
        input_type = self.input_type_var.get()

        try:
            path_obj = Path(file_path)
            if input_type == "dwca" and path_obj.suffix.lower() == ".zip":
                with zipfile.ZipFile(file_path, 'r') as z:
                    file_list = z.namelist()
                    tabulars = [f for f in file_list if f.lower().endswith(('.csv', '.tsv', '.txt'))]
                    for tab in tabulars:
                        with z.open(tab) as f:
                            first_line = f.readline().decode('utf-8', errors='ignore').strip()
                            delim = '\t' if '\t' in first_line else ','
                            header = [h.strip() for h in first_line.split(delim)]
                            self.tables_dict[tab] = header

                table_names = list(self.tables_dict.keys())
                self.available_tables = table_names if table_names else ["(Ninguna)"]
                self.combo_table['values'] = self.available_tables
                if self.available_tables:
                    self.combo_table.current(0)
                    self.on_table_selected(None)
            else:
                encoding, delimiter = detect_file_format(file_path)
                with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    header = next(reader)
                    cols = [h.strip() for h in header]
                
                table_name = path_obj.name
                self.tables_dict[table_name] = cols
                self.available_tables = [table_name]
                self.combo_table['values'] = self.available_tables
                self.combo_table.set(table_name)
                self.update_columns_for_table(table_name)

        except Exception:
            pass

    def on_table_selected(self, event):
        selected = self.selected_table_var.get()
        if not selected and self.available_tables:
            selected = self.available_tables[0]
            self.selected_table_var.set(selected)
        
        self.update_columns_for_table(selected)

    def update_columns_for_table(self, table_name):
        cols = ["(Ninguna)"]
        if table_name in self.tables_dict:
            cols.extend(self.tables_dict[table_name])

        self.available_columns = cols
        self.combo_col1['values'] = self.available_columns
        self.combo_col2['values'] = self.available_columns
        self.combo_col3['values'] = self.available_columns

        self.col1_var.set("(Ninguna)")
        self.col2_var.set("(Ninguna)")
        self.col3_var.set("(Ninguna)")

    def select_output_dir(self):
        dir_path = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if dir_path:
            self.output_dir_var.set(dir_path)

    def execute_process(self):
        input_file = self.input_path_var.get()
        out_dir = self.output_dir_var.get()
        out_name = self.output_name_var.get()

        if not input_file or not Path(input_file).exists():
            messagebox.showerror("Error", "Por favor, selecciona un archivo de entrada válido.")
            return

        if not out_dir or not out_name:
            messagebox.showerror("Error", "Debes especificar la carpeta y el nombre del archivo de salida.")
            return

        input_type = self.input_type_var.get()
        uuid_type = self.uuid_type_var.get()
        is_deterministic = (uuid_type == "deterministic")

        det_params = {
            "target_table": self.selected_table_var.get().strip(),
            "prefix": self.prefix_var.get().strip(),
            "seed": self.seed_var.get().strip(),
            "cols": [
                self.col1_var.get().strip(),
                self.col2_var.get().strip(),
                self.col3_var.get().strip()
            ]
        }
        det_params["cols"] = [c for c in det_params["cols"] if c and c != "(Ninguna)"]

        try:
            custom_output_path = str(Path(out_dir) / out_name)

            if input_type == "dwca":
                result = process_dwca(
                    input_file,
                    deterministic=is_deterministic,
                    det_params=det_params,
                    custom_output_path=custom_output_path
                )

                if result is None:
                    return

                messagebox.showinfo(
                    "Proceso Completado",
                    f"Transformación DwC-A Finalizada:\n\n"
                    f"Registros Core: {result.records_core}\n"
                    f"Registros Extensiones: {result.records_extensions}\n\n"
                    f"Guardado en:\n{result.output_zip}"
                )

            else:
                output_file = process_single_file(
                    input_file,
                    deterministic=is_deterministic,
                    det_params=det_params,
                    custom_output_path=custom_output_path
                )

                messagebox.showinfo(
                    "Completado",
                    f"Archivo individual generado:\n\n{output_file}"
                )

        except Exception as ex:
            messagebox.showerror("Error durante el proceso", str(ex))

    def run(self):
        self.root.mainloop()