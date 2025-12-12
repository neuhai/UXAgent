import asyncio
import json
import logging
import pathlib
import shutil
import traceback
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional

from dotenv import load_dotenv
from hydra import compose, initialize, initialize_config_dir
from omegaconf import DictConfig

from ..agent import context, gpt
from ..executor.env import WebAgentEnv  # Playwright env
from .model import AgentPolicy  # noqa
from .cost_calculator import format_cost

log = logging.getLogger("simulated_web_agent.main.experiment")
logging.basicConfig(level=logging.INFO)


def _generate_token_report(trace_dir: pathlib.Path) -> dict:
    """
    Generate a token and cost report from api_trace files.

    Args:
        trace_dir: Directory containing api_trace files

    Returns:
        Dictionary with token and cost statistics
    """
    api_trace_dir = trace_dir / "api_trace"
    if not api_trace_dir.exists():
        return {}

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    total_cost = 0.0
    api_calls_count = 0
    method_counts = {}

    # Read all api_trace files
    for api_trace_file in sorted(api_trace_dir.glob("api_trace_*.json")):
        try:
            with open(api_trace_file, "r") as f:
                data = json.load(f)
                api_calls_count += 1

                # Count by method
                method = data.get("method_name", "unknown")
                method_counts[method] = method_counts.get(method, 0) + 1

                # Sum tokens
                usage = data.get("usage")
                if usage:
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    total_prompt_tokens += prompt_tokens
                    total_completion_tokens += completion_tokens
                    total_tokens += usage.get("total_tokens", 0)

                # Sum costs
                cost = data.get("cost", 0.0)
                if cost:
                    total_cost += cost
        except Exception as e:
            log.warning(f"Error reading {api_trace_file}: {e}")

    report = {
        "api_calls": api_calls_count,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "total_cost_formatted": format_cost(total_cost),
        "method_calls": method_counts,
    }

    return report


def _save_token_report(trace_dir: pathlib.Path, report: dict) -> None:
    """
    Save token report to a JSON file and print summary.

    Args:
        trace_dir: Directory to save the report
        report: Token report dictionary
    """
    if not report:
        return

    # Save as JSON
    report_file = trace_dir / "token_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    log.info("=" * 60)
    log.info("TOKEN AND COST REPORT")
    log.info("=" * 60)
    log.info(f"Total API Calls: {report['api_calls']}")
    log.info(f"Total Tokens Used: {report['total_tokens']:,}")
    log.info(f"  - Prompt Tokens: {report['total_prompt_tokens']:,}")
    log.info(f"  - Completion Tokens: {report['total_completion_tokens']:,}")
    log.info(f"Total Cost: {report['total_cost_formatted']}")
    log.info("")
    log.info("API Calls by Method:")
    for method, count in sorted(report['method_calls'].items()):
        log.info(f"  - {method}: {count} calls")
    log.info("=" * 60)


async def _run_for_persona_and_intent(
    cfg: DictConfig,
    persona_info: Dict,
    start_url: str,
    max_steps: int,
    wait_for_login: bool = False,
    env_setup_hook: Callable = None,
    env_wait_hook: Callable = None,
):
    persona = persona_info["persona"]
    intent = persona_info["intent"]
    log.info(
        f"\n=== persona (first 200 chars) ===\n{persona[:200]}...\n=== intent ===\n{intent}"
    )
    run_uid = uuid.uuid4().hex[:8]

    task_to_use = {
        "sites": ["shopping"],
        "task_id": 1,
        "require_login": False,
        "start_url": start_url,
        "intent": intent or "Interactive testing session",
    }

    run_name = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{uuid.uuid4().hex[:4]}"
    base_dir = pathlib.Path().resolve()
    trace_dir = base_dir / "runs" / run_name
    # trace_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "runs" / run_name / "simp_html").mkdir(parents=True, exist_ok=True)
    (base_dir / "runs" / run_name / "raw_html").mkdir(parents=True, exist_ok=True)
    (base_dir / "runs" / run_name / "api_trace").mkdir(parents=True, exist_ok=True)
    (base_dir / "runs" / run_name / "screenshot").mkdir(parents=True, exist_ok=True)
    (base_dir / "runs" / run_name / "observation_trace").mkdir(
        parents=True, exist_ok=True
    )
    # save persona and intent
    (base_dir / "runs" / run_name / "basic_info.json").write_text(
        json.dumps(persona_info)
    )
    context.run_path.set(trace_dir)
    steps_taken = 0

    async def before_action_hook():
        if cfg.environment.recording.enabled:
            return
        # input()
        # save screenshot
        await env.page.screenshot(
            path=trace_dir / "screenshot" / f"screenshot_{steps_taken}_full_page.png",
            full_page=True,
        )
        await env.page.screenshot(
            path=trace_dir / "screenshot" / f"screenshot_{steps_taken}.png",
        )
        # get scroll top position
        scroll_top = await env.page.evaluate("window.scrollY")
        with open(trace_dir / "screenshot" / f"scroll_top_{steps_taken}.txt", "w") as f:
            f.write(
                str(
                    scroll_top
                    * cfg.environment.browser.context_options.device_scale_factor
                )
            )

    env = WebAgentEnv(
        cfg.environment, before_action_hook=before_action_hook, wait_hook=env_wait_hook
    )

    async def clear_cart(env):
        page = await env.context.new_page()

        # Initial navigation
        await page.goto(
            "https://www.amazon.com/fmc/ssd-storefront?ref_=nav_cs_SSD_nav_storefront",
            wait_until="networkidle",
        )

        while True:
            # Find all delete buttons currently visible
            delete_buttons = page.locator('button[data-action="a-stepper-decrement"]')
            count = await delete_buttons.count()

            print(f"Found {count} delete buttons")

            if count == 0:
                print("No more items to delete.")
                break

            # Always click the FIRST button, then reload the page
            btn = delete_buttons.nth(0)
            await btn.click()
            await env.observation()
        await page.close()

    log.info(f"[{run_uid}] env created")
    try:
        policy = AgentPolicy(persona, intent)
        print("setting up env with headless = " + str(cfg.environment.browser.launch_options.headless))
        await env.setup(task_to_use, headless=cfg.environment.browser.launch_options.headless)

        if wait_for_login:
            env.debug_pause()

        # await clear_cart(env)

        # Execute any custom setup actions if specified
        if env_setup_hook:
            await env_setup_hook(env)
        obs = await env.observation()

        log.info("Initial observation ready")

        action_trace = []
        while steps_taken < max_steps:
            with open(trace_dir / "observation_trace.jsonl", "a") as f:
                json.dump(obs, f)
            if obs.get("tabs"):
                current_url = obs["tabs"][0].get("url")
                print("Current url:", current_url)
            with open(
                trace_dir / "simp_html" / f"simp_html_{steps_taken}.html", "w"
            ) as f:
                f.write(obs["html"])
            with open(
                trace_dir / "raw_html" / f"raw_html_{steps_taken}.html", "w"
            ) as f:
                f.write(await env.page.content())

            # Use our policy to determine the action for this step from the environment
            action = await policy.forward(env)
            action_trace.append(action)
            with open(trace_dir / "action_trace.json", "w") as f:
                json.dump(action_trace, f, indent=2)
            with open(
                trace_dir
                / "observation_trace"
                / f"observation_trace_{steps_taken}.txt",
                "w",
            ) as f:
                f.write(policy.agent.observation)
            # save memory trace
            with open(trace_dir / "memory_trace.json", "w") as f:
                json.dump(policy.agent.memory.memories, f)
            print(f"Taking action {action}")
            print(f"Action: {steps_taken + 1} out of {max_steps}")

            # Update and display real-time token statistics
            token_report = _generate_token_report(trace_dir)
            if token_report:
                print(f"[Token Stats] Total Calls: {token_report['api_calls']}, "
                      f"Tokens: {token_report['total_tokens']:,}, "
                      f"Cost: {token_report['total_cost_formatted']}")
                # Save report immediately so it's available even if interrupted
                _save_token_report(trace_dir, token_report)

            obs = await env.step(action)
            steps_taken += 1

            if obs.get("terminated"):
                break

        log.info(
            f"Finished persona run: terminated={obs.get('terminated')}, "
            f"score={obs.get('score')}, steps={steps_taken}"
        )

        # ---- save final memory trace ----
        final_memories_str = policy.get_formatted_memories()

        trace_file = trace_dir / f"{run_name}.txt"
        trace_file.write_text(final_memories_str, encoding="utf-8")

        log.info(f"Saved memory trace to {trace_file}")

        # ---- generate and save final token/cost report ----
        token_report = _generate_token_report(trace_dir)
        _save_token_report(trace_dir, token_report)
        print("\n" + "=" * 60)
        print("FINAL TOKEN AND COST REPORT")
        print("=" * 60)
        if token_report:
            print(f"Total API Calls: {token_report['api_calls']}")
            print(f"Total Tokens: {token_report['total_tokens']:,}")
            print(f"  - Prompt Tokens: {token_report['total_prompt_tokens']:,}")
            print(f"  - Completion Tokens: {token_report['total_completion_tokens']:,}")
            print(f"Total Cost: {token_report['total_cost_formatted']}")
        print("=" * 60 + "\n")

    except Exception:
        err = traceback.format_exc()
        print(err)
        try:
            (policy.run_path / "error.txt").write_text(err)  # type: ignore[attr-defined]
        except Exception:
            pass
        # Still generate report even if there was an error
        try:
            token_report = _generate_token_report(trace_dir)
            if token_report:
                print("\n" + "=" * 60)
                print("PARTIAL TOKEN AND COST REPORT (before error)")
                print("=" * 60)
                print(f"Total API Calls: {token_report['api_calls']}")
                print(f"Total Tokens: {token_report['total_tokens']:,}")
                print(f"  - Prompt Tokens: {token_report['total_prompt_tokens']:,}")
                print(f"  - Completion Tokens: {token_report['total_completion_tokens']:,}")
                print(f"Total Cost: {token_report['total_cost_formatted']}")
                print("=" * 60 + "\n")
                _save_token_report(trace_dir, token_report)
        except Exception:
            pass
    finally:
        try:
            log.info(f"[{run_uid}] closing env...")
            await asyncio.wait_for(asyncio.shield(env.close()), timeout=10)
            log.info(f"[{run_uid}] env.close() completed")
        except Exception as e:
            log.exception(f"[{run_uid}] env.close() raised: {e!r}")
    return trace_dir

def _load_cfg(config_name: str = "base"):
    here = pathlib.Path(__file__).resolve().parent
    conf_dir = here.parents[2] / "conf"
    with initialize_config_dir(version_base=None, config_dir=str(conf_dir)):
        cfg = compose(config_name=config_name)
    return cfg

async def experiment_async(
    agents: List[Dict[str, str]],
    start_url: str,
    max_steps: int,
    *,
    headless=False,
    config_name: str = "base",
    config_path: str = ".",
    concurrency: int = 4,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> None:
    cfg = _load_cfg(config_name=config_name)
    if concurrency:
        cfg.environment.browser.user_data_dir = None
    gpt.provider = cfg.llm_provider
    print("llm provider: " + cfg.llm_provider)

    sem = asyncio.Semaphore(concurrency)

    total = len(agents)
    done = 0
    lock = asyncio.Lock()  # protect shared counter in async context

    async def run_one(entry: Dict[str, str]):
        nonlocal done
        # persona = (entry.get("persona") or "").strip()
        # intent = (entry.get("intent") or "").strip()
        # if not persona or not intent:
        #     log.warning("Skipping agent: missing persona or intent")
        #     return
        async with sem:
            trace_dir = await _run_for_persona_and_intent(
                cfg=cfg,
                persona_info=entry,
                start_url=start_url,
                max_steps=max_steps,
            )

        # --- progress tick ---
        async with lock:
            done += 1
            if on_progress:
                try:
                    on_progress(done, total)
                except Exception:
                    pass
        return trace_dir

    tasks = [asyncio.create_task(run_one(e)) for e in agents]
    # This await is the "barrier": it doesn't return until ALL experiments finish
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            log.exception("A session failed", exc_info=r)
    return results
