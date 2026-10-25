# 💸 Splitwise 2.0

> An intelligent, next-generation group expense ledger powered by Google Gemini Vision & NLP, featuring algorithmic debt minimization, UPI-native settlement, and temporary self-closing trip groups.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Google Gemini](https://img.shields.io/badge/Google%20GenAI-Gemini%203.8%20Flash-4E75F6.svg?logo=google&logoColor=white)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

## 📌 Problem Statement & Solution

Traditional group expense apps like Splitwise solved the manual arithmetic of who owes whom, but have not evolved past their original design:
- **Manual Data Entry**: Every receipt line item has to be manually typed in, encouraging unfair equal splits.
- **Disconnected Settlements**: Apps show balances, but users must leave the app, pay via UPI separately, and remember to manually mark debts settled.
- **Tangled Debts**: Instead of clean net transfers, small pairwise debts accumulate into chaotic payment webs.
- **Permanent Clutter**: One-off groups (weekend trips, college fests, flat dinners) linger forever without a clean closure.

**Splitwise 2.0** solves this by layering an **Intelligence Layer** (Gemini Vision OCR + Resilient NLP Engine) and a **Payments Layer** (UPI deep-links and dynamic QR codes) directly over a robust, multi-method core expense ledger.

---

## 🚀 Key Features Implemented

### 1. Flexible Core Splitting (4 Methods)
Every expense can be split:
- **Equally** across all group members.
- By **Exact Amount** per person.
- By **Percentage (%)** of the bill.
- By **Shares / Ratios** (e.g., 2 shares for person A, 1 share for person B).

### 2. Smart AI Bill Splitter (Gemini Vision OCR)
- Upload photos or screenshots of itemized restaurant and shopping receipts.
- Powered by `gemini-3.8-flash` vision with zero-latency thinking config to extract item names, quantities, taxes, and discounts into structured data.
- Interactive multi-select UI lets group members tag what they ordered. Taxes and discounts are automatically calculated and distributed proportionally.

### 3. Natural Language Expense Entry (Resilient Hybrid NLP)
- Log expenses by typing plain-English sentences:  
  *`"I paid 1500 for dinner for me, Aman and Rohan"`*
- Uses Google Gemini to extract the payer, amount, participants, and category with an instant local fallback engine ensuring zero downtime even during cloud capacity spikes.
- Includes a mandatory confirmation screen before committing data to the ledger.

### 4. "Who Owes Whom" Debt Minimizer
- Nets down every individual's balance in the group.
- Executes an optimal greedy balance matching algorithm ($O(N \log N)$) that collapses tangled multi-party webs of small debts into the minimum possible number of direct settlements.

### 5. Native UPI Settle-Up
- Eliminates manual app-switching with dynamically generated `upi://pay` deep links and on-the-fly QR codes for instant mobile payment apps (GPay, PhonePe, Paytm).
- Supports both full payments and partial settlement tracking.

### 6. Trip Mode (Self-Closing Groups)
- Temporary group flag with an expiration end date for trips, hostel events, and festivals.
- Automatically flags when an event has concluded and archives the group with a finalized closure summary.

### 7. Recurring Expenses & Automated Nudges
- Scheduler that auto-generates repeat monthly expenses (rent, Wi-Fi, shared streaming subscriptions) when due.
- Active nudges for outstanding unpaid balances.

### 8. Frictionless Roster (No Sign-Up Required)
- Add friends and flatmates to the group ledger using their name, email, or phone number without requiring them to download or register first.

### 9. Analytics, Audit Trail & CSV Export
- Interactive Plotly spending breakdowns by category and contributor.
- Live keyword search across historical records.
- Immutable audit log tracking changes and payments.
- One-click export of group ledgers to CSV.

---

## 🛠️ Architecture & Tech Stack

```text
[ User / Browser ]
        │
        ▼
[ Streamlit UI Layer ] ─── (Tabs: Ledger | AI Bill | NLP Add | Analytics | Recurring)
        │
   ┌────┴───────────────────────────┬──────────────────────────┐
   ▼                                ▼                          ▼
[ Intelligence Layer ]      [ Core Ledger Engine ]      [ Payments Layer ]
 • Gemini 3.8 Flash Vision   • 4 Split Math Calculators   • UPI URI Builder
 • Zero-Lag NLP Parser       • Greedy Debt Minimizer      • Dynamic QR Codes
 • Resilient Fallback Engine • JSON State Persistence     • Partial Settlements
