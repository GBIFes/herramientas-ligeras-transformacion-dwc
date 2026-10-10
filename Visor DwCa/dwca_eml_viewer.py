import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import xml.etree.ElementTree as ET
import xml.dom.minidom


class EMLViewer(tk.Toplevel):
    """
    Ventana independiente que contiene el editor XML universal.
    Adaptación del módulo EditarXML.py para integrarlo en el sistema DwC-A.
    """

    def __init__(self, root, eml_path):
        super().__init__(root)
        self.title("Metadata EML")
        self.geometry("1200x800")

        # Editor integrado como Frame
        self.editor = XMLTreeEditor(self)
        self.editor.pack(fill="both", expand=True)

        # Abrir automáticamente el EML
        self.editor.open_xml(eml_path)


class XMLTreeEditor(tk.Frame):
    """
    Versión adaptada del editor XML universal.
    Antes: class XMLTreeEditor(tk.Tk)
    Ahora: class XMLTreeEditor(tk.Frame)
    """

    def __init__(self, master):
        super().__init__(master)

        self.tree_xml = None
        self.root_xml = None
        self.current_node = None
        self.current_path = None

        self.node_map = {}
        self.search_results = []
        self.search_index = -1

        self.create_menu(master)
        self.create_layout()
        self.create_styles()

    # -------------------------------
    # MENÚ
    # -------------------------------
    def create_menu(self, master):
        menubar = tk.Menu(master)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Abrir...", command=self.open_xml)
        filemenu.add_command(label="Guardar (pretty)", command=self.save_xml_pretty)
        filemenu.add_command(label="Guardar como (pretty)...", command=self.save_as_xml_pretty)
        filemenu.add_separator()
        filemenu.add_command(label="Cerrar metadata", command=master.destroy)
        menubar.add_cascade(label="Archivo", menu=filemenu)

        toolsmenu = tk.Menu(menubar, tearoff=0)
        toolsmenu.add_command(label="Buscar nodo...", command=self.search_node_dialog)
        toolsmenu.add_command(label="Buscar / Reemplazar texto...", command=self.search_replace_dialog)
        toolsmenu.add_separator()
        toolsmenu.add_command(label="Expandir todo", command=self.expand_all)
        toolsmenu.add_command(label="Colapsar todo", command=self.collapse_all)
        menubar.add_cascade(label="Herramientas", menu=toolsmenu)

        master.config(menu=menubar)

    # -------------------------------
    # ESTILOS
    # -------------------------------
    def create_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        colors = {
            "level0": "#e0e0e0",
            "level1": "#d0e8ff",
            "level2": "#d8ffd0",
            "level3": "#fff5c2",
            "level4": "#ffd6e8",
            "level5": "#f0d0ff",
        }
        for level, color in colors.items():
            style.configure(level, background=color)
    # -------------------------------
    # LAYOUT
    # -------------------------------
    def create_layout(self):
        main = tk.Frame(self)
        main.pack(fill="both", expand=True)

        # Panel izquierdo (árbol)
        left = tk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        tree_frame = tk.Frame(left)
        tree_frame.pack(fill="both", expand=True)

        tree_scroll_y = tk.Scrollbar(tree_frame, orient="vertical")
        tree_scroll_y.pack(side="right", fill="y")

        tree_scroll_x = tk.Scrollbar(left, orient="horizontal")
        tree_scroll_x.pack(side="bottom", fill="x")

        self.treeview = ttk.Treeview(tree_frame)
        self.treeview.pack(side="left", fill="both", expand=True)

        self.treeview.configure(
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )
        tree_scroll_y.config(command=self.treeview.yview)
        tree_scroll_x.config(command=self.treeview.xview)

        self.treeview.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Botones mover nodo
        btn_frame = tk.Frame(left)
        btn_frame.pack(fill="x")
        tk.Button(btn_frame, text="Subir nodo", command=self.move_node_up).pack(side="left", padx=2, pady=2)
        tk.Button(btn_frame, text="Bajar nodo", command=self.move_node_down).pack(side="left", padx=2, pady=2)

        # Panel derecho (edición)
        right = tk.Frame(main)
        right.pack(side="right", fill="both", expand=True)

        tk.Label(right, text="Etiqueta (tag):").pack(anchor="w")
        self.entry_tag = tk.Entry(right)
        self.entry_tag.pack(fill="x")

        tk.Label(right, text="Texto (text):").pack(anchor="w")

        text_frame = tk.Frame(right)
        text_frame.pack(fill="both", expand=True)

        text_scroll_y = tk.Scrollbar(text_frame, orient="vertical")
        text_scroll_y.pack(side="right", fill="y")

        text_scroll_x = tk.Scrollbar(right, orient="horizontal")
        text_scroll_x.pack(fill="x")

        self.text_content = tk.Text(text_frame, height=10, wrap="none")
        self.text_content.pack(side="left", fill="both", expand=True)

        self.text_content.configure(
            yscrollcommand=text_scroll_y.set,
            xscrollcommand=text_scroll_x.set
        )
        text_scroll_y.config(command=self.text_content.yview)
        text_scroll_x.config(command=self.text_content.xview)

        tk.Label(right, text="Atributos (key=value por línea):").pack(anchor="w")

        attrs_frame = tk.Frame(right)
        attrs_frame.pack(fill="both", expand=True)

        attrs_scroll_y = tk.Scrollbar(attrs_frame, orient="vertical")
        attrs_scroll_y.pack(side="right", fill="y")

        attrs_scroll_x = tk.Scrollbar(right, orient="horizontal")
        attrs_scroll_x.pack(fill="x")

        self.text_attrs = tk.Text(attrs_frame, height=6, wrap="none")
        self.text_attrs.pack(side="left", fill="both", expand=True)

        self.text_attrs.configure(
            yscrollcommand=attrs_scroll_y.set,
            xscrollcommand=attrs_scroll_x.set
        )
        attrs_scroll_y.config(command=self.text_attrs.yview)
        attrs_scroll_x.config(command=self.text_attrs.xview)

        btns = tk.Frame(right)
        btns.pack(fill="x", pady=5)
        tk.Button(btns, text="Aplicar cambios", command=self.apply_changes).pack(side="left", padx=2)
        tk.Button(btns, text="Añadir hijo...", command=self.add_child_dialog).pack(side="left", padx=2)
        tk.Button(btns, text="Eliminar nodo", command=self.delete_node).pack(side="left", padx=2)
    # -------------------------------
    # ABRIR XML
    # -------------------------------
    def open_xml(self, path=None):
        if not path:
            path = filedialog.askopenfilename(filetypes=[("XML files", "*.xml"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.tree_xml = ET.parse(path)
        except Exception as e:
            messagebox.showerror("Error al abrir XML", str(e))
            return
        self.root_xml = self.tree_xml.getroot()
        self.current_path = path
        self.treeview.delete(*self.treeview.get_children())
        self.node_map.clear()
        self.build_tree(self.root_xml, "", 0)

    # -------------------------------
    # GUARDAR XML
    # -------------------------------
    def save_xml_pretty(self):
        if not self.tree_xml or not self.current_path:
            messagebox.showwarning("Sin XML", "Primero abre un documento XML.")
            return
        self._save_pretty_to_path(self.current_path)
        messagebox.showinfo("Guardado", f"XML guardado (pretty) en:\n{self.current_path}")

    def save_as_xml_pretty(self):
        if not self.tree_xml:
            messagebox.showwarning("Sin XML", "Primero abre un documento XML.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xml")
        if not path:
            return
        self._save_pretty_to_path(path)
        messagebox.showinfo("Guardado", f"XML guardado (pretty) en:\n{path}")

    def _save_pretty_to_path(self, path):
        xml_bytes = ET.tostring(self.root_xml, encoding="utf-8")
        dom = xml.dom.minidom.parseString(xml_bytes)
        pretty = dom.toprettyxml(indent="  ")
        with open(path, "w", encoding="utf-8") as f:
            f.write(pretty)

    # -------------------------------
    # ÁRBOL XML
    # -------------------------------
    def build_tree(self, elem, parent_id, depth):
        tag = f"level{min(depth, 5)}"
        node_id = self.treeview.insert(parent_id, "end", text=elem.tag, tags=(tag,))
        self.node_map[node_id] = elem
        for child in list(elem):
            self.build_tree(child, node_id, depth + 1)

    def expand_all(self):
        for node_id in self.treeview.get_children():
            self._expand_recursive(node_id)

    def _expand_recursive(self, node_id):
        self.treeview.item(node_id, open=True)
        for child in self.treeview.get_children(node_id):
            self._expand_recursive(child)

    def collapse_all(self):
        for node_id in self.treeview.get_children():
            self._collapse_recursive(node_id)

    def _collapse_recursive(self, node_id):
        self.treeview.item(node_id, open=False)
        for child in self.treeview.get_children(node_id):
            self._collapse_recursive(child)

    # -------------------------------
    # SELECCIÓN DE NODO
    # -------------------------------
    def on_tree_select(self, event):
        sel = self.treeview.selection()
        if not sel:
            return
        node_id = sel[0]
        elem = self.node_map.get(node_id)
        if elem is None:
            return
        self.current_node = elem
        self.entry_tag.delete(0, tk.END)
        self.entry_tag.insert(0, elem.tag)
        self.text_content.delete("1.0", tk.END)
        if elem.text:
            self.text_content.insert("1.0", elem.text.strip())
        self.text_attrs.delete("1.0", tk.END)
        for k, v in elem.attrib.items():
            self.text_attrs.insert(tk.END, f"{k}={v}\n")

    # -------------------------------
    # APLICAR CAMBIOS
    # -------------------------------
    def apply_changes(self):
        if not self.current_node:
            return
        new_tag = self.entry_tag.get().strip()
        if new_tag:
            self.current_node.tag = new_tag
        new_text = self.text_content.get("1.0", tk.END).strip()
        self.current_node.text = new_text if new_text else None
        attrs_text = self.text_attrs.get("1.0", tk.END).strip()
        new_attrs = {}
        for line in attrs_text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                new_attrs[k.strip()] = v.strip()
        self.current_node.attrib.clear()
        self.current_node.attrib.update(new_attrs)
        self.treeview.delete(*self.treeview.get_children())
        self.node_map.clear()
        self.build_tree(self.root_xml, "", 0)

    # -------------------------------
    # AÑADIR / ELIMINAR NODOS
    # -------------------------------
    def add_child_dialog(self):
        if not self.current_node:
            return
        win = tk.Toplevel(self)
        win.title("Añadir hijo")
        tk.Label(win, text="Nombre de la etiqueta del nuevo hijo:").pack(anchor="w", padx=5, pady=5)
        entry = tk.Entry(win)
        entry.pack(fill="x", padx=5, pady=5)

        def do_add():
            tag = entry.get().strip()
            if not tag:
                return
            new = ET.SubElement(self.current_node, tag)
            new.text = ""
            self.treeview.delete(*self.treeview.get_children())
            self.node_map.clear()
            self.build_tree(self.root_xml, "", 0)
            win.destroy()

        tk.Button(win, text="Añadir", command=do_add).pack(pady=5)

    def delete_node(self):
        if not self.current_node:
            return
        parent = self.find_parent(self.root_xml, self.current_node)
        if parent is None:
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar este nodo y todos sus hijos?"):
            parent.remove(self.current_node)
            self.current_node = None
            self.treeview.delete(*self.treeview.get_children())
            self.node_map.clear()
            self.build_tree(self.root_xml, "", 0)

    def find_parent(self, root, target):
        for child in list(root):
            if child is target:
                return root
            res = self.find_parent(child, target)
            if res is not None:
                return res
        return None
    # -------------------------------
    # MOVER NODOS
    # -------------------------------
    def move_node_up(self):
        if not self.current_node:
            return

        parent = self.find_parent(self.root_xml, self.current_node)
        if parent is None:
            return

        children = list(parent)
        idx = children.index(self.current_node)

        if idx == 0:
            return  # ya está arriba

        children[idx], children[idx - 1] = children[idx - 1], children[idx]
        parent[:] = children

        self.treeview.delete(*self.treeview.get_children())
        self.node_map.clear()
        self.build_tree(self.root_xml, "", 0)

    def move_node_down(self):
        if not self.current_node:
            return

        parent = self.find_parent(self.root_xml, self.current_node)
        if parent is None:
            return

        children = list(parent)
        idx = children.index(self.current_node)

        if idx == len(children) - 1:
            return  # ya está abajo

        children[idx], children[idx + 1] = children[idx + 1], children[idx]
        parent[:] = children

        self.treeview.delete(*self.treeview.get_children())
        self.node_map.clear()
        self.build_tree(self.root_xml, "", 0)

    # -------------------------------
    # BÚSQUEDA SIMPLE
    # -------------------------------
    def search_node_dialog(self):
        if not self.root_xml:
            messagebox.showwarning("Sin XML", "Primero abre un documento XML.")
            return

        win = tk.Toplevel(self)
        win.title("Buscar nodo")

        tk.Label(win, text="Buscar por etiqueta (tag) o texto:").pack(anchor="w", padx=5, pady=5)
        entry = tk.Entry(win)
        entry.pack(fill="x", padx=5, pady=5)

        def do_search():
            term = entry.get().strip()
            if not term:
                return
            matches = []
            self._search_recursive(self.root_xml, term, matches)
            if not matches:
                messagebox.showinfo("Sin resultados", "No se encontraron nodos que coincidan.")
                return
            elem = matches[0]
            for node_id, e in self.node_map.items():
                if e is elem:
                    self.treeview.selection_set(node_id)
                    self.treeview.see(node_id)
                    self.on_tree_select(None)
                    break
            win.destroy()

        tk.Button(win, text="Buscar", command=do_search).pack(pady=5)

    def _search_recursive(self, elem, term, matches):
        if term.lower() in elem.tag.lower() or (elem.text and term.lower() in elem.text.lower()):
            matches.append(elem)
        for child in list(elem):
            self._search_recursive(child, term, matches)

    # -------------------------------
    # BÚSQUEDA Y REEMPLAZO AVANZADO
    # -------------------------------
    def search_replace_dialog(self):
        if not self.root_xml:
            messagebox.showwarning("Sin XML", "Primero abre un documento XML.")
            return

        win = tk.Toplevel(self)
        win.title("Buscar / Reemplazar")
        win.geometry("700x400")

        self.search_results = []
        self.search_index = -1

        frame_top = tk.Frame(win)
        frame_top.pack(fill="x")

        tk.Label(frame_top, text="Buscar:").pack(anchor="w", padx=5, pady=5)
        entry_find = tk.Entry(frame_top)
        entry_find.pack(fill="x", padx=5)

        tk.Label(frame_top, text="Reemplazar con:").pack(anchor="w", padx=5, pady=5)
        entry_replace = tk.Entry(frame_top)
        entry_replace.pack(fill="x", padx=5)

        frame_buttons = tk.Frame(frame_top)
        frame_buttons.pack(fill="x", pady=10)

        results_frame = tk.Frame(win)
        results_frame.pack(fill="both", expand=True)

        results_scroll = tk.Scrollbar(results_frame, orient="vertical")
        results_scroll.pack(side="right", fill="y")

        self.results_list = tk.Listbox(results_frame)
        self.results_list.pack(side="left", fill="both", expand=True)
        self.results_list.configure(yscrollcommand=results_scroll.set)
        results_scroll.config(command=self.results_list.yview)

        def update_results_list():
            self.results_list.delete(0, tk.END)
            for elem in self.search_results:
                tag = elem.tag
                text = elem.text.strip() if elem.text else ""
                self.results_list.insert(tk.END, f"{tag}: {text[:80]}")

        def select_from_results(event):
            idx = self.results_list.curselection()
            if not idx:
                return
