# Ghost

Ghost is a modular Linux companion CLI, designed primarily for CachyOS. It provides read-only system reports, explicit-confirmation maintenance actions, Python development helpers, and a persistent programming course.

## Requirements

- Linux and Python 3.10 or newer
- `pip` to install Ghost in a virtual environment
- Optional system tools enable additional reports (for example, `lspci`, `smartctl`, `systemctl`, and `pacman`). Ghost reports when a tool or permission is unavailable.

## Install for development

```bash
git clone https://github.com/blawyxd/ghost.git
cd ghost
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
ghost --help
```

The project depends on Typer and Rich. Ghost does not install system packages.

## Commands

Run `ghost` or `ghost help` to see the command list. Common commands include:

| Area | Commands |
| --- | --- |
| System | `doctor`, `hardware`, `processes`, `services`, `network`, `ports`, `logs` |
| Storage and maintenance | `disk`, `large`, `cache`, `clean`, `temp`, `orphans`, `updates` |
| Backups and security | `backup`, `backups`, `restore-backup`, `security` |
| Development | `dev`, `git`, `project`, `project-deps`, `env`, `vars`, `deps`, `test`, `build`, `serve`, `install-deps` |
| Learning | `learn`, `exercises`, `exercise`, `projects`, `progress`, `learning`, `glossary`, `cheatsheet` |

System reports are read-only. `ghost clean` previews the cache entries and estimated space, then asks before removing them. Backup restore previews files and skips existing files. Dependency installation also requires confirmation.

## Python learning

`ghost learn` opens the course browser. Lessons contain explanations, runnable examples, walkthroughs, common mistakes, recaps, and linked exercises. `ghost exercises` lists the course exercises. To submit a solution from a file:

```bash
ghost exercise greeting --file answer.py
ghost exercise greeting --hint 1
ghost progress
```

The course includes programming exercises tested in a separate timed Python process. **This process is not a security sandbox.** Submitted code can access the same user files, network, and system resources as Ghost. Only submit code you trust. Exercise HTTP tests use mocked responses and do not require a live API.

Enable or disable optional XP, levels, achievements, and streaks with `ghost learning on` and `ghost learning off`. Turning Game Mode off preserves its saved data, and no course content depends on it.

## Tests

Run the test suite from the repository root:

```bash
python -m unittest discover -s tests -v
python -m compileall -q main.py ghost tests
```

## Links

- [Project documentation](website/src/pages/docs.astro)
- [Report an issue](https://github.com/blawyxd/ghost/issues)
