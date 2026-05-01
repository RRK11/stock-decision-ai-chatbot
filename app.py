import os
import csv
from datetime import datetime

import gradio as gr
import yfinance as yf
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from langchain.agents import create_agent


load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.2
)


def safe_round(value, decimals=2):
    if value is None or value == "N/A":
        return "N/A"
    try:
        return round(value, decimals)
    except Exception:
        return value


def get_score_components(ticker):
    ticker = ticker.upper().strip()
    stock = yf.Ticker(ticker)
    info = stock.info

    if not info or "currentPrice" not in info:
        raise ValueError("Invalid or unsupported ticker symbol.")

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

    # Debt / Risk
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
        "price": info.get("currentPrice", "N/A"),
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


@tool
def get_stock_data(ticker: str) -> str:
    """
    Pulls basic stock financial data for a given ticker symbol.
    Example input: AAPL, MSFT, NVDA
    """
    try:
        data = get_score_components(ticker)

        return f"""
Company: {data['company']}
Ticker: {data['ticker']}
Sector: {data['sector']}
Current Price: {data['price']}
Market Cap: {data['market_cap']}
P/E Ratio: {safe_round(data['pe'])}
Profit Margin: {safe_round(data['profit_margin'])}
Revenue Growth: {safe_round(data['revenue_growth'])}
Debt-to-Equity: {safe_round(data['debt_to_equity'])}
Return on Equity: {safe_round(data['roe'])}
"""
    except Exception as e:
        return f"Error pulling stock data: {e}"


@tool
def stock_report(ticker: str) -> str:
    """
    Creates a professional mini equity research style report for one stock.
    Use this when a user asks whether to buy, hold, avoid, analyze, or evaluate a stock.
    """
    try:
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
Recommendation: {data['recommendation']}
Confidence: {data['confidence']}
Confidence Explanation: The confidence level reflects how consistent the financial signals are across valuation, profitability, growth, debt/risk, and efficiency metrics.
Score: {data['score']}/10

Company Snapshot:
- Company: {data['company']}
- Ticker: {data['ticker']}
- Sector: {data['sector']}
- Current Price: {data['price']}
- Market Cap: {data['market_cap']}

Scorecard:
- Valuation: {data['categories']['Valuation']}
- Profitability: {data['categories']['Profitability']}
- Growth: {data['categories']['Growth']}
- Debt/Risk: {data['categories']['Debt/Risk']}
- Efficiency: {data['categories']['Efficiency']}

Key Metrics:
- P/E Ratio: {safe_round(data['pe'])}
- Profit Margin: {safe_round(data['profit_margin'])}
- Revenue Growth: {safe_round(data['revenue_growth'])}
- Debt-to-Equity: {safe_round(data['debt_to_equity'])}
- Return on Equity: {safe_round(data['roe'])}

Bull Case:
- """ + "\n- ".join(bull_case) + """

Bear Case:
- """ + "\n- ".join(bear_case) + """

Reasoning:
- """ + "\n- ".join(data["reasons"]) + f"""

Final Take:
Based on the available financial metrics, {data['ticker']} receives a {data['recommendation']} rating with {data['confidence'].lower()} confidence.

This is for educational purposes only and should not be considered financial advice.
"""
    except Exception as e:
        return f"Error creating stock report: {e}"


@tool
def compare_two_stocks(tickers: str) -> str:
    """
    Compares two stocks side-by-side.
    Input should be two tickers separated by a comma, such as: AAPL, MSFT
    """
    try:
        parts = [
            x.strip().upper()
            for x in tickers.replace(" and ", ",").replace("&", ",").split(",")
            if x.strip()
        ]

        if len(parts) != 2:
            return "Please provide exactly two tickers, such as: AAPL, MSFT"

        first = get_score_components(parts[0])
        second = get_score_components(parts[1])

        if first["score"] > second["score"]:
            winner = first["ticker"]
        elif second["score"] > first["score"]:
            winner = second["ticker"]
        else:
            winner = "Tie"

        return f"""
Stock Comparison: {first['ticker']} vs. {second['ticker']}

Overall Scores:
- {first['ticker']}: {first['score']}/10, Recommendation: {first['recommendation']}, Confidence: {first['confidence']}
- {second['ticker']}: {second['score']}/10, Recommendation: {second['recommendation']}, Confidence: {second['confidence']}

Company Snapshot:
- {first['ticker']}: {first['company']} | Sector: {first['sector']} | Price: {first['price']}
- {second['ticker']}: {second['company']} | Sector: {second['sector']} | Price: {second['price']}

Metric Comparison:
- P/E Ratio: {first['ticker']} = {safe_round(first['pe'])}, {second['ticker']} = {safe_round(second['pe'])}
- Profit Margin: {first['ticker']} = {safe_round(first['profit_margin'])}, {second['ticker']} = {safe_round(second['profit_margin'])}
- Revenue Growth: {first['ticker']} = {safe_round(first['revenue_growth'])}, {second['ticker']} = {safe_round(second['revenue_growth'])}
- Debt-to-Equity: {first['ticker']} = {safe_round(first['debt_to_equity'])}, {second['ticker']} = {safe_round(second['debt_to_equity'])}
- Return on Equity: {first['ticker']} = {safe_round(first['roe'])}, {second['ticker']} = {safe_round(second['roe'])}

Scorecard:
- {first['ticker']}: Valuation {first['categories']['Valuation']}, Profitability {first['categories']['Profitability']}, Growth {first['categories']['Growth']}, Debt/Risk {first['categories']['Debt/Risk']}, Efficiency {first['categories']['Efficiency']}
- {second['ticker']}: Valuation {second['categories']['Valuation']}, Profitability {second['categories']['Profitability']}, Growth {second['categories']['Growth']}, Debt/Risk {second['categories']['Debt/Risk']}, Efficiency {second['categories']['Efficiency']}

Stronger Pick Based on This Model:
- {winner}

Why:
The stronger pick is based on the overall score, which reflects a combination of valuation, profitability, growth, leverage, and efficiency metrics.

Final Take:
This comparison is based on a simplified scoring model using valuation, profitability, growth, leverage, and efficiency metrics.

This is for educational purposes only and should not be considered financial advice.
"""
    except Exception as e:
        return f"Error comparing stocks: {e}"


@tool
def finance_knowledge_base(question: str) -> str:
    """
    Answers finance concept questions using the local knowledge base.
    """
    try:
        with open("knowledge_base.md", "r", encoding="utf-8") as file:
            knowledge = file.read()

        return f"""
Finance Knowledge Base:
{knowledge}

User Question:
{question}
"""
    except Exception as e:
        return f"Error reading knowledge base: {e}"


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


tools = [
    get_stock_data,
    stock_report,
    compare_two_stocks,
    finance_knowledge_base
]


agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="""
You are an AI Stock Decision & Risk Analysis Bot.

Your job is to analyze stocks like a financial analyst.

Tool routing:
- Use stock_report when the user asks whether to buy, hold, avoid, analyze, or evaluate one stock.
- Use compare_two_stocks when the user asks to compare two stocks.
- Use get_stock_data when the user only asks for raw stock data or financial metrics.
- Use finance_knowledge_base when the user asks about finance concepts or how the model works.

Response style:
- Use clear headers.
- Be professional and concise.
- Interpret the numbers rather than only listing them.
- Highlight both bull case and bear case when analyzing a stock.
- If data is missing or unclear, say so instead of guessing.
- For follow-up questions, use the conversation history to understand what the user is referring to.

Important:
- This is educational and should not be considered financial advice.
- Do not guarantee investment returns.
"""
)


def chat(message, history):
    try:
        messages = []

        if history:
            for item in history:
                if isinstance(item, dict):
                    role = item.get("role")
                    content = item.get("content")
                    if role and content:
                        messages.append({"role": role, "content": content})

                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    user_msg, bot_msg = item
                    if user_msg:
                        messages.append({"role": "user", "content": user_msg})
                    if bot_msg:
                        messages.append({"role": "assistant", "content": bot_msg})

        messages.append({"role": "user", "content": message})

        response = agent.invoke({"messages": messages})

        bot_response = response["messages"][-1].content

        log_conversation(message, bot_response)

        return bot_response

    except Exception as e:
        error_message = f"Something went wrong: {e}"
        log_conversation(message, error_message)
        return error_message


demo = gr.ChatInterface(
    fn=chat,
    title="AI Stock Decision & Risk Analysis Bot",
    description="Ask for a stock report, compare two stocks, or learn finance concepts using an AI-powered financial analysis assistant."
)

if __name__ == "__main__":
    demo.launch()