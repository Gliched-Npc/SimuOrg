import os

directory = "frontend/src"

replacements = {
    "892CDC": "00ADB5",
    "BC6FF1": "33c9cf",
    "52057B": "007a80",
    "137,44,220": "0,173,181",
    "188,111,241": "51,201,207",
    "82,5,123": "57,62,70",
}

for root, _, files in os.walk(directory):
    for file in files:
        if file.endswith(".jsx"):
            file_path = os.path.join(root, file)
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            new_content = content
            for old, new in replacements.items():
                new_content = new_content.replace(old, new)

            if new_content != content:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Updated {file_path}")
