"""互換エントリ: kaburadar.cli.publish へ委譲。"""

from kaburadar3.cli.publish import main

if __name__ == "__main__":
    raise SystemExit(main())
