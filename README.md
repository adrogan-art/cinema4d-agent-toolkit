# Cinema 4D Skills (public)

Skills for working with Cinema 4D Python from [Claude Code](https://claude.com/claude-code)
and [Codex](https://openai.com/codex). They teach the assistant how to run
Cinema 4D headlessly, how to test plugins inside the real GUI, and how to build
reusable `.py` / `.pyp` tools without rediscovering the same API traps.

| Skill | Purpose |
|-------|---------|
| [`cinema4d-c4dpy`](cinema4d-c4dpy/) | Execute and verify Cinema 4D Python code headlessly with the matching `c4dpy.exe`. |
| [`cinema4d-gui-testing`](cinema4d-gui-testing/) | Run deterministic Cinema 4D Python integration tests that require the real Windows GUI and event loop. |
| [`develop-cinema4d-tools`](develop-cinema4d-tools/) | Design, implement, diagnose, and verify reusable Cinema 4D Python scripts and plugins. |

## Install

```sh
git clone https://github.com/adrogan-art/skills-public.git
cd skills-public
./install.sh
```

On Windows PowerShell:

```powershell
git clone https://github.com/adrogan-art/skills-public.git
cd skills-public
.\install.ps1
```

The installer copies each skill into the skills directory of every assistant it
finds — `~/.claude/skills` and `~/.codex/skills` — and installs nothing where
the assistant is not present. Restart the assistant afterwards.

It never overwrites an existing skill: rerun with `--force` (`-Force` in
PowerShell) if you want the repository version to replace what you already have.
A skill that is a symlink or junction is always left alone, so a linked
development checkout cannot be clobbered.

Prefer to do it by hand? A skill is just a directory containing `SKILL.md` —
copy the three folders into your assistant's skills directory yourself.

## Update

```sh
git pull
./install.sh --force
```

## Requirements

The skills assume Windows with Cinema 4D 2024 or newer installed, including its
`c4dpy.exe`. The Redshift render rules apply to installations that ship
Redshift. Nothing else is required: skills are plain Markdown instructions plus
a few helper scripts, and they contain no Cinema 4D binaries.

## What is inside a skill

```
cinema4d-c4dpy/
  SKILL.md        # entry point the assistant reads
  scripts/        # helper scripts the skill calls
  references/     # detail loaded only when a step needs it
```

`SKILL.md` starts with a YAML header whose `description` tells the assistant
when the skill applies, so skills activate on their own when a task matches.

## License and contributions

Published as-is, without warranty. Issues and pull requests are welcome, but
these skills are tuned for a specific production setup, so behaviour may be
opinionated.
