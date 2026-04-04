# AI Dungeon CLI Release

AI Dungeon CLI Release is a terminal-based interactive fiction client for Linux. It lets you play AI-generated adventures from the command line, keep persistent local references to saved adventures, and resume previous sessions without leaving the terminal.

## Project Origin

This project was inspired by the original `ai-dungeon-cli` created by Eigenbahn:
https://github.com/Eigenbahn/ai-dungeon-cli

That original project was an important reference for the terminal gameplay flow and overall user experience, but it no longer works with the modern AI Dungeon backend. This release was created as a new practical implementation inspired by that earlier work and its README.

## Features

- Interactive story gameplay with `/do`, `/say`, `/story`, and `/remember` actions
- Persistent save and resume support through local adventure state tracking
- Terminal-first user interface with optional slow typing mode
- Spinner-based loading feedback while the client waits for API responses
- Resume support with `--resume <id>` and `--resume-last`

## Requirements

- Linux
- Python 3.10 or newer recommended
- Internet access to reach the AI Dungeon backend
- A valid Firebase web API key exported as `AIDUNGEON_FIREBASE_API_KEY`

## Project Layout

- `main.py`: main entry point
- `ai_dungeon_cli/`: application source code
- `requirements.txt`: Python runtime dependencies
- `install.sh`: local installation helper for Linux
- `RELEASE_NOTES.md`: release sanitization and packaging notes

## Installation

Clone or download the repository, then run:

```bash
chmod +x install.sh
./install.sh
```

The installer creates a local virtual environment in `./venv`, installs the required dependencies, and creates a local launcher at `./venv/bin/ai-dungeon`.

## Usage

Before starting the client, export the backend key:

```bash
export AIDUNGEON_FIREBASE_API_KEY="YOUR_FIREBASE_WEB_API_KEY"
```

Then run the game with either of the following:

```bash
source venv/bin/activate
ai-dungeon
```

or

```bash
./venv/bin/ai-dungeon
```

## Example Commands

Start a new session:

```bash
./venv/bin/ai-dungeon
```

Resume the most recent saved adventure:

```bash
./venv/bin/ai-dungeon --resume-last
```

Resume a specific adventure by short ID or adventure ID:

```bash
./venv/bin/ai-dungeon --resume OwKgw6dd61NW
./venv/bin/ai-dungeon --resume 194532449
```

Enable slow typing output:

```bash
./venv/bin/ai-dungeon --slow-typing
```

## Save and Load Notes

- Adventure metadata is stored locally in `~/.config/ai-dungeon-cli/adventures.yml`
- `--resume-last` loads the most recently saved adventure reference
- `--resume <id>` accepts either an adventure short ID or a numeric adventure ID
- The client updates the local save reference whenever a story is created or resumed

## Virtual Environment Notes

The project installs into a local virtual environment to keep your system Python clean and predictable. This avoids polluting global packages and keeps the command isolated to this project folder.

If you open a new shell, reactivate the environment before running `ai-dungeon`:

```bash
source venv/bin/activate
```

If you prefer not to activate the environment manually, use the launcher directly:

```bash
./venv/bin/ai-dungeon
```

## Uninstall

Remove the project folder and local save metadata if you no longer need them:

```bash
rm -rf venv
rm -f ~/.config/ai-dungeon-cli/adventures.yml
```

If you want to keep your saves, remove only `venv/`.

## Creator

Creator: Pedro W. L. Soares de Souza
LinkedIn: https://www.linkedin.com/in/pedro-ssap/
