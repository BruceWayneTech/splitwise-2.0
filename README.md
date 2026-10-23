# 🤝 Splitwise 2.0 - Optimal Expense Ledger Engine

A full-stack, rapid-deployment expense tracking system designed to log transactions, map expenses, and optimize group settlement networks using an algorithmic greedy cash-flow router.

## 🚀 Core Engine Features
* **Optimal Settlement Engine:** Built using a greedy Min-Cash-Flow network optimization algorithm to condense complex group balances down to the fewest possible transaction steps.
* **Smart UI Dashboard:** Clean dual-column design built with Streamlit featuring responsive metrics cards for total group outlay, member size, and entry counts.
* **Spend Segmentation Analysis:** Integrated live category allocation visual charts graphing spending habits instantly.
* **Flexible Accounting Controls:** Interactive user profile registration, instant line-item deletion hooks, global database purge safety controls, and multi-currency selectors.

## 🛠|| Local System Installation Guide
1. Open terminal in the directory root and build the isolated environment:
   ```bash
   python -m venv venv
   ```
2. Activate the virtual environment path:
   * Windows: `.\venv\Scripts\activate`
3. Install necessary application core packages:
   ```bash
   pip install streamlit google-genai
   ```
4. Boot the application engine dashboard interface locally:
   ```bash
   streamlit run app.py
   ```
