"""
Helper script to iteratively refactor a large Python file by:
- Replacing in-file class/function definitions with import statements from new modules
- Removing obsolete code blocks
- Processing the file in manageable chunks (line-by-line)

Usage:
    python iterative_large_file_refactor.py <input_file> <output_file> <replacements.json>

Where replacements.json is a JSON file with:
{
  "replacements": [
    {
      "type": "class" | "function",
      "name": "ClassNameOrFunctionName",
      "import": "from .module_name import ClassNameOrFunctionName"
    },
    ...
  ]
}

Author: Cascade AI
"""
import sys
import re
import json


def load_replacements(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)["replacements"]

def process_file(input_path, output_path, replacements):
    # Compile regex for each class/function
    patterns = []
    for repl in replacements:
        if repl["type"] == "class":
            pat = re.compile(rf"^class {repl['name']}\b")
        else:
            pat = re.compile(rf"^def {repl['name']}\b")
        patterns.append((pat, repl))

    with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
        skipping = False
        skip_pat = None
        indent_level = None
        for line in infile:
            if not skipping:
                for pat, repl in patterns:
                    if pat.match(line):
                        # Write the import instead of the code block
                        outfile.write(f"# Replaced in-file {repl['type']} {repl['name']} with import\n")
                        outfile.write(repl['import'] + '\n')
                        skipping = True
                        skip_pat = pat
                        # Compute indent level (number of leading spaces)
                        indent_level = len(line) - len(line.lstrip())
                        break
                else:
                    outfile.write(line)
            else:
                # Continue skipping lines until dedent
                if line.strip() == '':
                    continue
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent_level and not line.lstrip().startswith('@'):
                    skipping = False
                    skip_pat = None
                    indent_level = None
                    outfile.write(line)

    print(f"Refactor complete. Output written to {output_path}.")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python iterative_large_file_refactor.py <input_file> <output_file> <replacements.json>")
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    replacements_json = sys.argv[3]
    replacements = load_replacements(replacements_json)
    process_file(input_file, output_file, replacements)
