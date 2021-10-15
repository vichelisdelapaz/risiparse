# 2.0.1

-  Renamed ```all-messages``` to ```all-posts``` to be consistent

# 2.0.0

- Most changes in this version are internal , i.e adding more test, refactor, proper CI...

- Changed database location to be xdg compliant, i.e ".local/share/risiparse/risiparse.db"
  it follows the same logic for windows and macos (Appdata, Library...)

- Dropped PyQtWebengine in favour of PySide

# 1.4.0

- If the html file is too big, it will be splitted into smaller ones, pdfs will then be created
  and finally they will be merged together.

# 1.3.0

- Added ```--create-pdfs``` which allows to create pdfs from a list of html files given on the command
  line, just use ```--no-download``` to create pdfs of all html files in cur_dir/risitas-html.

# 1.2.0

- It is now possible to download risitas and continue the download at a given page instead of redownloading everything
  thanks to the sqlite database introduced in this version.

# 1.1.0

- Added Wayback machine support for risific.fr
