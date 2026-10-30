class DwcaModel:
    def __init__(self, core_fields, core_rows, extensions, ext_data):
        self.core_fields = core_fields
        self.core_rows = core_rows
        self.extensions = extensions
        self.ext_data = ext_data
        self.filtered_indices = None

    def get_indices(self):
        return range(len(self.core_rows)) if self.filtered_indices is None else self.filtered_indices

    def get_record(self, idx):
        return self.core_rows[idx]

    def get_extension_records(self, cid):
        result = {}
        for name, fields in self.extensions:
            result[name] = self.ext_data[name].get(cid, [])
        return result

    def edit_core(self, idx, field, value):
        try:
            fidx = self.core_fields.index(field)
        except ValueError:
            return
        row = self.core_rows[idx]
        if fidx >= len(row):
            row += [""] * (fidx - len(row) + 1)
        row[fidx] = value

    def edit_extension(self, cid, field, value):
        for name, fields in self.extensions:
            if field not in fields:
                continue
            fidx = fields.index(field)
            rows = self.ext_data[name].get(cid, [])
            for r in rows:
                if fidx >= len(r):
                    r += [""] * (fidx - len(r) + 1)
                r[fidx] = value
