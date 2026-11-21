"""Read local OUI registries and classify known vendor names."""
import csv
import re


def load_vendors(paths):
    vendors = {}
    loaded_files = []
    for path in paths:
        try:
            with open(path, encoding="utf-8-sig", errors="replace", newline="") as source:
                loaded = False
                if path.endswith(".csv"):
                    reader = csv.DictReader(source)
                    if not reader.fieldnames or not {"Assignment", "Organization Name"}.issubset(reader.fieldnames):
                        raise ValueError("Invalid IEEE OUI CSV: " + path)
                    for row in reader:
                        prefix = row["Assignment"].strip().upper()
                        vendor = row["Organization Name"].strip()
                        if re.fullmatch(r"[0-9A-F]{6}", prefix) and vendor:
                            vendors.setdefault(prefix, vendor)
                            loaded = True
                else:
                    for line in source:
                        ieee = re.match(r"^\s*([0-9A-Fa-f]{6})\s+\(base 16\)\s+(.+?)\s*$", line)
                        manuf = re.match(r"^\s*([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){2}|[0-9A-Fa-f]{6})\s+(?:\([^)]*\)\s+)?(.+?)\s*$", line)
                        match = ieee or manuf
                        if match:
                            prefix = match.group(1).replace(":", "").upper()
                            vendors.setdefault(prefix, match.group(2).strip())
                            loaded = True
                if loaded:
                    loaded_files.append(path)
        except FileNotFoundError:
            continue
    return vendors, loaded_files


def device_type(vendor):
    name = vendor.lower()
    groups = (
        (("apple", "iphone", "ipad"), "Apple device"),
        (("samsung", "xiaomi", "huawei", "oneplus", "motorola"), "Android phone/tablet"),
        (("raspberry", "rasp pi"), "Raspberry Pi"),
        (("google", "nest"), "Google/Nest device"),
        (("amazon", "ring"), "Amazon/IoT device"),
        (("intel", "realtek", "broadcom", "mediatek"), "Network device"),
        (("microsoft", "dell", "lenovo", "hewlett", "hp", "asus"), "Computer"),
    )
    for names, label in groups:
        if any(term in name for term in names):
            return label
    return "Unknown device"
