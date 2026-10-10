import os
import zipfile
import xml.etree.ElementTree as ET
import csv

def strip_ns(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag

def short(term):
    return term.rsplit("/", 1)[-1] if term else ""

class DwcaLoader:
    def __init__(self, path):
        self.path = path
        self.base = None

    def load(self):
        if self.path.lower().endswith(".zip"):
            meta = self._load_from_zip()
        else:
            meta = ET.parse(self.path).getroot()
            self.base = os.path.dirname(self.path)
        return self._parse_meta(meta)

    def _load_from_zip(self):
        temp = os.path.join(os.path.dirname(self.path), "_dwca_temp")
        if not os.path.exists(temp):
            os.makedirs(temp)
        with zipfile.ZipFile(self.path, "r") as z:
            z.extractall(temp)
        self.base = temp
        return ET.parse(os.path.join(temp, "meta.xml")).getroot()

    def _resolve(self, location):
        location = location.strip()
        if os.path.isabs(location):
            return location
        return os.path.join(self.base, location)

    def _find_core(self, root):
        for child in root.iter():
            if strip_ns(child.tag) == "core":
                return child
        return None

    def _find_extensions(self, root):
        result = []
        for child in root.iter():
            if strip_ns(child.tag) == "extension":
                result.append(child)
        return result

    def _parse_meta(self, meta):
        core = self._find_core(meta)
        if core is None:
            raise ValueError("meta.xml no contiene <core>")

        loc_nodes = [n for n in core.iter() if strip_ns(n.tag) == "location"]
        core_file = self._resolve(loc_nodes[-1].text)

        id_elem = None
        for n in core.iter():
            if strip_ns(n.tag) == "id":
                id_elem = n
                break
        core_id_index = int(id_elem.get("index"))

        fields_raw = [n for n in core.iter() if strip_ns(n.tag) == "field"]
        fields_raw_sorted = sorted(fields_raw, key=lambda f: int(f.get("index")))
        max_index = max([core_id_index] + [int(f.get("index")) for f in fields_raw_sorted])

        index_to_term = {core_id_index: "id"}
        for f in fields_raw_sorted:
            idx = int(f.get("index"))
            index_to_term[idx] = short(f.get("term"))

        core_fields = [index_to_term.get(i, f"col_{i}") for i in range(max_index + 1)]

        core_rows = []
        with open(core_file, encoding="utf-8") as f:
            r = csv.reader(f, delimiter="\t")
            next(r, None)
            for row in r:
                if len(row) < len(core_fields):
                    row += [""] * (len(core_fields) - len(row))
                core_rows.append(row)

        extensions = []
        ext_data = {}

        for ext in self._find_extensions(meta):
            loc_nodes = [n for n in ext.iter() if strip_ns(n.tag) == "location"]
            fname = self._resolve(loc_nodes[-1].text)

            fields_raw_ext = [n for n in ext.iter() if strip_ns(n.tag) == "field"]
            fields_raw_ext_sorted = sorted(fields_raw_ext, key=lambda f: int(f.get("index")))
            max_idx_ext = max(int(f.get("index")) for f in fields_raw_ext_sorted)

            coreid_elem = None
            for n in ext.iter():
                if strip_ns(n.tag) == "coreid":
                    coreid_elem = n
                    break
            cid_index = int(coreid_elem.get("index"))

            index_to_term_ext = {cid_index: "id"}
            for f in fields_raw_ext_sorted:
                idx = int(f.get("index"))
                index_to_term_ext[idx] = short(f.get("term"))

            fields = [index_to_term_ext.get(i, f"col_{i}") for i in range(max_idx_ext + 1)]

            rows = {}
            with open(fname, encoding="utf-8") as f:
                r = csv.reader(f, delimiter="\t")
                next(r, None)
                for row in r:
                    if len(row) < len(fields):
                        row += [""] * (len(fields) - len(row))
                    cid = row[cid_index]
                    rows.setdefault(cid, []).append(row)

            tab_name = os.path.basename(fname)
            extensions.append((tab_name, fields))
            ext_data[tab_name] = rows

        return core_fields, core_rows, extensions, ext_data
