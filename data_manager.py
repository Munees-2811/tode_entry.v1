import json
import csv
import os
from datetime import datetime


class DataManager:
    def __init__(self):
        self.entries = []
        self.field_names = []
        self.current_entry = {}

    def set_field_names(self, names):
        self.field_names = list(names)

    def update_field(self, field_name, value):
        self.current_entry[field_name] = value

    def save_current_entry(self):
        if self.current_entry:
            entry = dict(self.current_entry)
            entry["_timestamp"] = datetime.now().isoformat()
            self.entries.append(entry)
            self.current_entry = {}
            return True
        return False

    def export_csv(self, filepath):
        if not self.entries:
            return False

        all_keys = []
        for entry in self.entries:
            for k in entry:
                if k not in all_keys:
                    all_keys.append(k)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_keys)
            writer.writeheader()
            writer.writerows(self.entries)
        return True

    def export_json(self, filepath):
        if not self.entries:
            return False

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, indent=2, ensure_ascii=False)
        return True

    def get_entry_count(self):
        return len(self.entries)

    def clear_all(self):
        self.entries.clear()
        self.current_entry.clear()
