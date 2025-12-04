#!/usr/bin/env python3
"""
COPR Build Log Monitor - Stream build logs in real-time
"""

import time
import argparse
import gzip
from typing import Optional, List, Tuple
import httpx
from rich.console import Console


class COPRMonitor:
    COLORS = ["cyan", "magenta", "green", "yellow", "blue", "red"]
    
    def __init__(self, build_id: str, url: Optional[str] = None):
        self.build_id = build_id
        self.url = url
        self.console = Console()
        self.positions = {}  # Track how much we've read per log source
        self.colors = {}  # Color per chroot
        
    def fetch_build_info(self):
        """Get build details from COPR API."""
        api_url = f"https://copr.fedorainfracloud.org/api_3/build/{self.build_id}"
        try:
            response = httpx.get(api_url, timeout=10, follow_redirects=True)
            if response.status_code == 200:
                data = response.json()
                return data.get('ownername'), data.get('projectname'), data.get('chroots', [])
        except Exception as e:
            self.console.print(f"[red]API error: {e}[/red]")
        return None, None, []
    
    def parse_url(self):
        """Extract info from URL if provided."""
        parts = self.url.split('/')
        try:
            idx = parts.index('results')
            return parts[idx + 1], parts[idx + 2], [parts[idx + 3]]
        except (ValueError, IndexError):
            return None, None, []
    
    def build_log_sources(self, owner: str, project: str, chroots: List[str]) -> List[Tuple[str, str, str]]:
        """
        Build list of all log sources to monitor.
        Returns list of (source_name, url_base, log_type) tuples.
        """
        sources = []
        
        # SRPM build logs
        sources.append((
            "srpm/builder-live",
            f"https://download.copr.fedorainfracloud.org/results/{owner}/{project}/srpm-builds/{self.build_id}/builder-live.log",
            "srpm"
        ))
        sources.append((
            "srpm/backend",
            f"https://download.copr.fedorainfracloud.org/results/{owner}/{project}/srpm-builds/{self.build_id}/backend.log",
            "srpm"
        ))
        sources.append((
            "srpm/dist-git",
            f"https://copr-dist-git.fedorainfracloud.org/per-task-logs/{self.build_id}.log",
            "srpm"
        ))
        
        # RPM build logs for each chroot
        for chroot in chroots:
            sources.append((
                f"{chroot}/builder-live",
                f"https://download.copr.fedorainfracloud.org/results/{owner}/{project}/{chroot}/0{self.build_id}-{project}/builder-live.log",
                "rpm"
            ))
            sources.append((
                f"{chroot}/backend",
                f"https://download.copr.fedorainfracloud.org/results/{owner}/{project}/{chroot}/0{self.build_id}-{project}/backend.log",
                "rpm"
            ))
        
        return sources
    
    def fetch_log(self, url_base: str) -> Optional[str]:
        """
        Fetch log content. Try uncompressed first, then .gz.
        """
        for url in [url_base, url_base + ".gz"]:
            try:
                response = httpx.get(url, timeout=10, follow_redirects=True)
                if response.status_code != 200:
                    continue
                
                # Try to decompress if it's gzipped
                try:
                    return gzip.decompress(response.content).decode('utf-8', errors='replace')
                except gzip.BadGzipFile:
                    return response.content.decode('utf-8', errors='replace')
            except Exception:
                continue
        
        return None
    
    def get_source_color(self, source_name: str) -> str:
        """Assign consistent color to each source."""
        # Extract chroot/category from source name
        category = source_name.split('/')[0]
        if category not in self.colors:
            self.colors[category] = self.COLORS[len(self.colors) % len(self.COLORS)]
        return self.colors[category]
    
    def colorize_line(self, line: str) -> str:
        """Add color to log lines based on content."""
        line_upper = line.upper()
        if "ERROR" in line_upper or "FAILED" in line_upper:
            return f"[red]{line}[/red]"
        elif "WARNING" in line_upper or "WARN" in line_upper:
            return f"[yellow]{line}[/yellow]"
        elif "SUCCESS" in line_upper or "COMPLETE" in line_upper or "FINISHED" in line_upper:
            return f"[green]{line}[/green]"
        return line
    
    def print_line(self, source_name: str, line: str):
        """Print a log line with source prefix."""
        if not line.strip():
            return
        
        timestamp = time.strftime("%H:%M:%S")
        colored_line = self.colorize_line(line)
        color = self.get_source_color(source_name)
        
        # Format source name with fixed width for alignment
        self.console.print(f"[dim]{timestamp}[/dim] [{color}]{source_name:30}[/{color}] {colored_line}")
    
    def monitor_source(self, source_name: str, url_base: str) -> bool:
        """
        Fetch and print new log lines for a source.
        Returns True if there's activity, False if stalled.
        """
        content = self.fetch_log(url_base)
        
        if content:
            last_pos = self.positions.get(source_name, 0)
            
            # Only print new content
            if len(content) > last_pos:
                new_content = content[last_pos:]
                for line in new_content.split('\n'):
                    self.print_line(source_name, line)
                
                self.positions[source_name] = len(content)
                return True
            elif last_pos > 0:
                # Has content but no change
                return False
        
        # No log file found yet (normal for logs that haven't started)
        return True
    
    def run(self):
        """Main monitoring loop."""
        # Get build information
        if self.url:
            owner, project, chroots = self.parse_url()
        else:
            owner, project, chroots = self.fetch_build_info()
        
        if not owner or not project:
            self.console.print("[red]Error: Could not get build information[/red]")
            return
        
        # Print header
        self.console.print(f"\n[bold]COPR Build Monitor[/bold]")
        self.console.print(f"Build ID:  {self.build_id}")
        self.console.print(f"Owner:     {owner}")
        self.console.print(f"Project:   {project}")
        if chroots:
            self.console.print(f"Chroots:   {', '.join(chroots)}")
        self.console.print()
        
        # Get all log sources
        sources = self.build_log_sources(owner, project, chroots)
        stalled_count = {name: 0 for name, _, _ in sources}
        
        try:
            while True:
                all_stalled = True
                
                for source_name, url_base, log_type in sources:
                    has_activity = self.monitor_source(source_name, url_base)
                    
                    if has_activity:
                        stalled_count[source_name] = 0
                        all_stalled = False
                    else:
                        stalled_count[source_name] += 1
                        # Consider stalled after 30 seconds (15 checks at 2s interval)
                        if stalled_count[source_name] < 15:
                            all_stalled = False
                
                if all_stalled:
                    self.console.print(f"\n[green]✓ All builds complete[/green]")
                    break
                
                time.sleep(2)
                
        except KeyboardInterrupt:
            self.console.print(f"\n[yellow]Stopped by user[/yellow]")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor COPR build logs in real-time",
        epilog="""
Examples:
  %(prog)s 09857949
  %(prog)s --url https://download.copr.fedorainfracloud.org/results/owner/project/chroot/09857949-project/builder-live.log
  
This monitors all log sources:
  - SRPM: builder-live.log, backend.log, dist-git log
  - RPM: builder-live.log and backend.log for each chroot
        """
    )
    
    parser.add_argument(
        "build_id",
        help="COPR build ID"
    )
    
    parser.add_argument(
        "--url",
        help="Direct log URL (optional, will use API if not provided)"
    )
    
    args = parser.parse_args()
    
    monitor = COPRMonitor(args.build_id, args.url)
    monitor.run()


if __name__ == "__main__":
    main()
