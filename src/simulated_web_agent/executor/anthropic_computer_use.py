import base64
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, List

import anthropic
from dotenv import load_dotenv
from pathlib import Path
from .dom_llm_actions_env import BrowserbaseConnector


logger = logging.getLogger(__name__)


class AnthropicComputerUseRunner:
    """
    Runs a high-level goal using Anthropic's native Computer Use (beta) in Claude.

    Notes:
    - Requires ANTHROPIC_API_KEY in the environment.
    - Uses beta Computer Use tool via anthropic SDK. This executes in Anthropic's sandbox,
      not Browserbase.
    """

    def __init__(self, model: Optional[str] = None):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            # Attempt to load from project-level .env
            try:
                project_root = Path(__file__).resolve().parents[3]
                dotenv_path = project_root / ".env"
                load_dotenv(dotenv_path=dotenv_path, override=False)
            except Exception:
                pass
            api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            # Try explicit path ./.env as last resort
            try:
                dotenv_path = os.path.join(os.getcwd(), ".env")
                if os.path.exists(dotenv_path):
                    load_dotenv(dotenv_path=dotenv_path, override=False)
            except Exception:
                pass
            api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for Anthropic Computer Use.")
        self.client = anthropic.Anthropic(api_key=api_key)
        # Prefer explicit model via env/argument; default to Claude Sonnet 4 sample from docs
        self.model = model or os.getenv("ANTHROPIC_COMPUTER_USE_MODEL") or "claude-sonnet-4-20250514"

    def run(self, persona: str, goal: str, target_url: Optional[str] = None) -> Dict[str, Any]:
        instruction = {
            "persona": persona,
            "goal": goal,
            "target_url": target_url,
        }
        beta_tag = os.getenv("ANTHROPIC_COMPUTER_USE_BETA", "computer-use-2025-01-24")
        # Preferred: beta messages with explicit computer-use beta flag
        try:
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=1024,
                tools=[
                    {
                        "type": "computer_20250124",
                        "name": "computer",
                        "display_width_px": 1024,
                        "display_height_px": 768,
                        "display_number": 1,
                    },
                ],
                messages=[{"role": "user", "content": json.dumps(instruction)}],
                betas=[beta_tag],
                system=(
                    "You are a shopper who is looking to purchase something on a website. "
                    "Control the browser only via the computer tool. "
                    "Before acting and after each action, request and review a screenshot. "
                    "Use precise clicks and short waits. Avoid destructive actions. "
                    "When the goal is complete, stop issuing tool_use."
                ),
            )
            try:
                payload = resp.model_dump()
            except Exception:
                payload = json.loads(json.dumps(resp, default=str))
            return {"success": True, "provider": "anthropic", "api": "beta.messages", "payload": payload}
        except Exception as e:
            logger.error(f"Anthropic Computer Use error (beta.messages): {e}")
            # Fallback: attempt non-beta messages without explicit betas
            try:
                resp2 = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    tools=[
                        {
                            "type": "computer_20250124",
                            "name": "computer",
                            "display_width_px": 1280,
                            "display_height_px": 800,
                            "display_number": 1,
                        }
                    ],
                    messages=[{"role": "user", "content": json.dumps(instruction)}],
                    betas=[beta_tag],
                    system=(
                        "You are a shopper who is looking to purchase something on a website. "
                        "Control the browser only via the computer tool. "
                        "Before acting and after each action, request and review a screenshot. "
                        "Use precise clicks and short waits. Avoid destructive actions. "
                        "When the goal is complete, stop issuing tool_use."
                    ),
                )
                try:
                    payload2 = resp2.model_dump()
                except Exception:
                    payload2 = json.loads(json.dumps(resp2, default=str))
                return {"success": True, "provider": "anthropic", "api": "messages", "payload": payload2}
            except Exception as e2:
                logger.error(f"Anthropic Computer Use error (messages): {e2}")
                return {"success": False, "error": str(e2)}

    async def run_browserbase(self, persona: str, goal: str, target_url: str, output_dir: str, max_steps: int = 40) -> Dict[str, Any]:
        """Execute Anthropic Computer Use tool actions against a Browserbase browser via Playwright.

        Saves screenshots under output_dir/screens.
        """
        beta_tag = os.getenv("ANTHROPIC_COMPUTER_USE_BETA", "computer-use-2025-01-24")

        # Setup Browserbase
        # Prefer an existing endpoint from env or persisted file, fall back to API creation.
        ws_ep = os.getenv("BROWSERBASE_WS_ENDPOINT")
        if not ws_ep:
            try:
                persisted_path = Path(__file__).resolve().parents[3] / ".browserbase_ws_endpoint"
                if persisted_path.exists():
                    ws_ep = persisted_path.read_text().strip()
                    os.environ["BROWSERBASE_WS_ENDPOINT"] = ws_ep
                    logger.info("Using persisted Browserbase ws_endpoint from .browserbase_ws_endpoint")
            except Exception:
                pass
        if not ws_ep:
            api_key = os.getenv("BROWSERBASE_API_KEY")
            if api_key:
                try:
                    from .dom_agentql_env import AgentQLEnv
                    ws_ep = AgentQLEnv()._create_browserbase_session(api_key)
                    os.environ["BROWSERBASE_WS_ENDPOINT"] = ws_ep
                    logger.info("Created Browserbase session for Computer Use mode via API")
                except Exception as e:
                    logger.error(f"Failed to create Browserbase session: {e}")
                    # Let connector attempt other fallbacks and raise a clearer error later

        bb = BrowserbaseConnector(timeout=30000, ws_endpoint=ws_ep)
        await bb.setup(headless=os.getenv("HEADLESS", "true").lower() == "true")
        # Align viewport with advertised display size
        try:
            await bb.page.set_viewport_size({"width": 1280, "height": 800})
        except Exception:
            pass
        screens_dir = Path(output_dir) / "screens"
        screens_dir.mkdir(parents=True, exist_ok=True)

        # Navigate initial URL if provided
        if target_url:
            try:
                await bb.page.goto("about:blank", timeout=5000)
            except Exception:
                pass
            logger.info(f"[CU] Navigating to initial target URL: {target_url}")
            await bb.page.goto(target_url, wait_until="domcontentloaded")
            try:
                await bb.page.wait_for_load_state("load", timeout=8000)
            except Exception:
                pass
            try:
                title_now = await bb.page.title()
            except Exception:
                title_now = None
            logger.info(f"[CU] At URL: {bb.page.url} | Title: {title_now}")

        # Transcript history
        history: List[Dict[str, Any]] = [
            {
                "role": "user",
                "content": json.dumps({
                    "persona": persona,
                    "goal": goal,
                    "target_url": target_url,
                }),
            }
        ]

        def build_tools() -> List[Dict[str, Any]]:
            return [
                {
                    "type": "computer_20250124",
                    "name": "computer",
                    "display_width_px": 1280,
                    "display_height_px": 800,
                    "display_number": 1,
                },
            ]

        step = 0
        results: List[Dict[str, Any]] = []
        try:
            while step < max_steps:
                # Create / continue the conversation
                try:
                    cur_title = await bb.page.title()
                except Exception:
                    cur_title = None
                logger.info(f"[CU] Step {step + 1} of {max_steps} | URL: {bb.page.url} | Title: {cur_title}")
                resp = self.client.beta.messages.create(
                    model=self.model,
                    max_tokens=256,
                    tools=build_tools(),
                    messages=history,
                    betas=[beta_tag],
                    system=(
                        "You are a shopper who is looking to purchase something on a website. "
                        "Control the browser only via the computer tool. "
                        "Before acting and after each action, request and review a screenshot. "
                        "Use precise clicks and short waits. Avoid destructive actions. "
                        "When the goal is complete, stop issuing tool_use."
                    ),
                )

                # Normalize assistant content blocks and extract tool_uses
                assistant_blocks: List[Dict[str, Any]] = []
                tool_uses: List[Dict[str, Any]] = []
                for block in resp.content:
                    btype = getattr(block, "type", None)
                    if btype == "text":
                        assistant_blocks.append({"type": "text", "text": getattr(block, "text", "")})
                    elif btype == "tool_use":
                        normalized = {
                            "type": "tool_use",
                            "id": getattr(block, "id", None),
                            "name": getattr(block, "name", None),
                            "input": getattr(block, "input", {}) or {},
                        }
                        assistant_blocks.append(normalized)
                        if normalized.get("name") == "computer":
                            tool_uses.append(normalized)
                    else:
                        assistant_blocks.append({"type": "text", "text": str(block)})

                # Log assistant decision
                if tool_uses:
                    summary = ", ".join(
                        [
                            f"id={tu.get('id')} action={(tu.get('input') or {}).get('action')}"
                            for tu in tool_uses
                        ]
                    )
                    logger.info(f"[CU] Assistant issued {len(tool_uses)} computer tool_use(s): {summary}")
                else:
                    texts = [b.get("text", "") for b in assistant_blocks if b.get("type") == "text"]
                    text_preview = (" ".join(texts))[:280]
                    logger.info(f"[CU] No computer tool_use provided. Assistant text preview: {text_preview}")

                # Append assistant turn
                history.append({"role": "assistant", "content": assistant_blocks})
                if not tool_uses:
                    # Finished
                    return {
                        "success": True,
                        "provider": "anthropic",
                        "api": "beta.messages.loop",
                        "final": {"url": bb.page.url if bb.page else None, "title": (await bb.page.title()) if bb.page else None},
                        "steps": results,
                    }

                # For each tool_use, execute and prepare tool_result content blocks
                tool_result_blocks: List[Dict[str, Any]] = []
                for tu in tool_uses:
                    tu_id = tu.get("id")
                    tu_input = tu.get("input", {}) or {}
                    action = (tu_input.get("action") or "").lower()
                    result_text = "ok"
                    img_b64 = None

                    try:
                        logger.info(f"[CU] Executing tool_use id={tu_id} action={action} input={json.dumps(tu_input)[:500]}")
                        if action == "screenshot":
                            png = await bb.page.screenshot(full_page=False)
                            img_b64 = base64.b64encode(png).decode("ascii")
                        elif action in ("navigate", "goto"):
                            url = tu_input.get("url") or tu_input.get("value") or tu_input.get("target")
                            if url:
                                logger.info(f"[CU] navigate → {url}")
                                await bb.page.goto(url, wait_until="domcontentloaded")
                            else:
                                result_text = "no-url"
                        elif action in ("click", "mouse_click", "double_click", "left_click"):
                            x = tu_input.get("x") or (tu_input.get("position") or {}).get("x")
                            y = tu_input.get("y") or (tu_input.get("position") or {}).get("y")
                            # Claude may provide coordinates as an array under 'coordinate' or 'coordinates'
                            coord = tu_input.get("coordinate") or tu_input.get("coordinates")
                            if (x is None or y is None) and isinstance(coord, (list, tuple)) and len(coord) >= 2:
                                x = coord[0]
                                y = coord[1]
                            if x is not None and y is not None:
                                logger.info(f"[CU] click at ({x}, {y}) double={action=='double_click'}")
                                await bb.page.mouse.move(float(x), float(y))
                                if action == "double_click":
                                    await bb.page.mouse.dblclick(float(x), float(y))
                                else:
                                    await bb.page.mouse.click(float(x), float(y))
                            else:
                                result_text = "missing-coordinates"
                        elif action in ("move_mouse", "mouse_move"):
                            x = tu_input.get("x") or (tu_input.get("position") or {}).get("x")
                            y = tu_input.get("y") or (tu_input.get("position") or {}).get("y")
                            if x is not None and y is not None:
                                logger.info(f"[CU] move mouse to ({x}, {y})")
                                await bb.page.mouse.move(float(x), float(y))
                            else:
                                result_text = "missing-coordinates"
                        elif action in ("right_click", "context_click"):
                            x = tu_input.get("x") or (tu_input.get("position") or {}).get("x")
                            y = tu_input.get("y") or (tu_input.get("position") or {}).get("y")
                            coord = tu_input.get("coordinate") or tu_input.get("coordinates")
                            if (x is None or y is None) and isinstance(coord, (list, tuple)) and len(coord) >= 2:
                                x = coord[0]
                                y = coord[1]
                            if x is not None and y is not None:
                                logger.info(f"[CU] right click at ({x}, {y})")
                                await bb.page.mouse.click(float(x), float(y), button="right")
                            else:
                                result_text = "missing-coordinates"
                        elif action in ("hover",):
                            x = tu_input.get("x") or (tu_input.get("position") or {}).get("x")
                            y = tu_input.get("y") or (tu_input.get("position") or {}).get("y")
                            if x is not None and y is not None:
                                logger.info(f"[CU] hover at ({x}, {y})")
                                await bb.page.mouse.move(float(x), float(y))
                            else:
                                result_text = "missing-coordinates"
                        elif action in ("type", "keyboard_type"):
                            text = tu_input.get("text") or tu_input.get("value") or ""
                            logger.info(f"[CU] type text len={len(text)}")
                            await bb.page.keyboard.type(text)
                        elif action in ("key", "key_press", "press"):
                            # Accept key value from multiple fields commonly seen in Claude outputs
                            key = tu_input.get("key") or tu_input.get("value") or tu_input.get("text") or "Enter"
                            logger.info(f"[CU] press key {key}")
                            await bb.page.keyboard.press(key)
                        elif action in ("scroll", "mouse_wheel"):
                            dx = int(tu_input.get("dx") or 0)
                            dy = int(tu_input.get("dy") or 600)
                            logger.info(f"[CU] scroll wheel dx={dx} dy={dy}")
                            await bb.page.mouse.wheel(dx, dy)
                        elif action == "wait":
                            ms = int(tu_input.get("ms") or 1000)
                            logger.info(f"[CU] wait {ms}ms")
                            await bb.page.wait_for_timeout(ms)
                        elif action in ("back", "go_back"):
                            logger.info("[CU] browser go back")
                            await bb.page.go_back()
                        elif action in ("forward", "go_forward"):
                            logger.info("[CU] browser go forward")
                            await bb.page.go_forward()
                        elif action in ("reload", "refresh"):
                            logger.info("[CU] browser reload")
                            await bb.page.reload()
                        else:
                            result_text = f"unsupported-action:{action}"

                        # After each action, capture a small screenshot for trace
                        try:
                            await bb.page.wait_for_timeout(200)
                        except Exception:
                            pass
                        if img_b64 is None:
                            png2 = await bb.page.screenshot(full_page=False)
                            img_b64 = base64.b64encode(png2).decode("ascii")
                        # Save to disk
                        step += 1
                        shot_path = screens_dir / f"step_{step:03d}.png"
                        shot_path.write_bytes(base64.b64decode(img_b64))

                        try:
                            cur_title_after = await bb.page.title()
                        except Exception:
                            cur_title_after = None
                        logger.info(
                            f"[CU] Completed action={action} status={result_text} → URL: {bb.page.url} | Title: {cur_title_after} | Screenshot: {shot_path}"
                        )

                        # Append tool_result with image
                        tool_result_blocks.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tu_id,
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/png",
                                            "data": img_b64,
                                        },
                                    },
                                    {"type": "text", "text": result_text},
                                ],
                            }
                        )

                        results.append({"action": action, "status": result_text, "screenshot": str(shot_path)})
                    except Exception as exec_err:
                        # Return an error tool_result
                        logger.exception(f"[CU] Error executing action={action}: {exec_err}")
                        tool_result_blocks.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tu_id,
                                "content": [{"type": "text", "text": f"error:{exec_err}"}],
                            }
                        )
                        results.append({"action": action, "status": f"error:{exec_err}"})

                # Append our user tool_result turn and continue
                history.append({"role": "user", "content": tool_result_blocks})
                # Gentle throttle to avoid 429 rate limits
                await asyncio.sleep(1.5)

            # If loop exits
            return {"success": True, "provider": "anthropic", "api": "beta.messages.loop", "steps": results}
        finally:
            await bb.cleanup()


