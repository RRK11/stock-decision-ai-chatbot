import os
import csv
import re
from datetime import datetime

import gradio as gr
import yfinance as yf
from dotenv import load_dotenv
from openai import OpenAI


# -----------------------------
# Setup
# -----------------------------
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# -----------------------------
# Helper Functions
# -----------------------------
def safe_round(value, decimals=2):
    if value is None or value == "N/A":
        return "N/A"
    try:
        return round(value, decimals)
    except Exception:
        return value


def format_large_number(value):
    if value is None or value == "N/A":
        return "N/A"

    try:
        value = float(value)
        if value >= 1_000_000_000_000:
            return f"${value / 1_000_000_000_000:.2f}T"
        elif value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        else:
            return f"${value:,.0f}"
    except Exception:
        return value


def get_valid_ticker(message):
    """
    Pulls likely ticker symbols from a user message.
    This avoids treating words like I, BUY, SHOULD, APP, etc. as tickers.
    """
    possible = re.findall(r"\b[A-Z]{1,5}\b", message.upper())

    common_words = {
        "I", "A", "AN", "BUY", "SELL", "HOLD", "AVOID", "AND", "OR", "THE",
        "FOR", "WITH", "WHAT", "WHY", "HOW", "IS", "ARE", "AI", "API", "PE",
        "P", "E", "DOES", "THIS", "APP", "HELLO", "PLEASE", "SHOULD", "CAN",
        "YOU", "ME", "MY", "YOUR", "TO", "OF", "IN", "ON", "AT", "IT", "AS",
        "VS", "V", "COMPARE", "ANALYZE", "REPORT", "EVALUATE", "EXPLAIN"
    }

    tickers = [word for word in possible if word not in common_words]

    return tickers


# -----------------------------
# Yahoo Finance Scoring Model
# -----------------------------
def get_score_components(ticker):
    ticker = ticker.upper().strip()
    stock = yf.Ticker(ticker)
    info = stock.info

    if not info or not info.get("quoteType"):
        raise ValueError(f"Invalid or unsupported ticker symbol: {ticker}")

    price = info.get("currentPrice") or info.get("regularMarketPrice")

    if price is None:
        raise ValueError(f"Could not retrieve current price for ticker: {ticker}")

    score = 0
    reasons = []

    categories = {
        "Valuation": "N/A",
        "Profitability": "N/A",
        "Growth": "N/A",
        "Debt/Risk": "N/A",
        "Efficiency": "N/A"
    }

    pe = info.get("trailingPE")
    profit_margin = info.get("profitMargins")
    revenue_growth = info.get("revenueGrowth")
    debt_to_equity = info.get("debtToEquity")
    roe = info.get("returnOnEquity")

    # Valuation
    if pe is not None:
        if pe < 20:
            score += 2
            categories["Valuation"] = "Strong"
            reasons.append("P/E is below 20, which suggests valuation may be reasonable.")
        elif pe < 35:
            score += 1
            categories["Valuation"] = "Moderate"
            reasons.append("P/E is acceptable, but not especially cheap.")
        else:
            score -= 1
            categories["Valuation"] = "Weak"
            reasons.append("P/E is elevated, which creates valuation risk.")
    else:
        reasons.append("P/E data was unavailable.")

    # Profitability
    if profit_margin is not None:
        if profit_margin > 0.15:
            score += 2
            categories["Profitability"] = "Strong"
            reasons.append("Profit margin is above 15%, showing strong profitability.")
        elif profit_margin > 0.05:
            score += 1
            categories["Profitability"] = "Moderate"
            reasons.append("Profit margin is positive but not exceptional.")
        else:
            categories["Profitability"] = "Weak"
            reasons.append("Profit margin is weak or very low.")
    else:
        reasons.append("Profit margin data was unavailable.")

    # Growth
    if revenue_growth is not None:
        if revenue_growth > 0.10:
            score += 2
            categories["Growth"] = "Strong"
            reasons.append("Revenue growth is above 10%, showing strong expansion.")
        elif revenue_growth > 0.03:
            score += 1
            categories["Growth"] = "Moderate"
            reasons.append("Revenue growth is modest but positive.")
        else:
            categories["Growth"] = "Weak"
            reasons.append("Revenue growth is limited or negative.")
    else:
        reasons.append("Revenue growth data was unavailable.")

    # Debt/Risk
    if debt_to_equity is not None:
        if debt_to_equity < 100:
            score += 2
            categories["Debt/Risk"] = "Strong"
            reasons.append("Debt-to-equity is below 100, suggesting manageable leverage.")
        elif debt_to_equity > 200:
            score -= 1
            categories["Debt/Risk"] = "Weak"
            reasons.append("Debt-to-equity is above 200, suggesting elevated leverage risk.")
        else:
            score += 1
            categories["Debt/Risk"] = "Moderate"
            reasons.append("Debt levels appear moderate.")
    else:
        reasons.append("Debt-to-equity data was unavailable.")

    # Efficiency
    if roe is not None:
        if roe > 0.15:
            score += 2
            categories["Efficiency"] = "Strong"
            reasons.append("ROE is above 15%, suggesting efficient use of shareholder capital.")
        elif roe > 0.08:
            score += 1
            categories["Efficiency"] = "Moderate"
            reasons.append("ROE is acceptable.")
        else:
            categories["Efficiency"] = "Weak"
            reasons.append("ROE is weak or limited.")
    else:
        reasons.append("ROE data was unavailable.")

    if score >= 7:
        recommendation = "BUY"
    elif score >= 4:
        recommendation = "HOLD"
    else:
        recommendation = "AVOID"

    if score >= 8:
        confidence = "High"
    elif score >= 5:
        confidence = "Moderate"
    else:
        confidence = "Low"

    return {
        "ticker": ticker,
        "company": info.get("longName", ticker),
        "sector": info.get("sector", "N/A"),
        "price": price,
        "market_cap": info.get("marketCap", "N/A"),
        "pe": pe,
        "profit_margin": profit_margin,
        "revenue_growth": revenue_growth,
        "debt_to_equity": debt_to_equity,
        "roe": roe,
        "score": score,
        "recommendation": recommendation,
        "confidence": confidence,
        "categories": categories,
        "reasons": reasons
    }


# -----------------------------
# Report Functions
# -----------------------------
def stock_report(ticker):
    data = get_score_components(ticker)

    bull_case = []
    bear_case = []

    for category, rating in data["categories"].items():
        if rating == "Strong":
            bull_case.append(f"{category} is strong.")
        elif rating == "Weak":
            bear_case.append(f"{category} is weak.")

    if not bull_case:
        bull_case.append("The stock does not show many clear strengths based on the available metrics.")

    if not bear_case:
        bear_case.append("The stock does not show many major red flags based on the available metrics.")

    return f"""
## Recommendation
**{data['recommendation']}**

## Confidence
**{data['confidence']}**

## Score
**{data['score']}/10**

## Company Snapshot
- Company: {data['company']}
- Ticker: {data['ticker']}
- Sector: {data['sector']}
- Current Price: ${safe_round(data['price'])}
- Market Cap: {format_large_number(data['market_cap'])}

## Scorecard
- Valuation: {data['categories']['Valuation']}
- Profitability: {data['categories']['Profitability']}
- Growth: {data['categories']['Growth']}
- Debt/Risk: {data['categories']['Debt/Risk']}
- Efficiency: {data['categories']['Efficiency']}

## Key Metrics
- P/E Ratio: {safe_round(data['pe'])}
- Profit Margin: {safe_round(data['profit_margin'])}
- Revenue Growth: {safe_round(data['revenue_growth'])}
- Debt-to-Equity: {safe_round(data['debt_to_equity'])}
- Return on Equity: {safe_round(data['roe'])}

## Bull Case
- """ + "\n- ".join(bull_case) + """

## Bear Case
- """ + "\n- ".join(bear_case) + """

## Model Reasoning
- """ + "\n- ".join(data["reasons"]) + f"""

## Final Take
Based on the available Yahoo Finance metrics, **{data['ticker']} receives a {data['recommendation']} rating with {data['confidence'].lower()} confidence.**

This is for educational purposes only and should not be considered financial advice.
"""


def compare_two_stocks(ticker1, ticker2):
    first = get_score_components(ticker1)
    second = get_score_components(ticker2)

    if first["score"] > second["score"]:
        winner = first["ticker"]
    elif second["score"] > first["score"]:
        winner = second["ticker"]
    else:
        winner = "Tie"

    return f"""
## Stock Comparison
**{first['ticker']} vs. {second['ticker']}**

## Overall Scores
- **{first['ticker']}**: {first['score']}/10 | Recommendation: {first['recommendation']} | Confidence: {first['confidence']}
- **{second['ticker']}**: {second['score']}/10 | Recommendation: {second['recommendation']} | Confidence: {second['confidence']}

## Company Snapshot
- **{first['ticker']}**: {first['company']} | Sector: {first['sector']} | Price: ${safe_round(first['price'])}
- **{second['ticker']}**: {second['company']} | Sector: {second['sector']} | Price: ${safe_round(second['price'])}

## Metric Comparison
- P/E Ratio: {first['ticker']} = {safe_round(first['pe'])}, {second['ticker']} = {safe_round(second['pe'])}
- Profit Margin: {first['ticker']} = {safe_round(first['profit_margin'])}, {second['ticker']} = {safe_round(second['profit_margin'])}
- Revenue Growth: {first['ticker']} = {safe_round(first['revenue_growth'])}, {second['ticker']} = {safe_round(second['revenue_growth'])}
- Debt-to-Equity: {first['ticker']} = {safe_round(first['debt_to_equity'])}, {second['ticker']} = {safe_round(second['debt_to_equity'])}
- Return on Equity: {first['ticker']} = {safe_round(first['roe'])}, {second['ticker']} = {safe_round(second['roe'])}

## Scorecard
- **{first['ticker']}**: Valuation {first['categories']['Valuation']}, Profitability {first['categories']['Profitability']}, Growth {first['categories']['Growth']}, Debt/Risk {first['categories']['Debt/Risk']}, Efficiency {first['categories']['Efficiency']}
- **{second['ticker']}**: Valuation {second['categories']['Valuation']}, Profitability {second['categories']['Profitability']}, Growth {second['categories']['Growth']}, Debt/Risk {second['categories']['Debt/Risk']}, Efficiency {second['categories']['Efficiency']}

## Stronger Pick Based on This Model
**{winner}**

## Final Take
This comparison is based on a simplified scoring model using Yahoo Finance data.

This is for educational purposes only and should not be considered financial advice.
"""


def raw_stock_data(ticker):
    data = get_score_components(ticker)

    return f"""
## Raw Stock Data

- Company: {data['company']}
- Ticker: {data['ticker']}
- Sector: {data['sector']}
- Current Price: ${safe_round(data['price'])}
- Market Cap: {format_large_number(data['market_cap'])}
- P/E Ratio: {safe_round(data['pe'])}
- Profit Margin: {safe_round(data['profit_margin'])}
- Revenue Growth: {safe_round(data['revenue_growth'])}
- Debt-to-Equity: {safe_round(data['debt_to_equity'])}
- Return on Equity: {safe_round(data['roe'])}
"""


# -----------------------------
# OpenAI Explanation Function
# -----------------------------
def ask_openai(prompt):
    try:
        if not os.getenv("OPENAI_API_KEY"):
            return "⚠️ Missing OPENAI_API_KEY. Add it to your .env file locally or Hugging Face Secrets."

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI Equity Research Assistant. "
                        "Be professional, concise, structured, and educational. "
                        "Do not guarantee returns. Always remind users that this is not financial advice."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"⚠️ OpenAI error: {e}"


def explain_finance_question(question):
    try:
        with open("knowledge_base.md", "r", encoding="utf-8") as file:
            knowledge = file.read()

        prompt = f"""
Use the finance knowledge base below to answer the user's question clearly.

Finance Knowledge Base:
{knowledge}

User Question:
{question}
"""
        return ask_openai(prompt)

    except Exception:
        return ask_openai(f"Answer this finance concept question clearly and simply: {question}")


def explain_app():
    return """
## What This App Does

This app is an **AI Equity Research Assistant**. It combines:

1. **Yahoo Finance data**
2. **A custom stock scoring model**
3. **OpenAI-powered explanations**

## Main Features

### Stock Reports
Ask questions like:

**Should I buy AAPL?**

The app pulls Yahoo Finance data, scores the stock, and gives a simplified recommendation: **BUY**, **HOLD**, or **AVOID**.

### Stock Comparisons
Ask:

**Compare MSFT and GOOGL**

The app compares both companies side-by-side using valuation, profitability, growth, leverage, and efficiency metrics.

### Finance Education
Ask:

**What is a P/E ratio?**

The app explains finance concepts in plain English.

## Scoring Model

The stock score is based on five categories:

- Valuation
- Profitability
- Growth
- Debt/Risk
- Efficiency

Each category adds or subtracts points based on financial metrics from Yahoo Finance.

## Important Disclaimer

This app is for educational purposes only and should not be considered financial advice.
"""


# -----------------------------
# Logging
# -----------------------------
def log_conversation(user_message, bot_response):
    file_exists = os.path.isfile("chat_logs.csv")

    with open("chat_logs.csv", "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow(["timestamp", "user_message", "bot_response"])

        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_message,
            bot_response
        ])


# -----------------------------
# Main Chat Function
# -----------------------------
def chat(message, history):
    try:
        lower_msg = message.lower()
        tickers = get_valid_ticker(message)

        print("User question:", message)
        print("Extracted tickers:", tickers)

        if any(phrase in lower_msg for phrase in ["what does this app do", "explain this app", "how does this app work"]):
            bot_response = explain_app()

        elif any(word in lower_msg for word in ["compare", "versus", "vs", "better"]) and len(tickers) >= 2:
            bot_response = compare_two_stocks(tickers[0], tickers[1])

        elif any(word in lower_msg for word in ["buy", "hold", "avoid", "analyze", "report", "evaluate"]) and len(tickers) >= 1:
            bot_response = stock_report(tickers[-1])

        elif any(word in lower_msg for word in ["data", "metrics", "price", "market cap", "p/e"]) and len(tickers) >= 1:
            bot_response = raw_stock_data(tickers[-1])

        else:
            bot_response = explain_finance_question(message)

        log_conversation(message, bot_response)
        return bot_response

    except Exception as e:
        error_message = f"Something went wrong: {e}"
        log_conversation(message, error_message)
        return error_message


# -----------------------------
# Gradio App
# -----------------------------
demo = gr.ChatInterface(
    fn=chat,
    title="AI Equity Research Assistant",
    description=(
        "Ask for a stock report, compare two stocks, or learn finance concepts using "
        "Yahoo Finance data and OpenAI-powered financial analysis."
    ),
    examples=[
        "Should I buy AAPL?",
        "Compare MSFT and GOOGL",
        "Analyze NVDA",
        "Show me TSLA metrics",
        "What is a P/E ratio?",
        "How does the scoring model work?",
        "What does this app do?"
    ]
)


if __name__ == "__main__":
    demo.launch()