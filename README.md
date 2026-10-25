# 💸 Splitwise 2.0 — Next-Gen AI Expense Management Engine

A resilient, multimodal group expense management and debt minimization platform built with **Python**, **Streamlit**, and the **Google Gemini API**. 

Unlike conventional bill splitters, **Splitwise 2.0** features an automated multimodal receipt parser, natural language spoken/word expense resolution, dynamic multi-currency conversion, an O(N log N) greedy cash-flow settlement minimizer, and zero-downtime offline fallback architecture.

---

## 🚀 Key Features

### 1. 📸 Multimodal AI Receipt Splitter (Gemini Vision)
- **Line-Item Extraction**: Uploads receipt photos (JPG/PNG) and extracts individual item names, raw amounts, itemized taxes, and discounts.
- **Dynamic Granular Allocation**: Assigns specific dishes/items to individual consumers rather than splitting blind subtotals.
- **Proportional Tax/Discount Distribution**: Distributes overall bill taxes and service fees proportionally based on each individual's consumption ratio.

### 2. 💬 Smart Hybrid NLP Entry Engine (Zero-Downtime Architecture)
- **Natural Language Parsing**: Parses conversational text entries (e.g., *"Rohan bought movie tickets for 1200 with Aman and me"*).
- **Spoken Word & Multi-Currency Detection**: Intelligently maps verbal amounts and currencies (e.g., *"two hundred dollars"*, *"thousand euros"*, *"fifty bucks"*) into base ledger values.
- **503 & Rate-Limit Resiliency**: If external cloud endpoints experience high-traffic spikes (HTTP 503) or rate limits, a deterministic local regex engine intercepts the request instantly with zero UI disruption.

### 3. 🧮 Greedy Debt Minimization (O(N log N))
- **Cash Flow Optimization**: Naive group settling produces O(N^2) circular transactions. Splitwise 2.0 uses a greedy two-pointer debt minimization algorithm to collapse mutual group debts into the absolute minimum number of settlement transfers.
- **Mobile UPI Deep Links & QR Codes**: Dynamically generates NPCI-compliant UPI deep links (`upi://pay`) and scannable QR codes with pre-filled payee IDs and exact settlement amounts for instant settlement via Google Pay, PhonePe, or Paytm.

### 4. ✈️ Trip Mode & Multi-Group Management
- **Lifecycle Trip Mode**: Create temporary event ledgers with automated expiration dates that lock and archive upon conclusion.
- **Dynamic Roster Controls**: Seamlessly create groups, add/remove friends without registration walls, and delete inactive groups.
- **Recurring Schedules & Nudges**: Automate monthly fixed splits (rent, Wi-Fi, subscriptions) with scheduled date trackers and automated balance nudges.

### 5. 💱 Real-Time Forex & Analytics
- **Live Currency Converter**: Built-in interactive currency converter across major global currencies (INR, USD, EUR, GBP, AED, CAD, AUD, SGD, JPY).
- **Data Visualization**: Category spending breakdowns via Plotly charts, keyword transaction filtering, and full ledger CSV export.

---

## 🛠️ Tech Stack

- **Frontend & App Framework**: Streamlit
- **AI & Multimodal Vision**: Google GenAI SDK (gemini-3.8-flash)
- **Data Manipulation & Analytics**: Pandas, Plotly
- **QR Code & Image Processing**: qrcode, Pillow (PIL)
- **Persistence**: JSON-backed local ledger engine with audit trails

---

## 📦 Installation & Local Setup

### 1. Clone the Repository

    git clone https://github.com/BruceWayneTech/splitwise-2.0.git
    cd splitwise-2.0

### 2. Set Up a Virtual Environment (Recommended)

    # Windows
    python -m venv venv
    venv\Scripts\activate

    # macOS / Linux
    python3 -m venv venv
    source venv/bin/activate

### 3. Install Required Dependencies

Create a `requirements.txt` file in the root folder with:

    streamlit>=1.38.0
    google-genai>=0.1.1
    pandas>=2.2.0
    plotly>=5.24.0
    qrcode>=7.4.2
    pillow>=10.4.0

Then run:

    pip install -r requirements.txt

### 4. Configure Your Gemini API Key

Create a `.streamlit` folder in your project root, and inside it add a file named `secrets.toml`:

    # .streamlit/secrets.toml
    GEMINI_API_KEY = "your_actual_gemini_api_key_here"

*(Alternatively, you can export it in your terminal as an environment variable: `export GEMINI_API_KEY="your_api_key"`)*

### 5. Run the Application

    streamlit run app.py

Streamlit will automatically open `http://localhost:8501` in your default browser.

---

## 🔒 Security & Privacy

- `.streamlit/secrets.toml` and runtime data files (`splitwise_ledger.json`) are excluded via `.gitignore` to prevent leaking private credentials or expense data to version control.
- Designed with zero mandatory sign-up walls for participants, prioritizing fast onboarding and frictionless tracking.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
