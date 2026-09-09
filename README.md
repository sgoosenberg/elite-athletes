# Elite Athletes

A local Python web portal for saving athlete names and phone numbers.
Each submission updates the saved directory and exports all records to the
`elite athletes` folder on your Desktop.

## Files

- `portal.py`: web server, form, data storage, and automatic Desktop exports.
- `README.md`: project description and instructions.
- `.gitignore`: keeps private contact data and generated files out of Git.

## Requirements

Python 3.8 or newer. No third-party packages are needed.

## Run

Open a terminal in this project folder and run:

```sh
python3 portal.py
```

Visit http://127.0.0.1:8000/elite-athletes in your browser.
Enter a full name and phone number, then click **Save athlete**.
Stop the server with **Ctrl+C** in its terminal.
Run only one copy of the portal at a time; stop an existing server before
starting this copy, since both use port 8000.

## Stored information

The portal reads and writes `names.json` beside `portal.py`.
On startup and after each save, it replaces these Desktop exports with the
complete saved directory:

- `~/Desktop/elite athletes/athletes.json`
- `~/Desktop/elite athletes/phone numbers.csv`

Edit information through the portal. Editing the Desktop exports does not
update the portal and those edits will be replaced on the next export.
The application needs permission to write to your Desktop.

If moving from another project folder, stop the old portal and copy its latest
`names.json` beside this `portal.py` before starting. This preserves the latest
records. A local copy of the existing data was included when this folder was
prepared; it is excluded from Git.

## GitHub

Upload the three project files: `portal.py`, `README.md`, and `.gitignore`.
Keep `names.json` and the Desktop contact exports local. The ignore file prevents
normal Git staging of those data files; do not manually upload them through
the GitHub website.

This server runs on your own computer and has no login system. It is intended
for local use.
