# Project Sync Tool

A simple GUI tool to sync development projects between two Macs using Git (for tracked files) and rsync (for untracked/gitignored files).

## Features

- **One-Way Sync**: Push this machine's state to remote - always run from the source machine
- **Git Operations**: Commits locally, pushes, then runs `git pull` on remote via SSH
- **Untracked File Sync**: Syncs gitignored files (like `.env`, `node_modules`, local configs) via rsync
- **SSH Setup Helper**: Built-in wizard to set up SSH keys between machines
- **Portable**: The entire folder can be copied between machines

## Requirements

- macOS (or Linux) with Python 3
- tkinter (included with system Python on macOS)
- SSH access between machines (passwordless via SSH keys)
- Git and rsync (pre-installed on macOS)

## Installation

### Option 1: Clone from GitHub
```bash
git clone https://github.com/ckirschner/ProjectSync.git
```

### Option 2: Download ZIP
Download and extract to your Desktop (or anywhere you like).

## Usage

### Launch the app
Double-click `ProjectSync.app` or run:
```bash
python3 sync_tool.py
```

### First-time setup

1. Click **SSH Setup** to configure passwordless SSH between your machines
2. Click **+ Add Project** to add a project to sync
3. Use **Test Connection** to verify SSH works

### Syncing

Always run from the machine where you made changes. The remote will be updated to match.

- **Sync to Remote**: Full sync - rsync untracked files, git push, then git pull on remote
- **Sync Untracked Files Only**: Just rsync gitignored files to remote
- **Git Push + Remote Pull**: Just the git operations (no untracked files)

## How it works

| File Type | Sync Method |
|-----------|-------------|
| Tracked files (in git) | `git push` / `git pull` |
| Untracked files (in .gitignore) | `rsync` via SSH |

The tool uses `git ls-files --others --ignored --exclude-standard` to identify which files are gitignored, then rsyncs only those files.

## SSH Setup

For syncing to work, you need passwordless SSH access between machines.

1. Click **SSH Setup** in the app
2. Copy your public key
3. Add it to `~/.ssh/authorized_keys` on the remote machine
4. Optionally, add an alias to `~/.ssh/config` for easier access

## Config

Projects are stored in `config.json` in the app folder:

```json
{
  "projects": [
    {
      "name": "My Project",
      "local_path": "/Users/me/projects/myapp",
      "remote_host": "other-mac",
      "remote_path": "/Users/me/projects/myapp",
      "git_branch": "main"
    }
  ]
}
```

## Troubleshooting

### tkinter not found
```
macOS (Homebrew): brew install python-tk
Ubuntu/Debian:    sudo apt install python3-tk
Fedora:           sudo dnf install python3-tkinter
```

Or use the system Python which includes tkinter:
```bash
/usr/bin/python3 sync_tool.py
```

### SSH connection fails
- Ensure SSH keys are set up (use the SSH Setup button)
- Check that the remote machine is reachable
- Verify the host alias in `~/.ssh/config`

### Permission denied on remote
- Make sure `~/.ssh/authorized_keys` on remote has correct permissions (600)
- Make sure `~/.ssh` directory has correct permissions (700)

## License

MIT
