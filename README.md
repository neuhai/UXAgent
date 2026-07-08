<h1 align="center"> UXAgent: A System for Simulating Usability Testing of Web Design with LLM </h1>

<p align="center">
    <a href="https://arxiv.org/abs/2504.09407">
        <img src="https://img.shields.io/badge/arXiv-2504.09407-B31B1B.svg?style=plastic&logo=arxiv" alt="arXiv">
    </a>
    <a href="https://opensource.org/licenses/MIT">
        <img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=plastic" alt="License: MIT">
    </a>
</p>

<p align="center">
Yuxuan Lu, Bingsheng Yao, Hansu Gu, Jing Huang, Jessie Wang, Laurence Li, Haiyang Zhang, Qi He, Toby Jia-Jun Li, Dakuo Wang
</p>

<p align="center">
    <img src="/figures/teaser.png" width="100%">
</p>


## Overview
**UXAgent** is a framework that uses Large Language Models (LLMs) as agents to conduct usability testing in web environments. These agents simulate human-like behaviors, allowing UX researchers to:
- Perform early usability evaluations.
- Gather actionable design insights.
- Iterate without immediate reliance on human participants.

The system leverages dual-system reasoning for quick decisions and in-depth analysis, and its **Universal Web Connector** ensures compatibility with any web page. By offering real-time feedback, UXAgent streamlines the design process and improves testing efficiency.


https://github.com/user-attachments/assets/8f4b352b-1c36-4b16-9d83-b39046357c40


<p align="center">
    <a href="https://uxagent.hailab.io/"> 
        <img src="https://img.shields.io/badge/Live_Demo-37a779?style=for-the-badge">
    </a>
    <a href="https://huggingface.co/datasets/NEU-HAI/UXAgent"> 
        <img src="https://img.shields.io/badge/Data-37a779?style=for-the-badge">
    </a>
</p>



---

## Installation

1. **Clone the repository:**
   ```bash
   git clone git@github.com:neuhai/UXAgent.git
   ```

2. install uv, follow [this guide](https://docs.astral.sh/uv/getting-started/installation/)

3. **Set up the environment:**
   ```bash
   uv sync
   ```

4. **Install Chromium for Playwright:**
   ```bash
   uv run playwright install chromium
   ```

5. **Set API keys:**
   ```bash
   # export AWS_ACCESS_KEY_ID=xxx123
   # export AWS_SECRET_ACCESS_KEY=xxx123
   # export OPENAI_API_KEY=sk-123
   export ANTHROPIC_API_KEY=sk-ant-123
   ```

6. **Optional: Enable "headful" mode:**
   By default, Chrome runs in headless mode (no GUI). To view the browser, set the following:
   ```bash
   export HEADLESS=false
   ```

---

## Using local models (Ollama / vLLM)

UXAgent can run fully locally without any cloud API key, using [Ollama](https://ollama.com/) or a [vLLM](https://docs.vllm.ai/) OpenAI-compatible server. Select the provider with `llm_provider` in `conf/base.yaml` (or `llm_provider=ollama` on the command line) and configure models via environment variables.

### Ollama

```bash
ollama pull llama3.1            # chat model
ollama pull nomic-embed-text    # embedding model (required for agent memory)

export OLLAMA_API_BASE=http://localhost:11434   # default
export OLLAMA_CHAT_MODEL=llama3.1               # fast model ("small")
export OLLAMA_SLOW_CHAT_MODEL=llama3.1          # deep-reasoning model
export OLLAMA_EMBEDDING_MODEL=nomic-embed-text

uv run -m src.simulated_web_agent.main --intent "..." --start-url "..." llm_provider=ollama
```

> [!IMPORTANT]
> The agent feeds the full simplified web page into each prompt, so raise Ollama's
> context window (default is 4096 tokens), e.g. `export OLLAMA_CONTEXT_LENGTH=32768`
> before starting `ollama serve`, or bake `num_ctx` into a Modelfile.

### vLLM

```bash
export VLLM_API_BASE=http://localhost:8000/v1
export VLLM_API_KEY=dummy-key                        # only if your server requires one
export VLLM_CHAT_MODEL=Qwen/Qwen2.5-32B-Instruct     # must match the served model name
export VLLM_SLOW_CHAT_MODEL=Qwen/Qwen2.5-32B-Instruct
export LLM_MAX_TOKENS=8192            # cap output tokens to fit the model context
export EMBEDDING_PROVIDER=ollama      # vLLM usually serves one model; use Ollama for embeddings

uv run -m src.simulated_web_agent.main --intent "..." --start-url "..." llm_provider=vllm
```

If your vLLM server also serves an embedding model, set `VLLM_EMBEDDING_MODEL` instead of `EMBEDDING_PROVIDER`.

**Notes on model choice:** every agent step requires reading a long simplified-HTML page and emitting structured JSON. Small models (< 14B) often produce invalid JSON and trigger repeated retries; instruction-tuned models of 32B or larger are recommended for usable simulations.

---

## Quick Start

### Running a single agent from the command line

```bash
uv run -m src.simulated_web_agent.main --intent "Buy a Jacket from Amazon" --start-url "https://www.amazon.com" --max-steps 20 --wait-for-login
```

For more options, see the help message:

```bash
uv run -m src.simulated_web_agent.main --help
```

### Running multiple agents (batch mode) from the command line

```bash
uv run -m src.simulated_web_agent.main.run
```
`runConfig.yaml` defines how **multiple simulated agents** are launched and what behavior or survey the agents performs during a batch run. Refer to this following table for how to use the fields in `runConfig.yaml`.

| Field               | Description                                                                                                                                                            |
|---------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **total_personas**  | The total number of virtual agents (personas) to spawn during the batch run. Each persona represents one simulated user.                                               |
| **concurrency**     | The number of agents to run in parallel (e.g., `10` for up to 10 simultaneous browser sessions).                                                                       |
| **demographics**    | Defines sampling categories (e.g., age, gender, shopping frequency) and their relative weights. Each persona randomly samples from these weighted options.             |
| **general_intent**  | A shot, plain-English instruction describing the overall shopping or web browsing goal for all agents.                                                                 |
| **example_persona** | A template persona profile (background, finances, habits, etc.) used to generate diverse personas. All generated personas will follow the same formate as the example. |
| **start_url**       | The base URL where each agent begins the simulated session.                                                                                                            |
| **max_steps**       | The maximum number of actions (clicks, navigations, form fills, etc.) an agent may perform before stopping.                                                            |
| **questionnaire**   | A post-run usability survey shown to each agent, defined with metadata (`id`, `title`) and a list of questions (with type, prompt, and options).                       |

Example `runConfig.yaml` you can get started with:

```yaml
# Number of personas and concurrency
total_personas: 20
concurrency: 10

# Demographic sampling (weighted random)
demographics:
  - name: "Age"
    choices:
      - { name: "18-55", weight: 1 }
  - name: "Gender"
    choices:
      - { name: "male", weight: 1 }
      - { name: "female", weight: 1 }
      - { name: "non-binary", weight: 1 }
  - name: "Online Shopping Frequency"
    choices:
      - { name: "A few times per year", weight: 1 }
      - { name: "A few times per month", weight: 1 }
      - { name: "A few times per week", weight: 1 }

# The general shopping intent for all agents
general_intent: Buy the highest rated product from the meat substitute category within a budget between 100 and 200. You don't need to finish the purchase, just go to the checkout page.

# Example persona template for generation reference
example_persona: |
  Background:
    Male, age 35-44, tech professional, lives in New Jersey.
  Financial Situation:
    Stable income, careful with expenses.
  Shopping Habits:
    Shops online twice a month, prefers Amazon Prime, brand-loyal but open-minded.
  Professional Life:
    Works full-time in tech; balanced lifestyle with family time and hobbies.

# Starting point for the browser agent
start_url: http://52.91.223.130:7770/

# Maximum allowed agent actions
max_steps: 50

# Post-run questionnaire definition
questionnaire:
  questionnaire_id: web_shopping_usability_v1
  title: System Usability Survey
  questions:
    - id: q1
      type: multiple_choice
      prompt: "I think that I would like to use this system frequently. (1 = Strongly disagree, 5 = Strongly agree)"
      options: ["1", "2", "3", "4", "5"]
```

### Using the quick experiment setup UI for multiple agents mode

In addition to configuring batch runs through `runConfig.yaml`, you can also use the **web-based quick experiment setup UI** to launch and manage multiple agents visually.
This interface allows you to adjust parameters such as total personas, concurrency, and intent directly from the browser without manually editing YAML files.

1. Have **flask** and **Node.js / npm** installed
2. From the project root:
   ```bash
   uv run -m src.simulated_web_agent.main.app
   ```
3. Boot up the interface
   ```bash
   cd experiment_ui
   npm install
   npm run dev
   ```
4. You can configure your multi-agent run through the experiment configuration wizard in the interface. (set participant demographics, modify task, edit survey, etc.)
Click "Confirm and Run" in the UI to start the custom configured multi-agent run.

## Results & Data Artifacts
After running a simulation with UXAgent, you’ll find a structured output folder `runs/<timestamp>` containing logs, session traces, screenshots, and aggregate metrics.

---
## License
This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).


## Citation
```bibtex
@article{lu2025uxagent,
  title={UXAgent: A System for Simulating Usability Testing of Web Design with LLM Agents},
  author={Lu, Yuxuan and Yao, Bingsheng and Gu, Hansu and Huang, Jing and Wang, Jessie and Li, Yang and Gesi, Jiri and He, Qi and Li, Toby Jia-Jun and Wang, Dakuo},
  journal={arXiv preprint arXiv:2504.09407},
  year={2025}
}
```
