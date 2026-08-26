# Azeroth Universe — Launcher

Official game launcher for **Azeroth Universe** (a customized WotLK 3.3.5a
private server). Downloads, installs, and updates the game client
automatically from the [UniverseClient](https://github.com/AzerothUniverseCore/UniverseClient)
GitHub releases, then launches the game.

## Features

- Custom dark "Midnight"-style UI (navy/black with gold accents), frameless
  window with its own title bar — fully drawn in code, no Blizzard assets
  used.
  
- Bilingual interface (French / English), switchable at any time via the
  FR/EN buttons in the title bar.
  
- Switching the launcher's language also updates the actual in-game
  language: it writes `SET locale "frFR"`/`"enUS"` to `WTF/Arealm.wtf`, not
  just the launcher's own interface text.
  
- Automatic download and installation of all ~30 client files: direct
  `.MPQ` downloads plus multi-part `.rar` archives (patches and the
  frFR/enUS language packs).
  
- Multi-part RAR archives are extracted with a bundled portable
  `UnRAR.exe` — nothing extra for players to install.
  
- Reliable downloads on unstable connections: each attempt downloads a
  file fully in one pass and retries from scratch on a network failure
  rather than resuming a partial file, avoiding silent corruption on
  flaky connections.
  
- **Pause / Resume**: an in-progress download can be paused and resumed
  later without losing progress or restarting the file from zero.
  
- **Cancel**: an installation in progress can be stopped cleanly at any
  time.
  
- Resume across sessions: files/archives that are already fully installed
  are remembered, so relaunching the installer never re-downloads content
  that's already in place.
  
- Automatic placement of every file in the right folder: patches into
  `Data/`, language files into `Data/frFR/` and `Data/enUS/`, other
  content at the client root.
  
- Writes `realmlist.wtf` for both locales (`Data/frFR/` and `Data/enUS/`)
  with the server's connection address.
  
- "Deep verification" checkbox: re-checks already-downloaded `.MPQ` files
  against the size reported by the server (a full MD5 check isn't
  possible yet — Azeroth Universe doesn't publish official checksums).
  
- Live progress feedback: a dedicated progress bar for the file currently
  downloading (tracks the real percentage), a separate overall
  installation progress bar and counter, plus download speed and
  estimated time remaining.
  
- Single action button that changes label depending on the current
  state: **Check → Install → Play**.
  
- **Play** launches the game client directly from the install folder once
  everything is installed.
  
- Server status badge (top right): shows online/offline and the number of
  connected players when a status endpoint is configured, refreshed
  automatically at a set interval.
  
- News panel with static announcements (editable).

- **Website** / **Register** buttons opening the configured URLs.

- Remembers the chosen install folder, language, and "deep verification"
  setting between launches.
  
- Real-time log console showing every install step (downloads,
  extraction, file placement, errors).
  
- Folder picker to choose or change the installation directory.

## Project structure

```
AzerothUniverseLauncher/
├── main.py                    # application entry point
├── config.py                  # paths, constants, settings persistence
├── i18n.py                    # FR/EN text strings
├── generate_manifest.py       # generates manifest.json (list of files to download)
├── generate_assets.py         # generates the launcher's original artwork
├── manifest.json               # list of client files (generated)
├── requirements.txt
├── core/
│   ├── downloader.py           # HTTP download with automatic retry
│   ├── extractor.py            # .rar extraction via portable UnRAR.exe
│   ├── installer.py            # full orchestration (QThread)
│   ├── wtf.py                  # writes SET locale to WTF/realm.wtf
│   └── server_status.py        # "server online" badge (optional)
├── ui/
│   ├── theme.py                 # stylesheet (QSS)
│   └── main_window.py           # main window (custom title bar)
├── assets/                     # logo, background, icon (generated)
├── tools/                       # UnRAR.exe to add manually (see inside)
└── build/
    ├── launcher.spec             # PyInstaller spec
    └── BUILD_INSTRUCTIONS.md     # Windows build procedure
```

## Running in development (Linux/Windows/macOS)

```bash
python3 -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python3 main.py
```

On Linux/macOS, extraction falls back to the system's `unrar` if installed
(`apt install unrar` on Debian/Ubuntu, or `unrar-free` depending on the
repository) since `tools/UnRAR.exe` is a Windows binary.

## Building the final Windows executable

To be done directly on a Windows machine, with the venv activated and
`tools/UnRAR.exe` already in place:

```bat
pyinstaller build\launcher.spec
```

The final executable is created at `dist\AzerothUniverseLauncher.exe`. See
[`build/BUILD_INSTRUCTIONS.md`](build/BUILD_INSTRUCTIONS.md) for the full
step-by-step procedure.

## Updating the client file list

If new patches are published on UniverseClient, edit the lists at the top
of `generate_manifest.py` (`MULTI_PART_MPQ`, `LOCALES`,
`SINGLE_MPQ_FILES`), then re-run it:

```bash
python3 generate_manifest.py
```
