import os
import re

api_dir = r"c:\project\media_server\api"
doc_file = r"c:\project\media_server\docs\api_endpoints.md"

with open(doc_file, "r", encoding="utf-8") as f:
    doc_content = f.read()

route_pattern = re.compile(r"@\w+\.route\(\s*['\"]([^'\"]+)['\"](?:,\s*methods=\[([^\]]+)\])?")

found_routes = []
for root, dirs, files in os.walk(api_dir):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                matches = route_pattern.findall(content)
                for endpoint, methods in matches:
                    rel_path = os.path.relpath(path, api_dir)
                    clean_methods = [m.strip(" '\"") for m in methods.split(",")] if methods else ["GET"]
                    found_routes.append((endpoint, clean_methods, rel_path))

# Also check app.py
if os.path.exists(r"c:\project\media_server\app.py"):
    with open(r"c:\project\media_server\app.py", "r", encoding="utf-8") as f:
        content = f.read()
        matches = route_pattern.findall(content)
        for endpoint, methods in matches:
            clean_methods = [m.strip(" '\"") for m in methods.split(",")] if methods else ["GET"]
            found_routes.append((endpoint, clean_methods, "app.py"))

print(f"Total endpoints found in source: {len(found_routes)}")
print("=" * 60)

missing_in_doc = []
found_in_doc = []

for ep, methods, file_path in found_routes:
    # Check if endpoint string exists in doc
    if ep in doc_content:
        found_in_doc.append((ep, methods, file_path))
    else:
        missing_in_doc.append((ep, methods, file_path))

print(f"Endpoints documented: {len(found_in_doc)}")
print(f"Endpoints missing in docs/api_endpoints.md: {len(missing_in_doc)}")
print("=" * 60)
for ep, methods, file_path in missing_in_doc:
    methods_str = ", ".join(methods)
    print(f"  [{methods_str}] {ep}  (File: {file_path})")
