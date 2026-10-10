import json

class DwcaEditor:
    def __init__(self, model):
        self.model = model

    def export_record(self, idx, path):
        core = self.model.get_record(idx)
        cid = core[0]

        data = {"core": {}, "extensions": {}}

        for i, field in enumerate(self.model.core_fields):
            data["core"][field] = core[i] if i < len(core) else ""

        ext_records = self.model.get_extension_records(cid)
        for name, rows in ext_records.items():
            ext_list = []
            fields = dict(self.model.extensions)[name]
            for r in rows:
                ext_list.append({fields[i]: (r[i] if i < len(r) else "") for i in range(len(fields))})
            data["extensions"][name] = ext_list

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
