"""後方互換: scheduler → scheduling."""

from kaburadar3.scheduling.launcher import run_due as run_for_now

__all__ = ["run_for_now"]

if __name__ == "__main__":
    from kaburadar3.scheduling.launcher import main
    raise SystemExit(main())
