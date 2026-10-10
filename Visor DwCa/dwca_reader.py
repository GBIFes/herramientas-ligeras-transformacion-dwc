import os
import zipfile
import xml.etree.ElementTree as ET

class DwcaReader:
    def __init__(self, zip_path):
        self.zip_path = zip_path
        self.temp_dir = os.path.join(os.path.dirname(zip_path), "_dwca_temp")

    def extract_zip(self):
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        with zipfile.ZipFile(self.zip_path, "r") as z:
            z.extractall(self.temp_dir)
        return os.path.join(self.temp_dir, "meta.xml")

    def load_meta(self):
        meta_path = self.extract_zip()
        tree = ET.parse(meta_path)
        root = tree.getroot()
        ns = {"dwc": "http://rs.tdwg.org/dwc/text/"}

        core = root.find("dwc:core", ns)
        if core is None:
            raise ValueError("El meta.xml del ZIP no contiene <core>.")

        core_file = core.find("dwc:files/dwc:location", ns).text
        core_fields = []
        for f in core.findall("dwc:field", ns):
            core_fields.append(f.get("term"))

        extensions = []
        for ext in root.findall("dwc:extension", ns):
            name = ext.find("dwc:files/dwc:location", ns).text
            fields = [f.get("term") for f in ext.findall("dwc:field", ns)]
            extensions.append((name, fields))

        return core_file, core_fields, extensions

    def load_txt(self, filename):
        path = os.path.join(self.temp_dir, filename)
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                rows.append(line.rstrip("\n").split("\t"))
        return rows

    def load_all(self):
        core_file, core_fields, extensions = self.load_meta()
        core_rows = self.load_txt(core_file)

        ext_data = {}
        for name, fields in extensions:
            rows = self.load_txt(name)
            ext_dict = {}
            for r in rows:
                cid = r[0]
                ext_dict.setdefault(cid, []).append(r)
            ext_data[name] = ext_dict

        return core_fields, core_rows, extensions, ext_data
