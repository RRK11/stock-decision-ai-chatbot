---
title: AI Equity Research Assistant
emoji: 📈
colorFrom: blue
colorTo: indigo
sdk: gradio
python_version: "3.11"
app_file: app.py
pinned: false
---

# AI Equity Research Assistant

## Project Overview

This project is an AI-powered financial analysis chatbot that helps users evaluate stocks and understand key investment concepts.  
It combines real-time financial data with AI-generated insights to provide structured buy/hold/avoid style recommendations.

The application is deployed as an interactive web app using Gradio on Hugging Face Spaces.

---

## Live Demo

Try the app here:(https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME)

---

## Features

-  **Stock Analysis** — Evaluate a stock with a structured recommendation
-  **Stock Comparison** — Compare two companies side-by-side
-  **Finance Knowledge Base** — Explain financial concepts (P/E ratio, ROE, etc.)
-  **Real Data Integration** — Pulls live data from Yahoo Finance
-  **Structured Output** — Clear, analyst-style responses
-  **Conversational Interface** — Natural language interaction
-  **Chat Logging** — Stores conversations for review

---

## Tech Stack

- **Python**
- **Gradio** (UI)
- **LangChain** (agent + tool orchestration)
- **Google Gemini API** (LLM)
- **Yahoo Finance (yfinance)** (financial data)
- **Hugging Face Spaces** (deployment)
- **Pandas / CSV** (logging + data handling)

---

## How It Works

The system uses a **LangChain agent** connected to multiple tools:

### Tools

- `stock_report` → Generates structured analysis for a single stock  
- `compare_two_stocks` → Side-by-side comparison  
- `get_stock_data` → Raw financial metrics  
- `finance_knowledge_base` → Answers finance questions  

The agent decides which tool to use based on the user’s prompt.

---

## Scoring Model

Each stock is evaluated using a custom scoring system based on:

- Valuation (P/E ratio)
- Profitability (profit margins)
- Growth (revenue growth)
- Risk (debt-to-equity)
- Efficiency (return on equity)

### Example scoring logic:

| Category       | Strong | Moderate | Weak |
|----------------|--------|----------|------|
| Valuation      | +2     | +1       | -1   |
| Profitability  | +2     | +1       | 0    |
| Growth         | +2     | +1       | 0    |
| Debt/Risk      | +2     | +1       | -1   |
| Efficiency     | +2     | +1       | 0    |

### Final Recommendation:

- **BUY** → Score ≥ 7  
- **HOLD** → Score 4–6  
- **AVOID** → Score < 4  

---

## Example Prompts

Try asking:

- "Should I buy AAPL?"
- "Compare MSFT and GOOGL"
- "Analyze NVDA"
- "What is a P/E ratio?"
- "How does the scoring model work?"

---

## Limitations

- Data depends on Yahoo Finance API availability
- Some financial metrics may be missing for certain companies
- AI responses are generated and may not always be perfect
- Not a substitute for professional financial advice

---

## Future Improvements

- Add stock price charts and visualizations
- Incorporate news sentiment analysis
- Add portfolio tracking features
- Improve scoring model with more advanced metrics
- Integrate additional financial data sources

---

## Author

**Ryan Kasper**  
Finance & Information Systems Student  
Gonzaga University  

---

## Disclaimer

This tool is for educational purposes only and should not be considered financial advice.  
Always conduct your own research before making investment decisions.
