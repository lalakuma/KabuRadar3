"""ローカルスケジュール実行（正確な時刻向け）."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import time

from kaburadar3.scheduling.slots import LOCAL_SLOTS, load_state, mark_slot_done, slots_due
from kaburadar3.settings.paths import LOG_DIR, PROJECT_ROOT
from kaburadar3.settings.scripts import run_script


def _setup_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("kaburadar3.scheduling")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    fh = logging.FileHandler(LOG_DIR / "local_scheduler.log", encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger


def _run_slot(slot_id: str, logger: logging.Logger, push: bool = False) -> int:
    slot = next((s for s in LOCAL_SLOTS if s.slot_id == slot_id), None)
    if slot is None:
        logger.error("Unknown slot: %s", slot_id)
        return 2

    os.environ["KABURADAR_CONFIG"] = str((PROJECT_ROOT / slot.config).resolve())
    logger.info("Run slot %s (%s) config=%s", slot.slot_id, slot.label, slot.config)

    rc = run_script(slot.script)
    if rc != 0:
        logger.error("Slot %s failed with code %s", slot.slot_id, rc)
        return rc

    if push:
        rc = run_script("publish", "--push")
        if rc != 0:
            logger.error("publish --push failed with code %s", rc)
            return rc

    mark_slot_done(slot.slot_id)
    logger.info("Slot %s completed", slot.slot_id)
    return 0


def run_due(now: dt.datetime | None = None, push: bool = False) -> int:
    logger = _setup_logger()
    now = now or dt.datetime.now()
    due = slots_due(now)
    if not due:
        logger.debug("No local slot due at %s", now.isoformat())
        return 0

    rc = 0
    for slot in due:
        slot_rc = _run_slot(slot.slot_id, logger, push=push)
        if slot_rc != 0:
            rc = slot_rc
    return rc


def run_loop(interval_sec: int = 30, push: bool = False) -> None:
    logger = _setup_logger()
    logger.info("Local scheduler loop started (interval=%ss)", interval_sec)
    try:
        while True:
            try:
                run_due(push=push)
            except Exception:
                logger.exception("Local scheduler iteration failed")
            time.sleep(max(5, interval_sec))
    except KeyboardInterrupt:
        logger.info("Local scheduler stopped")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KabuRadar3 ローカルスケジューラ")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="30秒ごとにスロットを監視して自動実行（常駐）",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="--loop 時の監視間隔（秒）",
    )
    parser.add_argument(
        "--once",
        metavar="SLOT_ID",
        help="指定スロットを即実行（例: hi_1130, lo_1500, lo_1600）",
    )
    parser.add_argument(
        "--due",
        action="store_true",
        help="現在時刻に該当するスロットがあれば1回実行",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="登録スロット一覧を表示",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="本日の実行済みスロットを表示",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="実行後に docs/data.json を git push する",
    )
    args = parser.parse_args(argv)
    logger = _setup_logger()

    if args.list:
        for slot in LOCAL_SLOTS:
            print(f"{slot.slot_id}\t{slot.at.strftime('%H:%M')}\t{slot.label}\t{slot.script}.bat")
        return 0

    if args.status:
        state = load_state()
        day_key = dt.date.today().isoformat()
        done = state.get(day_key, [])
        print(f"date={day_key} done={done or '[]'}")
        return 0

    if args.once:
        return _run_slot(args.once, logger, push=args.push)

    if args.loop:
        run_loop(interval_sec=args.interval, push=args.push)
        return 0

    if args.due:
        return run_due(push=args.push)

    logger.info("No action. Use --due, --once, --loop, or --list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
