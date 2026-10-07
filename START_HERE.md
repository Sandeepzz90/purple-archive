# Birthday website — start here

This backup contains the complete application, downloaded photos, local face-matching models, configuration and a consistent database snapshot.

## Start the website

Extract the `birthday-website` folder, open a terminal in that folder, then run:

```sh
python -m pip install -r requirements.txt
python server.py
```

Open **http://localhost:8000**. The dynamic site is served by `server.py` using `site.html` and its APIs.

Run one copy at a time: the application uses port 8000 and the configured bot's polling connection.

## Change the birthday name

Send the command privately to your bot from the configured owner account:

```text
/name Arjun
/name Aanya
/name Shivani | 시바니
```

Names containing spaces work too. Korean spelling is optional; other names are displayed as entered unless you supply a Korean form. `/name` alone shows the current setting.

## Important files

- `.env`: private bot token and owner ID.
- `data/gallery.sqlite`: media metadata, settings, private messages, visitor records and note receipts.
- `Download/`: stored original media and local travel photos.
- `models/`: verified local recognition models and their licences.
- `data/face_references.json`: labelled references for local matching.
- `README.md`: all features, commands and setup details.

The local recognition worker uses OpenCV and NumPy in `/usr/bin/python3` in the current installation. On another system, point `LOCAL_FACE_PYTHON` to a Python interpreter with those packages. FFmpeg/FFprobe are optional for additional media formats.

**This is a private backup, not a public release ZIP. It includes credentials and saved conversations.**

To make another complete backup:

```sh
python export_project.py --output /sdcard/birthday
```
