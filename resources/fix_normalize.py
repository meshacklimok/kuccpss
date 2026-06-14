"""Replace the entire normalize() function with a clean ASCII-safe version."""

path = r"c:\Users\user\OneDrive\Desktop\webdev2025\kuccpss\courses\management\commands\seed_tvet_programmes.py"

with open(path, encoding="utf-8") as f:
    content = f.read()

# Find the start and end of the normalize function
start_marker = "def normalize(name: str) -> str:"
end_marker = "\ndef is_section_header"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx)

if start_idx == -1 or end_idx == -1:
    print("Markers not found!")
    raise SystemExit(1)

print(f"Found normalize() at chars {start_idx}-{end_idx}")
print("Old function:")
print(content[start_idx:end_idx])

# Build the replacement using only ASCII string literals
# No curly quotes, no em-dashes in code
replacement = (
    "def normalize(name: str) -> str:\n"
    '    """Normalise institution/course name for DB lookup.\n'
    "    Strips apostrophes, normalises ampersands, removes level qualifiers.\n"
    '    """\n'
    "    n = name.upper()\n"
    "    # Remove apostrophe-like chars by codepoint to avoid encoding issues\n"
    "    for cp in (0x2018, 0x2019, 0x201a, 0x201b, 0x2032, 0x2035, 0x60, 0x27):\n"
    "        n = n.replace(chr(cp), \"\")\n"
    "    # Remove punctuation that varies by source\n"
    "    for ch in ('\"', \",\", \".\"):\n"
    "        n = n.replace(ch, \"\")\n"
    "    # Ampersand with or without surrounding spaces -> AND\n"
    "    import re as _re\n"
    "    n = _re.sub(r\"\\s*&\\s*\", \" AND \", n)\n"
    "    n = n.replace(\"-\", \" \")\n"
    "    # Strip trailing KUCCPS level / CDACC / CBET qualifiers\n"
    "    n = _re.sub(r\"\\s*\\(\\s*LEVEL\\s+\\d+\\s*\\)\\s*$\", \"\", n)\n"
    "    n = _re.sub(r\"\\s+LEVEL\\s+\\d+\\s*$\", \"\", n)\n"
    "    n = _re.sub(r\"\\s*\\(\\s*TVET[^)]*\\)\\s*$\", \"\", n, flags=_re.IGNORECASE)\n"
    "    n = _re.sub(r\"\\s*\\(\\s*CDACC[^)]*\\)\\s*$\", \"\", n, flags=_re.IGNORECASE)\n"
    "    n = _re.sub(r\"\\s*\\(\\s*CBET[^)]*\\)\\s*$\", \"\", n, flags=_re.IGNORECASE)\n"
    "    n = _re.sub(r\"\\s+\", \" \", n).strip()\n"
    "    return n\n"
)

new_content = content[:start_idx] + replacement + content[end_idx:]

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

# Verify syntax
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("\nSyntax OK.")
except py_compile.PyCompileError as e:
    print(f"\nSyntax error: {e}")
    # Show remaining non-ASCII code lines
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if any(ord(c) > 127 for c in line) and not line.strip().startswith("#") and not '"""' in line and "'" not in line:
                print(f"  Line {i}: {repr(line)}")
