# fuzzytail 🦊

Follow COPR build logs in your terminal in real-time.

## Installation

```bash
# Using pip
pip install fuzzytail

# Using uv
uv pip install fuzzytail

# From source
git clone https://github.com/r0x0d/fuzzytail
cd fuzzytail
pip install -e .
```

## Usage

### Watch a Project

The simplest way to use fuzzytail is to watch a COPR project for builds:

```bash
# Watch all builds in a project
fuzzytail owner/project

# Filter by package
fuzzytail owner/project --package broot

# Filter by chroot
fuzzytail owner/project --chroot fedora-43-x86_64

# Watch a specific build
fuzzytail owner/project --build 12345678
```

### Log Filtering

Control which logs to display:

```bash
# Only show SRPM build logs
fuzzytail owner/project --srpm-only

# Only show RPM build logs
fuzzytail owner/project --rpm-only

# Only show builder-live logs
fuzzytail owner/project --builder-live

# Only show backend logs
fuzzytail owner/project --backend

# Skip backend logs (show only builder-live)
fuzzytail owner/project --skip-backend

# Skip import (dist-git) logs
fuzzytail owner/project --skip-import
```

### Commands

#### `fuzzytail <project>` (default)

Watch a project for builds and stream their logs.

```bash
fuzzytail owner/project [OPTIONS]

Options:
  -p, --package TEXT     Filter by package name
  -c, --chroot TEXT      Filter by chroot (e.g., 'fedora-43-x86_64')
  -b, --build INT        Watch a specific build ID
  --srpm-only            Only show SRPM build logs
  --rpm-only             Only show RPM build logs
  -l, --builder-live     Only show builder-live logs
  -B, --backend          Only show backend logs
  --skip-backend         Skip backend logs (show only builder-live)
  --skip-import          Skip import (dist-git) logs
  -i, --interval FLOAT   Poll interval in seconds (default: 2.0)
```

#### `fuzzytail watch <project>`

Continuously monitor a project for new builds.

```bash
fuzzytail watch owner/project [OPTIONS]

Options:
  -p, --package TEXT     Filter by package name
  -c, --chroot TEXT      Filter by chroot
  --srpm                 Include SRPM logs (default: true)
  --rpm                  Include RPM logs (default: true)
  -l, --builder-live     Include builder-live logs (default: true)
  -B, --backend          Include backend logs (default: true)
  --skip-backend         Skip backend logs (show only builder-live)
  --skip-import          Skip import (dist-git) logs
  -i, --interval FLOAT   Poll interval in seconds (default: 5.0)
```

#### `fuzzytail logs <project>`

Fetch and display logs for a build. Shows recent builds and prompts for selection if no build ID is specified.

```bash
fuzzytail logs owner/project [OPTIONS]

Options:
  -b, --build INT        Specific build ID (skips selection)
  -p, --package TEXT     Filter by package name
  -c, --chroot TEXT      Filter by chroot
  -t, --type TEXT        Log type: 'import', 'builder-live', or 'backend'
  --srpm-only            Only show SRPM logs
  --rpm-only             Only show RPM logs
  --skip-backend         Skip backend logs (show only builder-live)
  --skip-import          Skip import (dist-git) logs
  -f, --follow           Follow logs in real-time
  -i, --interval FLOAT   Poll interval when following (default: 2.0)
  -n, --limit INT        Number of builds to show in selection (default: 10)
```

#### `fuzzytail builds <project>`

List builds for a COPR project.

```bash
fuzzytail builds owner/project [OPTIONS]

Options:
  -p, --package TEXT     Filter by package name
  -s, --status TEXT      Filter by status (running, pending, succeeded, failed)
  -n, --limit INT        Maximum builds to show (default: 10)
  -v, --verbose          Show detailed build information
```

## Log Types

Fuzzytail supports all COPR log types:

| Log Type | Description |
|----------|-------------|
| `import` | Import/dist-git logs for package source |
| `builder-live` | Real-time build output from mock |
| `backend` | COPR backend orchestration logs |

## Build Sources

| Source | Description |
|--------|-------------|
| SRPM | Source RPM build logs |
| RPM | Binary RPM build logs (per chroot) |

## Examples

### Watch a running build with all logs

```bash
fuzzytail r0x0d/my-project --build 09782941
```

### Monitor only the builder-live logs for x86_64

```bash
fuzzytail r0x0d/my-project --chroot fedora-43-x86_64 --builder-live
```

### Watch without backend logs

```bash
fuzzytail r0x0d/my-project --skip-backend
```

### List recent failed builds

```bash
fuzzytail builds r0x0d/my-project --status failed
```

### View logs for a project (with selection)

```bash
fuzzytail logs owner/project
```

### Follow logs for a specific build

```bash
fuzzytail logs owner/project --build 09782941 --follow
```

### View only import logs

```bash
fuzzytail logs owner/project --type import
```

## Requirements

- Python 3.10+
- COPR account (for authenticated operations, optional)

## Credits

This project was created by:

- **Rodolfo Olivieri** ([@r0x0d](https://github.com/r0x0d)) - Creator and maintainer
- **Claude** (Anthropic) - AI pair programming assistant

## License

MIT License - see LICENSE file for details.
