#!/usr/bin/env python
# QA: Sync env examples to keep sample aligned with example

from pathlib import Path


def main() -> None:
    src = Path("backend/.env.example")
    dsts = [Path("backend/.env.sample")]
    for dst in dsts:
        if src.exists():
            header = "# QA: deprecated alias of .env.example – kept for compatibility\n"
            dst.write_text(header + src.read_text(), encoding="utf-8")
            print(f"Synced {dst} from {src}")


if __name__ == "__main__":
    main()
