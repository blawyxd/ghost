# ghost.

A small Linux companion for the terminal.

## Features

- Check available pacman updates without installing them.
- View disk usage.
- Find large files in your home directory.
- Browse useful Linux commands.

## Requirements

- Linux
- Python 3.10+
- Git
- pacman for update checks

## Installation

    git clone https://github.com/uatimuu-cmyk/ghost.git
    cd ghost
    python -m venv .venv
    source .venv/bin/activate.fish
    python -m pip install -e .

## Commands

| Command | Description |
| --- | --- |
| `ghost` | Open the home screen |
| `ghost help` | Show available commands |
| `ghost updates` | Check pacman updates |
| `ghost disk` | Show disk usage |
| `ghost large` | Find large files |
| `ghost vault` | Display useful Linux commands |

## Safety

Ghost currently focuses on inspection. It does not install packages, delete files, or execute commands from the command vault.

## Website development

    cd website
    npm install
    npm run dev

Ghost is actively being developed.
