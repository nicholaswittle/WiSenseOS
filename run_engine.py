"""Launch the local WiSense OS engine API.

This is intentionally a thin launcher. The engine does not invoke a model at
startup; it only constructs durable state and waits for task requests.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

from wisense_os.bootstrap import (
    _default_state_dir,
    create_default_app,
    issue_launch_token,
)
from wisense_os.model_adapter import OllamaChatAdapter


def is_port_available(port: int) -> bool:
    """Check if local port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the WiSense OS local engine")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--state-dir", type=Path, default=None)
    args = parser.parse_args()

    if not is_port_available(args.port):
        print(f"Port {args.port} is already in use by WiSense Engine. Server may already be active at http://127.0.0.1:{args.port}.")
        sys.exit(1)

    state_dir = args.state_dir or _default_state_dir()
    token = issue_launch_token(state_dir)
    adapter = OllamaChatAdapter()
    app = create_default_app(
        state_dir,
        model_adapter=adapter,
        runtime_model_names=adapter.available_models(),
        auth_token=token,
    )
    print(f"WiSense Engine on http://127.0.0.1:{args.port} -- token at {state_dir / 'engine_token'}")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
