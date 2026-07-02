import os

# The string to search for (literally what caused your 404)
search_string = "{'clusters:cluster_detail'}"

# Root directory to search (project root)
root_dir = os.getcwd()

print(f"Searching for {search_string} in {root_dir}...\n")

for dirpath, dirnames, filenames in os.walk(root_dir):
    for filename in filenames:
        if filename.endswith(('.html', '.py')):
            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines, start=1):
                        if search_string in line:
                            print(f"Found in {filepath}, line {i}:")
                            print(line.strip())
                            print("-" * 60)
            except Exception as e:
                print(f"Could not read {filepath}: {e}")