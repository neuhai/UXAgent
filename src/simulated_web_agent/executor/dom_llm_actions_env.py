import json
import logging
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
)

from ..agent import gpt
from pathlib import Path
from dotenv import load_dotenv
from .dom_agentql_env import AgentQLEnv


logger = logging.getLogger(__name__)


class BrowserbaseConnector:
    def __init__(self, timeout: int = 30000, ws_endpoint: Optional[str] = None):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.timeout = timeout
        self.ws_endpoint_override = ws_endpoint

    def _create_browserbase_session(self, api_key: str) -> str:
        """Delegate to AgentQLEnv's tested session creation for parity with AgentQL mode."""
        helper = AgentQLEnv()
        return helper._create_browserbase_session(api_key)

    async def setup(self, headless: bool = True):
        # Ensure envs are loaded from project root .env
        try:
            project_root = Path(__file__).resolve().parents[3]
            dotenv_path = project_root / ".env"
            load_dotenv(dotenv_path=dotenv_path, override=False)
        except Exception:
            pass
        logger.info("[BB] Starting Playwright and preparing Browserbase connection")
        self.playwright = await async_playwright().start()

        # Load envs from project root .env if present, then try persisted endpoint first
        persisted = None
        try:
            persisted_path = Path(__file__).resolve().parents[3] / ".browserbase_ws_endpoint"
            if persisted_path.exists():
                persisted = persisted_path.read_text().strip()
        except Exception:
            pass
        ws_endpoint = self.ws_endpoint_override or persisted or os.getenv("BROWSERBASE_WS_ENDPOINT")
        if self.ws_endpoint_override:
            logger.info("[BB] Using ws_endpoint override from caller")
        elif persisted:
            logger.info("[BB] Using persisted ws_endpoint from .browserbase_ws_endpoint")
        elif os.getenv("BROWSERBASE_WS_ENDPOINT"):
            logger.info("[BB] Using ws_endpoint from environment variable")
        # Ensure the API key is loaded from .env if not already in env
        api_key = os.getenv("BROWSERBASE_API_KEY")
        if not api_key:
            try:
                project_root = Path(__file__).resolve().parents[3]
                dotenv_path = project_root / ".env"
                load_dotenv(dotenv_path=dotenv_path, override=False)
                api_key = os.getenv("BROWSERBASE_API_KEY")
            except Exception:
                pass

        if not ws_endpoint and api_key:
            logger.info("[BB] No ws_endpoint provided; creating Browserbase session via API")
            ws_endpoint = self._create_browserbase_session(api_key)
            # Cache into env for downstream components
            os.environ["BROWSERBASE_WS_ENDPOINT"] = ws_endpoint
            logger.info("Created Browserbase session via API and set BROWSERBASE_WS_ENDPOINT")

        if not ws_endpoint:
            raise RuntimeError(
                "Browserbase connection required. Set BROWSERBASE_WS_ENDPOINT or BROWSERBASE_API_KEY."
            )

        logger.info("[BB] Connecting to Chromium over CDP")
        try:
            self.browser = await self.playwright.chromium.connect_over_cdp(ws_endpoint)
        except Exception as connect_err:
            logger.warning(f"[BB] CDP connect failed ({type(connect_err).__name__}): {connect_err}")
            # If we have an API key, attempt to create a fresh session and retry
            if api_key:
                try:
                    logger.info("[BB] Creating a fresh Browserbase session via API due to connect failure")
                    ws_endpoint = self._create_browserbase_session(api_key)
                    os.environ["BROWSERBASE_WS_ENDPOINT"] = ws_endpoint
                    logger.info("[BB] Retrying CDP connect with fresh session")
                    self.browser = await self.playwright.chromium.connect_over_cdp(ws_endpoint)
                except Exception as retry_err:
                    logger.error(f"[BB] Retry connect failed: {retry_err}")
                    raise
            else:
                raise

        if self.browser.contexts:
            logger.info("[BB] Reusing existing browser context from Browserbase session")
            self.context = self.browser.contexts[0]
        else:
            logger.info("[BB] Creating new browser context")
            self.context = await self.browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1.0,
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                ),
                permissions=["camera", "microphone"],
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )

        blocked_domains = [
            "googlesyndication.com",
            "doubleclick.net",
            "g.doubleclick.net",
            "google-analytics.com",
            "googletagmanager.com",
            "facebook.net",
            "google.com/recaptcha",
            "safeframe.googlesyndication.com",
            "adservice.google.com",
        ]

        async def route_handler(route):
            try:
                req = route.request
                url = req.url
                host = urlparse(url).hostname or ""
                if any(domain in url or domain in host for domain in blocked_domains):
                    await route.abort()
                else:
                    await route.continue_()
            except Exception:
                try:
                    await route.continue_()
                except Exception:
                    pass

        try:
            await self.context.route("**/*", route_handler)
        except Exception:
            pass

        if self.context.pages:
            logger.info("[BB] Reusing existing page from context")
            self.page = self.context.pages[0]
        else:
            logger.info("[BB] Creating new page in context")
            self.page = await self.context.new_page()

        try:
            await self.page.set_default_navigation_timeout(self.timeout * 2)
            await self.page.set_default_timeout(self.timeout * 2)
        except Exception:
            pass
        logger.info("[BB] Browserbase setup complete")

    async def cleanup(self):
        try:
            logger.info("[BB] Cleaning up Playwright / Browserbase resources")
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")


COMPUTER_USE_SYSTEM_PROMPT = (
    "You control a web browser to achieve a user goal.\n"
    "Return exactly one JSON action with keys: action, target, value (optional).\n"
    "- action: one of [\"click\",\"type\",\"submit\",\"scroll\",\"navigate\",\"wait\"]\n"
    "- target: human-readable selector or description\n"
    "- value: text to type or URL (for navigate)\n"
    "Notes:\n"
    "- Adding to cart means placing the item into a VIRTUAL CART only (no sign-in, no checkout).\n"
    "- If an add-to-cart flow asks for fulfillment, ALWAYS choose Shipping/Delivery (not Pickup).\n"
    "Examples:\n"
    '{"action":"type","target":"search box","value":"nike shoes"}\n'
    '{"action":"submit","target":"search box"}\n'
    '{"action":"click","target":"Add to Cart"}\n'
    '{"action":"scroll","target":"down"}\n'
    '{"action":"navigate","target":"url","value":"https://example.com"}\n'
    "Respond ONLY with a JSON object, no extra text."
)


class ComputerUseEnv:
    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        max_steps: int = 50,
        output_dir: Optional[str] = None,
    ):
        self.headless = headless
        self.timeout = timeout
        self.max_steps = max_steps
        self.bb = BrowserbaseConnector(timeout=timeout)
        self.output_dir: Optional[Path] = Path(output_dir) if output_dir else None

    async def setup(self):
        await self.bb.setup(headless=self.headless)

    async def navigate_to(self, url: str) -> Dict[str, Any]:
        try:
            await self.bb.page.goto("about:blank", timeout=5000)
        except Exception:
            pass
        await self.bb.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 2)
        try:
            await self.bb.page.wait_for_load_state("load", timeout=8000)
        except Exception:
            pass
        return {"url": self.bb.page.url, "title": await self.bb.page.title()}

    async def observe(self) -> Dict[str, Any]:
        page_html = await self.bb.page.content()
        url = self.bb.page.url
        clickables = await self.bb.page.evaluate(
            """
() => Array.from(document.querySelectorAll('a,button,[role=button],input[type=submit],input[type=button]'))
  .slice(0, 100)
  .map(el => el.innerText?.trim() || el.getAttribute('aria-label') || el.getAttribute('alt') || el.getAttribute('name') || el.href || el.id)
  .filter(Boolean)
  .slice(0, 50)
"""
        )
        return {"page": page_html[:120000], "url": url, "clickables": clickables[:50]}

    async def think(self, persona: str, goal: str, observation: Dict[str, Any]) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": COMPUTER_USE_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"persona": persona, "goal": goal, "observation": observation})},
        ]
        resp = await gpt.async_chat(messages, json_mode=True, model="small")
        try:
            action = json.loads(resp)
        except Exception:
            import re
            js = re.findall(r"\{[\\s\\S]*\}", resp)
            action = json.loads(js[0]) if js else {"action": "scroll", "target": "down"}
        return action

    async def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        a = (action.get("action") or "").lower()
        target = action.get("target") or ""
        value = action.get("value") or ""

        page = self.bb.page

        async def try_click_by_text(t: str) -> bool:
            try:
                loc = page.get_by_role("button", name=t, exact=True)
                if await loc.count():
                    await loc.first.click()
                    return True
            except Exception:
                pass
            try:
                loc = page.get_by_text(t, exact=True)
                if await loc.count():
                    await loc.first.click()
                    return True
            except Exception:
                pass
            try:
                loc = page.locator("a", has_text=t)
                if await loc.count():
                    await loc.first.click()
                    return True
            except Exception:
                pass
            # Fallbacks: case-insensitive/partial matches
            try:
                loc = page.get_by_role("button", name=re.compile(re.escape(t), re.IGNORECASE))
                if await loc.count():
                    await loc.first.click()
                    return True
            except Exception:
                pass
            try:
                loc = page.get_by_text(re.compile(re.escape(t), re.IGNORECASE))
                if await loc.count():
                    await loc.first.click()
                    return True
            except Exception:
                pass
            try:
                loc = page.locator("button", has_text=re.compile(re.escape(t), re.IGNORECASE))
                if await loc.count():
                    await loc.first.click()
                    return True
            except Exception:
                pass
            return False

        async def type_into_search_box(txt: str) -> bool:
            selectors = [
                "input[type=search]",
                "input[name*=search i]",
                "input[placeholder*=search i]",
                "input[type=text]",
            ]
            for sel in selectors:
                try:
                    loc = page.locator(sel)
                    if await loc.count():
                        el = loc.first
                        await el.fill(txt)
                        return True
                except Exception:
                    continue
            return False

        async def try_click_add_to_cart() -> bool:
            # Prefer explicit product add-to-cart buttons
            candidates = [
                page.locator('button[data-test="addToCartButton" i]'),
                page.get_by_role("button", name=re.compile(r"add to (cart|bag)", re.IGNORECASE)),
                page.locator('button[aria-label*="Add to cart" i]'),
                page.locator("button", has_text=re.compile(r"add to (cart|bag)", re.IGNORECASE)),
            ]
            for loc in candidates:
                try:
                    if await loc.count():
                        await loc.first.click()
                        return True
                except Exception:
                    continue
            return False

        async def try_select_variants() -> bool:
            """Heuristically select required size/color variants before add-to-cart."""
            changed = False
            # Common size labels
            size_labels = [
                "Twin XL", "Twin", "Full", "Queen", "King", "California King",
                "Standard", "Standard/Queen", "One Size",
            ]
            for label in size_labels:
                try:
                    loc = page.get_by_role("button", name=re.compile(rf"^\s*{re.escape(label)}\s*$", re.IGNORECASE))
                    if await loc.count():
                        # Skip disabled options
                        try:
                            state = await loc.first.get_attribute("disabled")
                            if state is not None:
                                continue
                        except Exception:
                            pass
                        await loc.first.click()
                        changed = True
                        break
                except Exception:
                    continue
            # Try generic selects (drop-downs)
            try:
                selects = page.locator("select:not([disabled])")
                if await selects.count():
                    sel = selects.first
                    try:
                        await sel.select_option(index=1)
                        changed = True
                    except Exception:
                        pass
            except Exception:
                pass
            return changed

        async def goto_cart_if_visible() -> bool:
            # Only follow explicit confirmation affordances
            options = [
                page.get_by_role("button", name=re.compile(r"view cart\s*&\s*checkout", re.IGNORECASE)),
                page.get_by_role("link", name=re.compile(r"view cart\s*&\s*checkout", re.IGNORECASE)),
                page.get_by_text(re.compile(r"^\s*view cart\s*&\s*checkout\s*$", re.IGNORECASE)),
            ]
            for loc in options:
                try:
                    if await loc.count():
                        await loc.first.click()
                        return True
                except Exception:
                    continue
            return False

        try:
            if a == "navigate":
                if value:
                    await page.goto(value, wait_until="domcontentloaded")
                else:
                    await page.goto(target, wait_until="domcontentloaded")
            elif a == "scroll":
                if "up" in target.lower():
                    await page.evaluate("window.scrollBy(0,-600)")
                else:
                    await page.evaluate("window.scrollBy(0,600)")
            elif a == "type":
                ok = await type_into_search_box(value)
                if not ok and target:
                    try:
                        await page.keyboard.type(value)
                        ok = True
                    except Exception:
                        pass
                if not ok:
                    raise RuntimeError("Could not find input to type into")
                # Auto-submit when typing into search to trigger navigation/results
                try:
                    should_submit = False
                    if target:
                        should_submit = "search" in target.lower()
                    if not should_submit:
                        # Heuristic: common behavior after typing a query
                        should_submit = True
                    if should_submit:
                        logger.info("[CU-LLM] auto-submit: pressing Enter after typing")
                        await page.keyboard.press("Enter")
                        try:
                            await page.wait_for_load_state("load", timeout=10000)
                        except Exception:
                            pass
                except Exception:
                    pass
            elif a == "submit":
                try:
                    await page.keyboard.press("Enter")
                except Exception:
                    pass
            elif a == "click":
                # Special handling: if the target looks like an Add to Cart request, try generic add-to-cart flows
                if re.search(r"add to cart", target, re.IGNORECASE):
                    # Pre-select variants if required
                    try:
                        await try_select_variants()
                    except Exception:
                        pass
                    if await try_click_add_to_cart():
                        # Wait briefly for confirmation surface and click if present
                        try:
                            await page.wait_for_timeout(1200)
                            # If a confirmation text appears, prefer explicit checkout affordance
                            confirm = page.get_by_text(re.compile(r"added to cart|in your cart", re.IGNORECASE))
                            if await confirm.count():
                                await goto_cart_if_visible()
                            else:
                                await goto_cart_if_visible()
                        except Exception:
                            pass
                    else:
                        # As a fallback, try partial text click
                        if not await try_click_by_text("Add to cart"):
                            raise RuntimeError(f"Could not click add to cart: {target}")
                else:
                    if not await try_click_by_text(target):
                        token = target.strip().split()[0] if target else ""
                        if token and await try_click_by_text(token):
                            pass
                        else:
                            raise RuntimeError(f"Could not click: {target}")
            elif a == "wait":
                await page.wait_for_timeout(1500)
            else:
                await page.evaluate("window.scrollBy(0,400)")

            try:
                await page.wait_for_load_state("load", timeout=6000)
            except Exception:
                pass

            return {"success": True, "action": action, "url": page.url, "title": await page.title()}
        except Exception as e:
            return {"success": False, "error": str(e), "action": action, "url": page.url}

    async def run(self, persona: str, goal: str, target_url: str) -> Dict[str, Any]:
        await self.setup()
        try:
            await self.navigate_to(target_url)
            results = []
            for step_idx in range(self.max_steps):
                obs = await self.observe()
                try:
                    url_obs = obs.get("url")
                    clickables_count = len(obs.get("clickables", [])) if isinstance(obs.get("clickables"), list) else 0
                except Exception:
                    url_obs, clickables_count = None, 0
                logger.info(f"[CU-LLM] Step {step_idx + 1}/{self.max_steps} observe → url={url_obs} clickables={clickables_count}")

                thought = await self.think(persona, goal, obs)
                try:
                    logger.info(f"[CU-LLM] plan → {json.dumps(thought)[:500]}")
                except Exception:
                    logger.info(f"[CU-LLM] plan → {thought}")

                exec_result = await self.act(thought)
                try:
                    logger.info(
                        f"[CU-LLM] act → success={exec_result.get('success')} url={exec_result.get('url')} title={exec_result.get('title')}"
                    )
                except Exception:
                    pass
                results.append(exec_result)

                # Stop early if we reached cart page after add-to-cart
                try:
                    current_url = self.bb.page.url
                except Exception:
                    current_url = exec_result.get("url")
                if current_url and "/cart" in current_url:
                    logger.info("[CU-LLM] Cart page detected; capturing confirmation and stopping run.")
                    cart_info = await self._save_cart_confirmation()
                    final_obs = await self.observe()
                    return {
                        "success": True,
                        "steps": results,
                        "final": final_obs,
                        "cart": cart_info,
                        "total_steps": len(results),
                    }
                if not exec_result.get("success"):
                    break
                await self.bb.page.wait_for_timeout(800)
            final_obs = await self.observe()
            return {
                "success": True,
                "steps": results,
                "final": final_obs,
                "total_steps": len(results),
            }
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up Browserbase resources for ComputerUseEnv."""
        try:
            await self.bb.cleanup()
        except Exception as e:
            logger.warning(f"[CU-LLM] cleanup error: {e}")

    async def _save_cart_confirmation(self) -> Dict[str, Any]:
        """Save a cart screenshot and lightweight cart data if output_dir is provided."""
        info: Dict[str, Any] = {}
        try:
            url = self.bb.page.url
            title = await self.bb.page.title()
            info["url"] = url
            info["title"] = title
            # Try to extract a few item titles generically
            try:
                items = await self.bb.page.evaluate(
                    """
() => Array.from(document.querySelectorAll('[data-test="cartItem-title"], a[href*="/p/"]'))
  .slice(0, 5)
  .map(a => (a.innerText || a.textContent || '').trim())
  .filter(Boolean)
                    """
                )
            except Exception:
                items = []
            info["items_preview"] = items
            # Save screenshot
            if self.output_dir:
                try:
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    shot_path = self.output_dir / "cart_confirmation.png"
                    await self.bb.page.screenshot(path=str(shot_path), full_page=False)
                    info["screenshot"] = str(shot_path)
                except Exception:
                    pass
            # Persist simple cart JSON
            if self.output_dir:
                try:
                    cart_json_path = self.output_dir / "cart.json"
                    with cart_json_path.open("w") as f:
                        json.dump(info, f, indent=2)
                    info["json_path"] = str(cart_json_path)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"[CU-LLM] Failed to save cart confirmation: {e}")
        return info


