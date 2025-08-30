import asyncio
import functools
import json
import logging
import os
import traceback

import click
from dotenv import load_dotenv
from pathlib import Path

from ..agent import gpt
from ..executor.dom_agentql_env import AgentQLUniversalAgent
from ..executor.dom_llm_actions_env import ComputerUseEnv
from ..executor.openai_computer_use import OpenAIComputerUseRunner
from ..executor.anthropic_computer_use import AnthropicComputerUseRunner

from .model import AgentPolicy, HumanPolicy, OpenAIPolicy  # noqa  # noqa

# Website configurations
WEBSITE_CONFIGS = {}


def make_sync(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


"""Legacy Selenium utilities removed in Browserbase-only mode."""


async def run_agentql_automation(persona_data: dict, intent: str, target_url: str, output: str, max_steps: int):
    """
    Run AgentQL universal web automation.
    This is your breakthrough feature - works on ANY website!
    """
    print(f"🚀 Starting AgentQL Universal Web Automation")
    print(f"   Target URL: {target_url}")
    print(f"   Persona: {type(persona_data).__name__} - {str(persona_data)[:100]}...")
    print(f"   Goal: {intent}")
    print("-" * 80)
    
    # Create output directory
    os.makedirs(output, exist_ok=True)
    
    # Prepare persona with goal
    persona_with_goal = {
        "description": persona_data,
        "goal": intent,
        "target_url": target_url
    }
    
    # Initialize AgentQL Universal Agent
    headless = os.environ.get("HEADLESS", "true").lower() == "true"
    agent = AgentQLUniversalAgent(headless=headless)
    
    try:
        # Run the automation
        print("🤖 Starting persona-based automation...")
        result = await agent.run_persona_task(persona_with_goal, target_url)
        
        if result["success"]:
            print("✅ Automation completed successfully!")
            print(f"   Steps executed: {result['total_steps']}")
            print(f"   Final URL: {result.get('final_data', {}).get('url', target_url)}")
            
            # Save results
            results_file = os.path.join(output, "agentql_results.json")
            with open(results_file, "w") as f:
                json.dump(result, f, indent=2, default=str)
            
            print(f"   Results saved to: {results_file}")
            
        else:
            print("❌ Automation failed:")
            print(f"   Error: {result.get('error', 'Unknown error')}")
            
            # Save error details
            error_file = os.path.join(output, "agentql_error.json")
            with open(error_file, "w") as f:
                json.dump(result, f, indent=2, default=str)
    
    except Exception as e:
        print(f"💥 Critical error during automation: {e}")
        print(traceback.format_exc())
        
        # Save error details
        error_file = os.path.join(output, "agentql_critical_error.txt")
        with open(error_file, "w") as f:
            f.write(f"Critical Error: {e}\n\n")
            f.write(traceback.format_exc())
    
    print("\n🏁 AgentQL automation completed")
async def run_computer_use_automation(persona_data: dict, intent: str, target_url: str, output: str, max_steps: int):
    print("🚀 Starting Computer-Use automation (LLM-planned, Playwright-executed)")
    os.makedirs(output, exist_ok=True)
    headless = os.environ.get("HEADLESS", "true").lower() == "true"
    env = ComputerUseEnv(headless=headless, max_steps=max_steps, output_dir=output)
    persona_str = persona_data if isinstance(persona_data, str) else json.dumps(persona_data)
    result = await env.run(persona=persona_str, goal=intent, target_url=target_url)
    if result.get("success"):
        print("✅ Computer-Use automation completed successfully!")
    else:
        print("❌ Computer-Use automation encountered errors.")
    out_file = os.path.join(output, "computer_use_results.json")
    with open(out_file, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"   Results saved to: {out_file}")
    print("\n🏁 Computer-Use automation completed")


@click.command()
@click.option("--persona", type=str, help="Path to the persona file.", required=True)
@click.option("--output", type=str, help="Path to the output file.", required=True)
@click.option("--max-steps", type=int, help="Maximum steps to run.", default=50)
@click.option("--cookie", type=(str, str), help="Cookies to set.")
@click.option(
    "--record",
    is_flag=True,
    show_default=True,
    default=False,
    type=bool,
    help="Record the run.",
)
@click.option("--llm-provider", type=click.Choice(["openai", "aws"]), default="aws")
@click.option("--mode", type=click.Choice(["agentql", "computer-use", "openai-computer-use", "anthropic-computer-use"]), default="agentql")
@click.option(
    "--target-url",
    type=str,
    required=True,
    help="Target URL to test with AgentQL+Browserbase",
)
@make_sync
async def main(
    persona: str,
    output: str,
    max_steps: int,
    cookie: tuple[str, str],
    record: bool,
    llm_provider: str,
    target_url: str,
    mode: str,
):

    # Load project-level .env explicitly so envs are reliably present
    try:
        project_root = Path(__file__).resolve().parents[3]
        dotenv_path = project_root / ".env"
        load_dotenv(dotenv_path=dotenv_path, override=False)
    except Exception:
        # Fallback to default search
        load_dotenv()
    # Enable INFO logs for our modules and common dependencies
    logging.basicConfig(level=logging.INFO)
    for name in list(logging.root.manager.loggerDict.keys()):
        if name.startswith((
            "simulated_web_agent",
            "src.simulated_web_agent",
            "agentql",
            "playwright",
        )):
            logging.getLogger(name).setLevel(logging.INFO)
    gpt.provider = llm_provider

    persona_info = json.load(open(persona))
    persona_data = persona_info["persona"]
    intent = persona_info["intent"]

    # Select mode
    if mode == "agentql":
        await run_agentql_automation(persona_data, intent, target_url, output, max_steps)
    elif mode == "computer-use":
        await run_computer_use_automation(persona_data, intent, target_url, output, max_steps)
    else:
        if mode == "openai-computer-use":
            # Native OpenAI Computer Use API (does not use Browserbase)
            runner = OpenAIComputerUseRunner()
            result = runner.run(persona=persona_data, goal=intent, target_url=target_url)
        else:
            # Native Anthropic Computer Use (does not use Browserbase)
            runner = AnthropicComputerUseRunner()
            # Prefer full loop with Browserbase executor
            result = await runner.run_browserbase(
                persona=persona_data,
                goal=intent,
                target_url=target_url,
                output_dir=output,
                max_steps=max_steps,
            )
        os.makedirs(output, exist_ok=True)
        out_file = os.path.join(
            output,
            "openai_computer_use_results.json" if mode == "openai-computer-use" else "anthropic_computer_use_results.json",
        )
        with open(out_file, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"✅ {mode} result saved to: {out_file}")


if __name__ == "__main__":
    main()
