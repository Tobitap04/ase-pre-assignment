# Requirements.txt PyPI Validator Design

## Goal

Add a command-line Python script that validates pinned dependencies in a
user-supplied `requirements.txt` file against the PyPI JSON API and prints the
requested summary.

## Interface

`main.py` accepts one positional argument:

```text
python main.py path/to/requirements.txt
```

The input file is read as UTF-8. `Dependencies checked` is the number of
non-empty physical lines in the file. Input is expected to contain valid
`package==version` requirements; malformed lines are skipped rather than
classified as missing packages.

## PyPI validation

For each parsed requirement:

1. Request `https://pypi.org/pypi/{package}/json`.
2. If the response is 404, increment `Packages not on PyPI`.
3. If the package exists, request
   `https://pypi.org/pypi/{package}/{version}/json`.
4. If the version response is 404, increment `Versions not on PyPI`.
5. For an existing package/version, inspect the first entry in `urls` and
   parse its `upload_time`. The corresponding package/version is a candidate
   for the oldest pinned release.

Package names are URL-encoded when constructing URLs. The script uses only
Python standard-library modules (`argparse`, `json`, `urllib`, `datetime`, and
related utilities), avoiding an external dependency.

## Output

The script prints:

```text
Dependencies checked: <count>
Packages not on PyPI: <count>
Versions not on PyPI: <count>
Oldest pinned release: <name>==<version> (<year>)
```

The oldest line is printed only when at least one package/version pair is
available on PyPI. The year is derived from the first file's `upload_time`.

## Error handling

File access failures, HTTP failures other than a 404, invalid JSON, missing
required response fields, and invalid timestamps are reported to stderr and
produce a nonzero exit status. These failures are not silently converted into
missing-package or missing-version results.

## Verification

Create a sample `requirements.txt` containing:

```text
requests==2.31.0
flask==1.3.0
huggingface-cli==0.1.0
numpy==1.16.0
pyyaml=5.1
```

Run the script against that file and verify the summary has five checked
non-empty lines, one package missing from PyPI, one version missing from PyPI,
and `numpy==1.16.0 (2019)` as the oldest pinned release.
