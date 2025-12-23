#!/usr/bin/env python3
"""
Project Sync Tool - Sync projects between Macs using Git and rsync
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Check for tkinter before importing
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, simpledialog
except ImportError:
    # Show error without tkinter
    print("=" * 60)
    print("ERROR: tkinter is not installed")
    print("=" * 60)
    print()
    print("tkinter is required to run Project Sync Tool.")
    print()
    print("To install tkinter:")
    print()
    print("  macOS (Homebrew Python):")
    print("    brew install python-tk")
    print()
    print("  macOS (System Python):")
    print("    tkinter should be included. Try running with:")
    print("    /usr/bin/python3 sync_tool.py")
    print()
    print("  Ubuntu/Debian:")
    print("    sudo apt install python3-tk")
    print()
    print("  Fedora:")
    print("    sudo dnf install python3-tkinter")
    print()
    print("=" * 60)
    sys.exit(1)

# Get the directory where this script lives (src/) and the app root
SCRIPT_DIR = Path(__file__).parent.resolve()
APP_DIR = SCRIPT_DIR.parent  # One level up from src/
CONFIG_FILE = APP_DIR / "config.json"


class Config:
    """Manage project configurations"""

    def __init__(self):
        self.projects = []
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.projects = data.get('projects', [])
            except (json.JSONDecodeError, IOError):
                self.projects = []
        else:
            self.projects = []

    def save(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'projects': self.projects}, f, indent=2)

    def add_project(self, project):
        self.projects.append(project)
        self.save()

    def update_project(self, index, project):
        self.projects[index] = project
        self.save()

    def remove_project(self, index):
        del self.projects[index]
        self.save()

    def get_project_names(self):
        return [p['name'] for p in self.projects]


class ProjectDialog(tk.Toplevel):
    """Dialog for adding/editing a project"""

    def __init__(self, parent, title="Add Project", project=None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.project = project or {}

        self.transient(parent)
        self.grab_set()

        self.geometry("500x320")
        self.resizable(False, False)

        self._create_widgets()
        self._center_window(parent)

        self.wait_window(self)

    def _center_window(self, parent):
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Name
        ttk.Label(frame, text="Project Name:").grid(row=0, column=0, sticky="w", pady=8)
        self.name_var = tk.StringVar(value=self.project.get('name', ''))
        ttk.Entry(frame, textvariable=self.name_var, width=40).grid(row=0, column=1, columnspan=2, sticky="ew", pady=8)

        # Local Path
        ttk.Label(frame, text="Local Path:").grid(row=1, column=0, sticky="w", pady=8)
        self.local_var = tk.StringVar(value=self.project.get('local_path', ''))
        ttk.Entry(frame, textvariable=self.local_var, width=35).grid(row=1, column=1, sticky="ew", pady=8)
        ttk.Button(frame, text="...", width=3, command=self._browse_local).grid(row=1, column=2, padx=(5,0), pady=8)

        # Remote Host
        ttk.Label(frame, text="Remote Host:").grid(row=2, column=0, sticky="w", pady=8)
        self.host_var = tk.StringVar(value=self.project.get('remote_host', ''))
        ttk.Entry(frame, textvariable=self.host_var, width=40).grid(row=2, column=1, columnspan=2, sticky="ew", pady=8)

        # Remote Path
        ttk.Label(frame, text="Remote Path:").grid(row=3, column=0, sticky="w", pady=8)
        self.remote_var = tk.StringVar(value=self.project.get('remote_path', ''))
        ttk.Entry(frame, textvariable=self.remote_var, width=40).grid(row=3, column=1, columnspan=2, sticky="ew", pady=8)

        # Git Branch
        ttk.Label(frame, text="Git Branch:").grid(row=4, column=0, sticky="w", pady=8)
        self.branch_var = tk.StringVar(value=self.project.get('git_branch', 'main'))
        ttk.Entry(frame, textvariable=self.branch_var, width=40).grid(row=4, column=1, columnspan=2, sticky="ew", pady=8)

        # Help text
        help_text = "Remote Host: SSH alias from ~/.ssh/config or user@hostname"
        ttk.Label(frame, text=help_text, foreground="gray").grid(row=5, column=0, columnspan=3, sticky="w", pady=(10,5))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=(15,10))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side=tk.LEFT, padx=10)

        frame.columnconfigure(1, weight=1)

    def _browse_local(self):
        path = filedialog.askdirectory(title="Select Local Project Folder")
        if path:
            self.local_var.set(path)

    def _save(self):
        name = self.name_var.get().strip()
        local = self.local_var.get().strip()
        host = self.host_var.get().strip()
        remote = self.remote_var.get().strip()
        branch = self.branch_var.get().strip() or 'main'

        if not all([name, local, host, remote]):
            messagebox.showerror("Error", "All fields except branch are required")
            return

        if not os.path.isdir(local):
            messagebox.showerror("Error", f"Local path does not exist: {local}")
            return

        self.result = {
            'name': name,
            'local_path': local,
            'remote_host': host,
            'remote_path': remote,
            'git_branch': branch
        }
        self.destroy()


class CommitDialog(tk.Toplevel):
    """Dialog for entering commit message"""

    def __init__(self, parent, changes_summary=""):
        super().__init__(parent)
        self.title("Uncommitted Changes Detected")
        self.result = None

        self.transient(parent)
        self.grab_set()

        self.geometry("450x220")
        self.resizable(False, False)

        self._create_widgets(changes_summary)
        self._center_window(parent)

        self.wait_window(self)

    def _center_window(self, parent):
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self, changes_summary):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="You have uncommitted changes.").pack(anchor="w")

        if changes_summary:
            summary_frame = ttk.Frame(frame)
            summary_frame.pack(fill=tk.X, pady=(10,0))
            text = tk.Text(summary_frame, height=4, width=50, wrap=tk.WORD)
            text.insert("1.0", changes_summary)
            text.config(state=tk.DISABLED)
            text.pack(fill=tk.X)

        ttk.Label(frame, text="Commit message:").pack(anchor="w", pady=(15,5))
        self.msg_var = tk.StringVar()
        self.msg_entry = ttk.Entry(frame, textvariable=self.msg_var, width=50)
        self.msg_entry.pack(fill=tk.X)
        self.msg_entry.focus_set()
        self.msg_entry.bind("<Return>", lambda e: self._commit())

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=(20,0))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Commit & Push", command=self._commit).pack(side=tk.LEFT, padx=5)

    def _commit(self):
        msg = self.msg_var.get().strip()
        if not msg:
            messagebox.showerror("Error", "Commit message is required")
            return
        self.result = msg
        self.destroy()


class ConflictDialog(tk.Toplevel):
    """Dialog for resolving file conflicts"""

    def __init__(self, parent, conflicts):
        super().__init__(parent)
        self.title("Conflicts Detected")
        self.conflicts = conflicts
        self.results = {}  # file -> 'local' | 'remote' | 'skip'
        self.cancelled = False

        self.transient(parent)
        self.grab_set()

        self.geometry("500x400")
        self.resizable(True, True)

        self._create_widgets()
        self._center_window(parent)

        self.current_index = 0
        self._show_conflict(0)

        self.wait_window(self)

    def _center_window(self, parent):
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        self.title_label = ttk.Label(frame, text="", font=("TkDefaultFont", 12, "bold"))
        self.title_label.pack(anchor="w")

        self.file_label = ttk.Label(frame, text="")
        self.file_label.pack(anchor="w", pady=(10,5))

        ttk.Label(frame, text="Modified on both local and remote").pack(anchor="w")

        info_frame = ttk.Frame(frame)
        info_frame.pack(fill=tk.X, pady=15)

        self.local_time_label = ttk.Label(info_frame, text="Local:  ")
        self.local_time_label.pack(anchor="w")
        self.remote_time_label = ttk.Label(info_frame, text="Remote: ")
        self.remote_time_label.pack(anchor="w")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Use Local", command=lambda: self._resolve('local')).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Use Remote", command=lambda: self._resolve('remote')).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Skip", command=lambda: self._resolve('skip')).pack(side=tk.LEFT, padx=5)

        self.apply_all_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Apply to all remaining conflicts", variable=self.apply_all_var).pack(anchor="w", pady=10)

        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Button(frame, text="Cancel All", command=self._cancel).pack()

    def _show_conflict(self, index):
        if index >= len(self.conflicts):
            self.destroy()
            return

        conflict = self.conflicts[index]
        self.title_label.config(text=f"Conflict {index + 1} of {len(self.conflicts)}")
        self.file_label.config(text=f"File: {conflict['file']}")
        self.local_time_label.config(text=f"Local:  {conflict.get('local_time', 'Unknown')}")
        self.remote_time_label.config(text=f"Remote: {conflict.get('remote_time', 'Unknown')}")

    def _resolve(self, choice):
        conflict = self.conflicts[self.current_index]
        self.results[conflict['file']] = choice

        if self.apply_all_var.get():
            # Apply same choice to all remaining
            for i in range(self.current_index + 1, len(self.conflicts)):
                self.results[self.conflicts[i]['file']] = choice
            self.destroy()
        else:
            self.current_index += 1
            self._show_conflict(self.current_index)

    def _cancel(self):
        self.cancelled = True
        self.destroy()


class SSHSetupDialog(tk.Toplevel):
    """Dialog to help users set up SSH keys"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("SSH Setup Helper")
        self.parent = parent

        self.transient(parent)
        self.grab_set()

        self.geometry("580x620")
        self.resizable(False, False)

        self._create_widgets()
        self._center_window(parent)
        self._load_ssh_info()

    def _center_window(self, parent):
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(frame, text="SSH Key Setup", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Set up passwordless SSH access to your remote machine",
                  foreground="gray").pack(anchor="w", pady=(0,15))

        # Step 1: Check/Generate Key
        step1_frame = ttk.LabelFrame(frame, text="Step 1: Your SSH Public Key", padding=10)
        step1_frame.pack(fill=tk.X, pady=(0,10))

        self.key_status_label = ttk.Label(step1_frame, text="Checking...")
        self.key_status_label.pack(anchor="w")

        key_text_frame = ttk.Frame(step1_frame)
        key_text_frame.pack(fill=tk.X, pady=(10,5))

        self.key_text = tk.Text(key_text_frame, height=3, width=60, wrap=tk.WORD)
        self.key_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        key_scroll = ttk.Scrollbar(key_text_frame, orient=tk.VERTICAL, command=self.key_text.yview)
        key_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.key_text.config(yscrollcommand=key_scroll.set)

        key_btn_frame = ttk.Frame(step1_frame)
        key_btn_frame.pack(fill=tk.X, pady=(5,0))
        ttk.Button(key_btn_frame, text="Copy to Clipboard", command=self._copy_key).pack(side=tk.LEFT)
        ttk.Button(key_btn_frame, text="Generate New Key", command=self._generate_key).pack(side=tk.LEFT, padx=(10,0))

        # Step 2: Auto copy to remote
        step2_frame = ttk.LabelFrame(frame, text="Step 2: Add Key to Remote Machine", padding=10)
        step2_frame.pack(fill=tk.X, pady=(0,10))

        # Description
        ttk.Label(step2_frame, text="Auto-copy your key using ssh-copy-id (prompts for password once):").pack(anchor="w", pady=(0,5))

        # Auto copy option
        auto_frame = ttk.Frame(step2_frame)
        auto_frame.pack(fill=tk.X, pady=(0,5))

        self.remote_host_var = tk.StringVar()
        self.remote_host_entry = ttk.Entry(auto_frame, textvariable=self.remote_host_var, width=30)
        self.remote_host_entry.pack(side=tk.LEFT, padx=(0,10))
        self.remote_host_entry.insert(0, "user@192.168.1.xxx")
        ttk.Button(auto_frame, text="Send Key", command=self._auto_copy_key).pack(side=tk.LEFT)

        # Manual instructions
        instructions = """Or do it manually on the REMOTE machine:
    mkdir -p ~/.ssh && chmod 700 ~/.ssh
    echo "PASTE_KEY_HERE" >> ~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys"""

        inst_text = tk.Text(step2_frame, height=4, width=60, wrap=tk.WORD, bg="#2d2d2d", fg="#ffffff", relief=tk.FLAT)
        inst_text.insert("1.0", instructions)
        inst_text.config(state=tk.DISABLED)
        inst_text.pack(fill=tk.X)

        # Step 3: SSH Config
        step3_frame = ttk.LabelFrame(frame, text="Step 3: Optional - Add SSH Alias", padding=10)
        step3_frame.pack(fill=tk.X, pady=(0,10))

        ttk.Label(step3_frame, text="Add to ~/.ssh/config for easier access:").pack(anchor="w")

        self.config_text = tk.Text(step3_frame, height=4, width=60, bg="#2d2d2d", fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT)
        self.config_text.insert("1.0", "Host my-other-mac\n    HostName 192.168.1.XXX\n    User yourusername")
        self.config_text.pack(fill=tk.X, pady=(5,0))

        # Close button
        ttk.Button(frame, text="Close", command=self.destroy).pack(pady=(15,0))

    def _load_ssh_info(self):
        # Check for existing SSH keys
        home = Path.home()
        key_paths = [
            home / ".ssh" / "id_ed25519.pub",
            home / ".ssh" / "id_rsa.pub",
        ]

        pub_key = None
        for key_path in key_paths:
            if key_path.exists():
                try:
                    pub_key = key_path.read_text().strip()
                    self.key_status_label.config(
                        text=f"Found: {key_path.name}", foreground="green"
                    )
                    break
                except:
                    pass

        if pub_key:
            self.key_text.delete("1.0", tk.END)
            self.key_text.insert("1.0", pub_key)
        else:
            self.key_status_label.config(
                text="No SSH key found. Click 'Generate New Key' to create one.",
                foreground="orange"
            )
            self.key_text.delete("1.0", tk.END)
            self.key_text.insert("1.0", "(No key found)")

    def _copy_key(self):
        key = self.key_text.get("1.0", tk.END).strip()
        if key and key != "(No key found)":
            self.clipboard_clear()
            self.clipboard_append(key)
            messagebox.showinfo("Copied", "Public key copied to clipboard!")
        else:
            messagebox.showerror("Error", "No key to copy. Generate one first.")

    def _generate_key(self):
        if not messagebox.askyesno("Generate Key",
            "This will generate a new ed25519 SSH key pair.\n\n"
            "If you already have a key, this will NOT overwrite it.\n\n"
            "Continue?"):
            return

        home = Path.home()
        key_path = home / ".ssh" / "id_ed25519"

        if key_path.exists():
            messagebox.showinfo("Key Exists",
                f"SSH key already exists at {key_path}\n\n"
                "Reload to view it.")
            self._load_ssh_info()
            return

        # Generate key
        try:
            result = subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-f", str(key_path), "-N", ""],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                messagebox.showinfo("Success", "SSH key generated successfully!")
                self._load_ssh_info()
            else:
                messagebox.showerror("Error", f"Failed to generate key:\n{result.stderr}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate key:\n{e}")

    def _auto_copy_key(self):
        remote = self.remote_host_var.get().strip()
        if not remote:
            messagebox.showerror("Error", "Please enter the remote host (e.g., user@192.168.1.100)")
            return

        # Check if we have a key to copy
        key = self.key_text.get("1.0", tk.END).strip()
        if not key or key == "(No key found)":
            messagebox.showerror("Error", "No SSH key found. Generate one first.")
            return

        # Run ssh-copy-id in Terminal so user can enter password
        try:
            # Use AppleScript to open Terminal and run ssh-copy-id
            applescript = f'''
            tell application "Terminal"
                activate
                do script "ssh-copy-id {remote} && echo '' && echo '✓ SSH key copied successfully!' && echo 'You can close this window.'"
            end tell
            '''
            subprocess.run(["osascript", "-e", applescript])
            messagebox.showinfo("Terminal Opened",
                f"A Terminal window has opened to copy your key to {remote}.\n\n"
                "Enter your password when prompted.\n\n"
                "After it succeeds, you can close the Terminal window.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Terminal:\n{e}")


class SyncApp(tk.Tk):
    """Main application window"""

    def __init__(self):
        super().__init__()

        self.title("Project Sync Tool")
        self.geometry("580x440")
        self.resizable(False, False)

        self.config = Config()
        self.current_project = None

        self._create_widgets()
        self._update_project_list()

        # Center window on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Project selector row
        selector_frame = ttk.Frame(main_frame)
        selector_frame.pack(fill=tk.X, pady=(0,10))

        ttk.Label(selector_frame, text="Project:").pack(side=tk.LEFT)
        self.project_var = tk.StringVar()
        self.project_combo = ttk.Combobox(selector_frame, textvariable=self.project_var, state="readonly", width=28)
        self.project_combo.pack(side=tk.LEFT, padx=(10,10))
        self.project_combo.bind("<<ComboboxSelected>>", self._on_project_selected)

        ttk.Button(selector_frame, text="Test SSH", command=self._test_connection).pack(side=tk.RIGHT)

        # Project info display
        info_frame = ttk.LabelFrame(main_frame, text="Project Details", padding=10)
        info_frame.pack(fill=tk.X, pady=(0,15))

        self.local_label = ttk.Label(info_frame, text="Local:  (no project selected)")
        self.local_label.pack(anchor="w")
        self.remote_label = ttk.Label(info_frame, text="Remote: ")
        self.remote_label.pack(anchor="w")
        self.branch_label = ttk.Label(info_frame, text="Branch: ")
        self.branch_label.pack(anchor="w")

        # Full Sync button
        sync_frame = ttk.Frame(main_frame)
        sync_frame.pack(fill=tk.X, pady=10)
        self.full_sync_btn = ttk.Button(sync_frame, text="Full Sync", command=self._full_sync)
        self.full_sync_btn.pack(expand=True)

        # Untracked files section
        untracked_frame = ttk.LabelFrame(main_frame, text="Untracked Files (gitignored)", padding=10)
        untracked_frame.pack(fill=tk.X, pady=(0,10))

        btn_row1 = ttk.Frame(untracked_frame)
        btn_row1.pack(fill=tk.X)
        self.sync_to_btn = ttk.Button(btn_row1, text="Sync to Remote ->", command=self._sync_to_remote)
        self.sync_to_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,5))
        self.sync_from_btn = ttk.Button(btn_row1, text="<- Sync from Remote", command=self._sync_from_remote)
        self.sync_from_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5,0))

        # Git operations section
        git_frame = ttk.LabelFrame(main_frame, text="Git Operations", padding=10)
        git_frame.pack(fill=tk.X, pady=(0,10))

        btn_row2 = ttk.Frame(git_frame)
        btn_row2.pack(fill=tk.X)
        self.push_btn = ttk.Button(btn_row2, text="Push to Remote", command=self._git_push)
        self.push_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,5))
        self.pull_btn = ttk.Button(btn_row2, text="Pull from Remote", command=self._git_pull)
        self.pull_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5,0))

        # Project management buttons
        mgmt_frame = ttk.Frame(main_frame)
        mgmt_frame.pack(fill=tk.X, pady=(10,0))

        ttk.Button(mgmt_frame, text="+ Add Project", command=self._add_project).pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(mgmt_frame, text="Edit Project", command=self._edit_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(mgmt_frame, text="Remove", command=self._remove_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(mgmt_frame, text="SSH Setup", command=self._ssh_setup).pack(side=tk.RIGHT)

        # Status bar
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(15,10))
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="gray")
        self.status_label.pack(anchor="w")

        self._set_buttons_state(False)

    def _set_buttons_state(self, enabled):
        state = "normal" if enabled else "disabled"
        for btn in [self.full_sync_btn, self.sync_to_btn, self.sync_from_btn,
                    self.push_btn, self.pull_btn]:
            btn.config(state=state)

    def _update_project_list(self):
        names = self.config.get_project_names()
        self.project_combo['values'] = names
        if names and not self.project_var.get():
            self.project_combo.current(0)
            self._on_project_selected(None)

    def _on_project_selected(self, event):
        name = self.project_var.get()
        for p in self.config.projects:
            if p['name'] == name:
                self.current_project = p
                self.local_label.config(text=f"Local:  {p['local_path']}")
                self.remote_label.config(text=f"Remote: {p['remote_host']}:{p['remote_path']}")
                self.branch_label.config(text=f"Branch: {p['git_branch']}")
                self._set_buttons_state(True)
                return

        self.current_project = None
        self._set_buttons_state(False)

    def _set_status(self, msg, color="gray"):
        self.status_var.set(msg)
        self.status_label.config(foreground=color)
        self.update_idletasks()

    def _run_command(self, cmd, cwd=None):
        """Run a shell command and return (success, output)"""
        try:
            result = subprocess.run(
                cmd, shell=True, cwd=cwd,
                capture_output=True, text=True, timeout=120
            )
            output = result.stdout + result.stderr
            return result.returncode == 0, output.strip()
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def _ssh_setup(self):
        """Open SSH setup helper dialog"""
        SSHSetupDialog(self)

    def _test_connection(self):
        if not self.current_project:
            messagebox.showerror("Error", "No project selected")
            return

        self._set_status("Testing SSH connection...", "blue")
        host = self.current_project['remote_host']

        # Test SSH connection
        success, output = self._run_command(f'ssh -o ConnectTimeout=10 -o BatchMode=yes {host} "echo connected"')

        if success and "connected" in output:
            self._set_status("Connection successful!", "green")
            messagebox.showinfo("Success", f"Successfully connected to {host}")
        else:
            self._set_status("Connection failed", "red")
            messagebox.showerror("Connection Failed",
                f"Could not connect to {host}\n\nMake sure:\n"
                "1. SSH keys are set up for passwordless login\n"
                "2. The host is reachable\n"
                f"3. The host alias exists in ~/.ssh/config\n\nError: {output}")

    def _add_project(self):
        dialog = ProjectDialog(self, "Add Project")
        if dialog.result:
            self.config.add_project(dialog.result)
            self._update_project_list()
            # Select the new project
            self.project_var.set(dialog.result['name'])
            self._on_project_selected(None)
            self._set_status("Project added", "green")

    def _edit_project(self):
        if not self.current_project:
            messagebox.showerror("Error", "No project selected")
            return

        # Find index
        index = None
        for i, p in enumerate(self.config.projects):
            if p['name'] == self.current_project['name']:
                index = i
                break

        if index is None:
            return

        dialog = ProjectDialog(self, "Edit Project", self.current_project)
        if dialog.result:
            self.config.update_project(index, dialog.result)
            self._update_project_list()
            self.project_var.set(dialog.result['name'])
            self._on_project_selected(None)
            self._set_status("Project updated", "green")

    def _remove_project(self):
        if not self.current_project:
            messagebox.showerror("Error", "No project selected")
            return

        if not messagebox.askyesno("Confirm", f"Remove project '{self.current_project['name']}'?"):
            return

        for i, p in enumerate(self.config.projects):
            if p['name'] == self.current_project['name']:
                self.config.remove_project(i)
                break

        self.project_var.set("")
        self.current_project = None
        self._update_project_list()
        self._on_project_selected(None)
        self._set_status("Project removed", "green")

    def _get_git_status(self):
        """Check if there are uncommitted changes. Returns (is_dirty, summary)"""
        cwd = self.current_project['local_path']

        success, output = self._run_command("git status --porcelain", cwd=cwd)
        if not success:
            return False, "Error checking git status"

        is_dirty = bool(output.strip())
        return is_dirty, output.strip()

    def _git_push(self, skip_commit_check=False):
        if not self.current_project:
            return False

        cwd = self.current_project['local_path']
        branch = self.current_project['git_branch']

        self._set_status("Checking for uncommitted changes...", "blue")

        is_dirty, summary = self._get_git_status()

        if is_dirty:
            dialog = CommitDialog(self, summary)
            if not dialog.result:
                self._set_status("Push cancelled", "gray")
                return False

            # Commit changes
            self._set_status("Committing changes...", "blue")
            commit_msg = dialog.result.replace('"', '\\"')
            success, output = self._run_command(f'git add -A && git commit -m "{commit_msg}"', cwd=cwd)
            if not success:
                self._set_status("Commit failed", "red")
                messagebox.showerror("Error", f"Commit failed:\n{output}")
                return False

        # Push
        self._set_status("Pushing to remote...", "blue")
        success, output = self._run_command(f"git push origin {branch}", cwd=cwd)

        if success:
            self._set_status("Push successful", "green")
            return True
        else:
            self._set_status("Push failed", "red")
            messagebox.showerror("Error", f"Push failed:\n{output}")
            return False

    def _git_pull(self):
        if not self.current_project:
            return False

        cwd = self.current_project['local_path']
        branch = self.current_project['git_branch']

        # Check for uncommitted changes
        is_dirty, _ = self._get_git_status()
        if is_dirty:
            if not messagebox.askyesno("Warning",
                "You have uncommitted changes. Pull may fail or create merge conflicts.\n\nContinue anyway?"):
                self._set_status("Pull cancelled", "gray")
                return False

        self._set_status("Pulling from remote...", "blue")
        success, output = self._run_command(f"git pull origin {branch}", cwd=cwd)

        if success:
            self._set_status("Pull successful", "green")
            return True
        else:
            self._set_status("Pull failed", "red")
            messagebox.showerror("Error", f"Pull failed:\n{output}")
            return False

    def _get_gitignored_files(self, local=True):
        """Get list of gitignored files that exist"""
        if local:
            cwd = self.current_project['local_path']
            success, output = self._run_command(
                "git ls-files --others --ignored --exclude-standard",
                cwd=cwd
            )
        else:
            host = self.current_project['remote_host']
            path = self.current_project['remote_path']
            success, output = self._run_command(
                f'ssh {host} "cd {path} && git ls-files --others --ignored --exclude-standard"'
            )

        if success and output:
            return output.strip().split('\n')
        return []

    def _get_file_mtime(self, filepath, local=True):
        """Get file modification time"""
        if local:
            cwd = self.current_project['local_path']
            full_path = os.path.join(cwd, filepath)
            if os.path.exists(full_path):
                mtime = os.path.getmtime(full_path)
                return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        else:
            host = self.current_project['remote_host']
            path = self.current_project['remote_path']
            success, output = self._run_command(
                f'ssh {host} "stat -f %m {path}/{filepath}" 2>/dev/null || ssh {host} "stat -c %Y {path}/{filepath}" 2>/dev/null'
            )
            if success and output.strip().isdigit():
                mtime = int(output.strip())
                return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        return None

    def _detect_conflicts(self, direction):
        """Detect files that exist on both sides"""
        local_files = set(self._get_gitignored_files(local=True))
        remote_files = set(self._get_gitignored_files(local=False))

        common_files = local_files & remote_files
        conflicts = []

        for f in common_files:
            local_time = self._get_file_mtime(f, local=True)
            remote_time = self._get_file_mtime(f, local=False)

            if local_time and remote_time and local_time != remote_time:
                conflicts.append({
                    'file': f,
                    'local_time': local_time,
                    'remote_time': remote_time
                })

        return conflicts

    def _sync_to_remote(self, resolve_conflicts=True):
        if not self.current_project:
            return False

        self._set_status("Checking for conflicts...", "blue")

        if resolve_conflicts:
            conflicts = self._detect_conflicts('to_remote')
            if conflicts:
                dialog = ConflictDialog(self, conflicts)
                if dialog.cancelled:
                    self._set_status("Sync cancelled", "gray")
                    return False

                # Filter out files where user chose 'remote' or 'skip'
                exclude_files = [f for f, choice in dialog.results.items() if choice != 'local']
            else:
                exclude_files = []
        else:
            exclude_files = []

        self._set_status("Syncing untracked files to remote...", "blue")

        cwd = self.current_project['local_path']
        host = self.current_project['remote_host']
        remote_path = self.current_project['remote_path']

        # Get files to sync
        files = self._get_gitignored_files(local=True)
        files = [f for f in files if f not in exclude_files]

        if not files:
            self._set_status("No untracked files to sync", "gray")
            return True

        # Create a temp file with the list
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tf:
            tf.write('\n'.join(files))
            temp_file = tf.name

        try:
            cmd = f'rsync -avz --files-from="{temp_file}" "{cwd}/" "{host}:{remote_path}/"'
            success, output = self._run_command(cmd)

            if success:
                self._set_status(f"Synced {len(files)} files to remote", "green")
                return True
            else:
                self._set_status("Sync failed", "red")
                messagebox.showerror("Error", f"Sync failed:\n{output}")
                return False
        finally:
            os.unlink(temp_file)

    def _sync_from_remote(self, resolve_conflicts=True):
        if not self.current_project:
            return False

        self._set_status("Checking for conflicts...", "blue")

        if resolve_conflicts:
            conflicts = self._detect_conflicts('from_remote')
            if conflicts:
                dialog = ConflictDialog(self, conflicts)
                if dialog.cancelled:
                    self._set_status("Sync cancelled", "gray")
                    return False

                # Filter out files where user chose 'local' or 'skip'
                exclude_files = [f for f, choice in dialog.results.items() if choice != 'remote']
            else:
                exclude_files = []
        else:
            exclude_files = []

        self._set_status("Syncing untracked files from remote...", "blue")

        cwd = self.current_project['local_path']
        host = self.current_project['remote_host']
        remote_path = self.current_project['remote_path']

        # Get files from remote
        files = self._get_gitignored_files(local=False)
        files = [f for f in files if f not in exclude_files]

        if not files:
            self._set_status("No untracked files to sync", "gray")
            return True

        # Create a temp file with the list
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tf:
            tf.write('\n'.join(files))
            temp_file = tf.name

        try:
            cmd = f'rsync -avz --files-from="{temp_file}" "{host}:{remote_path}/" "{cwd}/"'
            success, output = self._run_command(cmd)

            if success:
                self._set_status(f"Synced {len(files)} files from remote", "green")
                return True
            else:
                self._set_status("Sync failed", "red")
                messagebox.showerror("Error", f"Sync failed:\n{output}")
                return False
        finally:
            os.unlink(temp_file)

    def _full_sync(self):
        if not self.current_project:
            return

        steps = [
            ("Syncing untracked to remote", lambda: self._sync_to_remote()),
            ("Pushing to git", lambda: self._git_push()),
            ("Pulling from git", lambda: self._git_pull()),
            ("Syncing untracked from remote", lambda: self._sync_from_remote()),
        ]

        for step_name, step_func in steps:
            self._set_status(step_name + "...", "blue")
            if not step_func():
                self._set_status(f"Full sync stopped at: {step_name}", "orange")
                return

        self._set_status("Full sync complete!", "green")
        messagebox.showinfo("Success", "Full sync completed successfully!")


def main():
    app = SyncApp()
    app.mainloop()


if __name__ == "__main__":
    main()
