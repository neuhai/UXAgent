<h1 align="center"> Synthetic User for A/B testing </h1>

<p align="center">
    <a href="https://arxiv.org/abs/2502.12561">
        <img src="https://img.shields.io/badge/arXiv-2502.12561-B31B1B.svg?style=plastic&logo=arxiv" alt="arXiv">
    </a>
    <a href="https://opensource.org/licenses/MIT">
        <img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=plastic" alt="License: MIT">
    </a>
</p>



<p align="center">
    <img src="/figures/teaser.png" width="100%">
</p>


## Overview
**Synthetic User** is a framework for creating AI-powered synthetic users that can simulate realistic human behaviors on websites. This repository provides tools to:
- Generate diverse user personas with customizable demographics and intents
- Create automated agents that navigate websites like real users would
- Conduct A/B testing and usability evaluations with synthetic participants
- Gather behavioral data and insights without requiring human test subjects

The system supports multiple execution modes (AgentQL, Computer Use) and integrates with Browserbase for scalable web automation. Whether you're testing new features, optimizing user flows, or conducting market research, synthetic users provide a cost-effective way to gather user behavior data at scale.

[![Button Click]][Link] 

<p align="center">
    <a href="https://uxagent.hailab.io/"> 
        <img src="https://img.shields.io/badge/Live_Demo-37a779?style=for-the-badge">
    </a>
    <a href="https://huggingface.co/datasets/NEU-HAI/UXAgent"> 
        <img src="https://img.shields.io/badge/Data-37a779?style=for-the-badge">
    </a>
</p>

https://github.com/user-attachments/assets/0c5d22a8-4438-402b-8e6c-2151bdf53bf1


---

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/UXAgent.git
   cd UXAgent
   ```

2. **Set up the environment:**
   ```bash
   conda env create -f environment.yml -n simulated_web_agent
   conda activate simulated_web_agent
   ```

3. **Install the package:**
   ```bash
   pip install -e .
   ```

4. **Browserbase credentials (required):**
   The synthetic user framework runs on Browserbase (remote Chromium over CDP). Provide one of the following:
   - Set an explicit WebSocket endpoint:
     ```bash
     export BROWSERBASE_WS_ENDPOINT="wss://connect.browserbase.com?sessionId=..."
     ```
   - Or let the tool create a session via API (preferred):
     ```bash
     export BROWSERBASE_API_KEY=bb_XXXX
     # optional, but recommended to scope usage
     export BROWSERBASE_PROJECT_ID=3034c893-8a55-4327-beb7-aa4829f70341
     # optional: override API base or region
     export BROWSERBASE_API_BASE=https://api.browserbase.com
     export BROWSERBASE_REGION=us
     ```

5. **Set API keys:**
   The system supports AWS Claude and OpenAI. You only need to set one of them.
   - For AWS Claude:
      - https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html
   ```bash
   export AWS_ACCESS_KEY_ID=xxx123
   export AWS_SECRET_ACCESS_KEY=xxx123
   export OPENAI_API_KEY=sk-123
   ```

6. **Optional: Headful mode:**
   Browserbase sessions can be headless or headful depending on your session configuration. You can still set:
   ```bash
   export HEADLESS=false
   ```
   Note: local browser launch is no longer supported.

---

## Quick Start (Browserbase + AgentQL)

1. **Run the Agent:**
   Provide a target URL and a persona. The agent will connect to Browserbase automatically using the environment variables above.
   ```bash
   python3 -m simulated_web_agent.main \
     --persona "example_data/personas/json/virtual customer 0.json" \
     --output "output" \
     --llm-provider openai \
     --target-url "https://www.amazon.com"
   ```
   Results are saved under the specified `--output` directory.

2. **Example Persona Format:**
   ```json
   {
       "persona": "Persona: Michael ...",
       "intent": "buy a large, inflatable spider decoration for halloween",
       "age": 42,
       "gender": "male",
       "income": [30001, 94000]
   }
   ```
3. **Example Persona:**
   ```
   Persona: Michael

   Background:
   Michael is a mid-career professional working as a marketing manager at a technology startup in San Francisco. He is passionate about using data-driven strategies to drive growth and innovation for the company.

   Demographics:
   Age: 42
   Gender: Male
   Education: Bachelor's degree in Business Administration
   Profession: Marketing Manager
   Income: $75,000

   Financial Situation:
   Michael has a comfortable income that allows him to maintain a decent standard of living in the expensive San Francisco Bay Area. He is financially responsible, saving a portion of his earnings for retirement and emergencies, while also enjoying occasional leisure activities and travel.

   Shopping Habits:
   Michael prefers to shop online for convenience, but he also enjoys the occasional trip to the mall or specialty stores to browse for new products. He tends to research items thoroughly before making a purchase, looking for quality, functionality, and value. Michael values efficiency and is not influenced by trends or impulse buys.

   Professional Life:
   As a marketing manager, Michael is responsible for developing and implementing marketing strategies to promote the startup's products and services. He collaborates closely with the product, sales, and design teams to ensure a cohesive brand experience. Michael is always looking for ways to optimize marketing campaigns and stay ahead of industry trends.

   Personal Style:
   Michael has a casual, yet professional style. He often wears button-down shirts, chinos, and leather shoes to the office. On weekends, he enjoys wearing comfortable, sporty attire for outdoor activities like hiking or cycling. Michael tends to gravitate towards neutral colors and classic, versatile pieces that can be mixed and matched.

   Intent:
   buy a large, inflatable spider decoration for halloween

   ```
---

## Executors and Modes

| Mode | Executor file | Parsing style | Output | Example CLI |
| --- | --- | --- | --- | --- |
| agentql | `src/simulated_web_agent/executor/dom_agentql_env.py` | DOM/text (AgentQL) | `agentql_results.json` | ```bash
python3 -m simulated_web_agent.main --mode agentql --persona example_data/personas/json/virtual\ customer\ 0.json --output output/agentql --llm-provider openai --target-url https://example.com
``` |
| computer-use | `src/simulated_web_agent/executor/dom_llm_actions_env.py` | DOM/text (LLM JSON actions) | `computer_use_results.json` | ```bash
python3 -m simulated_web_agent.main --mode computer-use --persona example_data/personas/json/virtual\ customer\ 0.json --output output/cu --llm-provider openai --target-url https://example.com
``` |
| openai-computer-use | `src/simulated_web_agent/executor/openai_computer_use.py` | Vision/screenshot (OpenAI native) | `openai_computer_use_results.json` | ```bash
OPENAI_API_KEY=... python3 -m simulated_web_agent.main --mode openai-computer-use --persona example_data/personas/json/virtual\ customer\ 0.json --output output/openai_cu --llm-provider openai --target-url https://example.com
``` |
| anthropic-computer-use | `src/simulated_web_agent/executor/anthropic_computer_use.py` | Vision/screenshot (Claude; Browserbase bridge executes tool actions) | `anthropic_computer_use_results.json` | ```bash
ANTHROPIC_API_KEY=... python3 -m simulated_web_agent.main --mode anthropic-computer-use --persona example_data/personas/json/virtual\ customer\ 0.json --output output/anthropic_cu --llm-provider aws --target-url https://example.com
``` |

**Important:** The OpenAI Computer Use executor requires allowlisted access granted by OpenAI. If your account is not allowlisted for the `computer-use-preview` model, this mode will fail with a 404 `model_not_found` error.

---

## Generating Personas

Use the `persona.py` script to generate virtual customer personas based on configurations.

1. **Example Config (`config.yml`):**
   ```yaml
   output_dir: "output"
   queries_file: "queries.txt"
   total_personas: 200

   age_groups:
     "18-24": 40
     "25-34": 30
     "35-44": 20
     "45-54": 10
   ```

2. **Example Queries (`queries.txt`):**
   ```
   jacket columbia
   smartphone samsung
   laptop apple
   ```

3. **Run the script:**
   ```bash
   python -m simulated_web_agent.main.persona --config-file config.yml
   ```

Generated personas will be saved in the specified `output_dir` as `.json` and `.txt` files.

---

## Notes on Legacy Modes
- Local Selenium/Chromedriver-based execution and manual recipe flows have been removed from the CLI. The runtime now uses Playwright over CDP to connect to Browserbase exclusively.
- Internal recipe modules remain in the repository history but are not used by the current entrypoint.

---

## License
This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

## Citation
```bibtex
@misc{lu2025uxagent,
    title={UXAgent: An LLM Agent-Based Usability Testing Framework for Web Design},
    author={Yuxuan Lu and Bingsheng Yao and Hansu Gu and Jing Huang and Jessie Wang and Laurence Li and Jiri Gesi and Qi He and Toby Jia-Jun Li and Dakuo Wang},
    year={2025},
    eprint={2502.12561},
    archivePrefix={arXiv},
    primaryClass={cs.HC}
}
```
