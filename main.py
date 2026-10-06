"""CLI entry point for grokforge."""
from __future__ import annotations

import datetime as _dt
import threading

from grokforge.colors import bold, dim, err, info, ok, step
from grokforge.config import (
    DEFAULT_PASSWORD, DEFAULT_THREADS, ROUTER_BASE, TEMPMAIL_PROVIDER,
)
from grokforge.router import get_router_token, _token_is_fresh
from grokforge.tempmail import available_providers
from grokforge.utils import print_safe as _print
from grokforge.xai import register_one


def _ask_int(prompt: str, default: int) -> int:
    try:
        raw = input(prompt).strip()
        return int(raw) if raw else default
    except (ValueError, EOFError):
        return default


def main() -> int:
    # ---- sanity check temp mail provider -----------------------
    try:
        _ = available_providers()  # triggers registry import
        from grokforge.tempmail import get_provider
        get_provider()  # will raise if provider name is wrong
    except Exception as e:
        _print(f"{err('[ERR]')} temp mail provider error: {e}")
        _print(f"{dim('  -> TEMPMAIL_PROVIDER=' + TEMPMAIL_PROVIDER)}")
        return 1

    # ---- ensure 9router token is ready -------------------------
    router_enabled = True
    token = get_router_token()
    if not token or not _token_is_fresh(token):
        _print(f"{err('[ERR]')} failed to obtain a valid 9router auth_token")
        _print(f"{dim('  -> make sure 9router is running at ' + ROUTER_BASE)}")
        _print(f"{dim('  -> and that ROUTER_PASSWORD in .env is correct')}")
        return 1
    _print(f"{ok('[OK]')} 9router auth_token ready")
    _print(f"{info('[i]')} temp mail provider: {TEMPMAIL_PROVIDER}")

    # ---- user input --------------------------------------------
    count   = max(1, _ask_int(f"{info('?')} How many accounts? ", 1))
    threads = max(1, _ask_int(f"{info('?')} Threads? [{DEFAULT_THREADS}] ", DEFAULT_THREADS))
    threads = min(threads, count)

    proxy = None
    try:
        if input(f"{info('?')} Proxy? (y/n) ").strip().lower() == "y":
            proxy = input(f"{info('?')} Proxy URL: ").strip() or None
    except EOFError:
        pass

    password = DEFAULT_PASSWORD

    _print(f"\n {step('>>')} {bold(str(count))} accounts | "
           f"{bold(str(threads))} threads | headless")
    _print(dim("=" * 46))

    # ---- run workers -------------------------------------------
    results = {"ok": 0, "fail": 0}
    results_lock = threading.Lock()
    start_time = _dt.datetime.now()

    def worker(worker_id: int):
        success = register_one(
            password=password,
            proxy=proxy,
            router=router_enabled,
            router_base=ROUTER_BASE,
            worker_id=worker_id,
        )
        with results_lock:
            results["ok" if success else "fail"] += 1

    pending = list(range(1, count + 1))
    while pending:
        batch = pending[:threads]
        pending = pending[threads:]
        running = [threading.Thread(target=worker, args=(w,), daemon=True) for w in batch]
        for t in running:
            t.start()
        for t in running:
            t.join()

    # ---- summary -----------------------------------------------
    elapsed = int((_dt.datetime.now() - start_time).total_seconds())
    minutes, seconds = divmod(elapsed, 60)
    _print(f"\n{dim('=' * 46)}")
    _print(f" {ok('[OK]')} Success : {ok(str(results['ok']))}")
    if results["fail"]:
        _print(f" {err('[ERR]')} Failed  : {err(str(results['fail']))}")
    _print(f" {info('[i]')} Time    : {bold(f'{minutes}m {seconds}s')}")
    _print(f" {step('>>')} accounts.txt")
    return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())