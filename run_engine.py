"""Launch the local WiSense OS engine API.

This is intentionally a thin launcher. The engine does not invoke a model at
startup; it only constructs durable state and waits for task requests.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from wisense_os.bootstrap import create_default_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the WiSense OS local engine")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--state-dir", type=Path, default=None)
    args = parser.parse_args()

    app = create_default_app(args.state_dir)
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
