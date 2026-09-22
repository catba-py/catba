"""React SSR worker: persistent Node process for server-side rendering.

Python owns the Node worker process. The lifecycle is:

  start()    -> Python starts the Node process, loads the SSR bundle
  render()   -> Python sends a render request, reads the HTML response
  stop()     -> Python terminates the Node process, closes all pipes

The worker communicates via newline-delimited JSON on stdin/stdout:

  Request:  {"id": 1, "page": "/", "props": {...}}
  Response: {"id": 1, "html": "..."}
  Error:    {"id": 1, "error": "..."}

Ownership:
  - who starts it: SSRWorker.start()
  - who owns it: the SSRWorker instance (holds subprocess.Popen)
  - who writes to it: SSRWorker.render() writes to proc.stdin
  - who reads from it: SSRWorker.render() reads from proc.stdout
  - who terminates it: SSRWorker.stop()
  - when it terminates: on shutdown, on error, on worker crash

No Python request objects are passed to the worker. Only JSON-serializable
props cross the boundary. Once a request completes, Python request objects
are eligible for cleanup immediately.
"""

import json
import os
import subprocess

from catba.frontend import find_node, find_ssr_bundle


class SSRError(Exception):
    """An SSR rendering or worker error."""


def _find_worker_script():
    """Find the ssr-worker.mjs script bundled with the catba package."""
    return os.path.join(os.path.dirname(__file__), "ssr-worker.mjs")


class SSRWorker:
    """A persistent Node process that renders React pages."""

    def __init__(self, project_root):
        self.project_root = project_root
        self.proc = None
        self._next_id = 1
        self.client_bundle_url = None  # set by start() if client bundle exists

    def start(self):
        """Start the Node SSR worker.

        Finds the SSR bundle, starts the Node process, and waits for the
        ready signal. Also discovers the client bundle URL for hydration.
        Raises SSRError on failure.
        """
        node = find_node()
        if not node:
            raise SSRError("Node.js is required for SSR but was not found.")

        bundle = find_ssr_bundle(self.project_root)
        if not bundle:
            raise SSRError(
                "SSR bundle not found. Run a frontend build first."
            )

        worker = _find_worker_script()
        if not os.path.isfile(worker):
            raise SSRError("SSR worker script not found.")

        self.proc = subprocess.Popen(
            [node, worker, bundle],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=self.project_root,
        )

        # Wait for the ready signal.
        ready_line = self.proc.stdout.readline()
        if not ready_line:
            err = self.proc.stderr.read()
            raise SSRError("SSR worker failed to start: " + err)
        try:
            ready = json.loads(ready_line.strip())
        except json.JSONDecodeError:
            raise SSRError("SSR worker sent invalid ready signal: " + ready_line)
        if not ready.get("ready"):
            raise SSRError("SSR worker not ready: " + str(ready))

        # Discover the client bundle URL for hydration.
        from catba.assets import get_client_bundle_url
        self.client_bundle_url = get_client_bundle_url(self.project_root)

    def render(self, page_id, props):
        """Render a page to HTML.

        Sends a render request to the Node worker and returns the HTML
        string. Raises SSRError on worker failure or rendering error.
        """
        if not self.proc or self.proc.poll() is not None:
            raise SSRError("SSR worker is not running.")

        req_id = self._next_id
        self._next_id += 1

        request = json.dumps({"id": req_id, "page": page_id, "props": props})
        try:
            self.proc.stdin.write(request + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            raise SSRError("SSR worker pipe closed.")

        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read()
            raise SSRError("SSR worker returned no response: " + err)

        try:
            resp = json.loads(line.strip())
        except json.JSONDecodeError:
            raise SSRError("SSR worker sent invalid response: " + line)

        if resp.get("error"):
            raise SSRError("SSR render error: " + resp["error"])

        html = resp.get("html")
        if html is None:
            raise SSRError("SSR worker response missing html field.")

        return html

    def stop(self):
        """Terminate the Node worker and close all pipes.

        Safe to call multiple times. No child process is left orphaned.
        """
        if self.proc:
            try:
                if self.proc.poll() is None:
                    self.proc.stdin.close()
                    try:
                        self.proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                        self.proc.wait()
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            finally:
                for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                    try:
                        stream.close()
                    except Exception:
                        pass
                self.proc = None

    def is_running(self):
        """Return True if the worker process is alive."""
        return self.proc is not None and self.proc.poll() is None
