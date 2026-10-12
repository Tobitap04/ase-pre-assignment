# Requirements.txt PyPI Validator

Checks pinned packages in a requirements file against PyPI.

## Usage

```bash
python main.py requirements.txt
```

The script prints the number of dependencies checked, missing packages,
missing versions, and the oldest pinned release. It uses only Python's
standard library.