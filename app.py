import streamlit as st
import json
import os

# --- STORAGE CONFIGURATION ---
DB_FILE = "ledger.json"

def load_data():
    if not os.path.exists(DB_FILE):
        return {
            "users": ["Me", "Aman", "Rohan"], 
            "expenses": [], 
            "currency": "₹"
        }
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- DEBT SIMPLIFICATION ENGINE (GREEDY MIN-CASH-FLOW) ---
def calculate_balances(expenses):
    balances = {}
    for exp in expenses:
        payer = exp["payer"]
        amount = float(exp["amount"])
        participants = exp["participants"]
        if not participants: continue
        split_amount = amount / len(participants)
        
        balances[payer] = balances.get(payer, 0.0) + amount
        for p in participants:
            balances[p] = balances.get(p, 0.0) - split_amount
    return balances

def simplify_debts(balances):
    net_balances = {k: round(v, 2) for k, v in balances.items() if abs(v) > 0.01}
    debtors = [[k, v] for k, v in net_balances.items() if v < 0]
    creditors = [[k, v] for k, v in net_balances.items() if v > 0]
    transactions = []
    
    while debtors and creditors:
        debtors.sort(key=lambda x: x[1])  # Sort by deepest debt
        creditors.sort(key=lambda x: x[1], reverse=True) # Sort by largest credit
        
        debtor_name, debtor_amt = debtors[0]
        creditor_name, creditor_amt = creditors[0]
        
        amount_to_pay = min(abs(debtor_amt), creditor_amt)
        
        transactions.append({
            "from": debtor_name, 
            "to": creditor_name, 
            "amount": round(amount_to_pay, 2)
        })
        
        debtors[0][1] += amount_to_pay
        creditors[0][1] -= amount_to_pay
        
        if abs(debtors[0][1]) < 0.01: debtors.pop(0)
        if abs(creditors[0][1]) < 0.01: creditors.pop(0)
    return transactions

# --- USER INTERFACE APP LAYER ---
st.set_page_config(page_title="Splitwise 2.0 Web Engine", layout="wide")
st.title("🤝 Splitwise 2.0 Professional Ledger")

data = load_data()

# --- SIDEBAR CONTROLS ---
st.sidebar.header("⚙️ Application Controls")

# Currency Switcher Feature
currency_options = ["₹", "$", "€", "£"]
current_curr_idx = currency_options.index(data.get("currency", "₹")) if data.get("currency") in currency_options else 0
selected_currency = st.sidebar.selectbox("Preferred Currency Symbol:", options=currency_options, index=current_curr_idx)

if selected_currency != data.get("currency"):
    data["currency"] = selected_currency
    save_data(data)
    st.rerun()

curr = data["currency"]

st.sidebar.markdown("---")
st.sidebar.subheader("Group Member Setup")
new_member = st.sidebar.text_input("Enter Member Name:")
if st.sidebar.button("➕ Register Member"):
    if new_member and new_member not in data["users"]:
        data["users"].append(new_member)
        save_data(data)
        st.sidebar.success(f"Registered {new_member}!")
        st.rerun()

registered_users = data["users"]

# Danger Zone - Master Reset Feature
st.sidebar.markdown("---")
st.sidebar.subheader("🚨 Emergency Options")
if st.sidebar.button("🗑️ Reset Entire Ledger", help="Completely wipe all transactions and reset data profiles"):
    data = {"users": ["Me", "Aman", "Rohan"], "expenses": [], "currency": "₹"}
    save_data(data)
    st.sidebar.success("Database wiped successfully!")
    st.rerun()

# --- HEADER METRICS DASHBOARD PANELS ---
expenses_list = data.get("expenses", [])
total_spend = sum(float(e["amount"]) for e in expenses_list)
total_transactions_count = len(expenses_list)

col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    st.metric("Total Group Outlay", f"{curr} {total_spend:,.2f}")
with col_m2:
    st.metric("Logged Expense Entries", f"{total_transactions_count} Items")
with col_m3:
    st.metric("Registered Group Size", f"{len(registered_users)} Members")

st.markdown("---")

# --- MAIN TWO-COLUMN DASHBOARD GRID LAYOUT ---
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📝 Record A Group Expense")
    with st.form("expense_form", clear_on_submit=True):
        description = st.text_input("What was paid for? (e.g., Cafe Bill, Airbnb, Uber)")
        amount = st.number_input(f"Total Amount Spent ({curr})", min_value=0.0, step=50.0)
        payer = st.selectbox("Who paid the transaction bill?", options=registered_users)
        participants = st.multiselect("Who splits this cost?", options=registered_users, default=registered_users)
        
        # Categorisation metric enhancement
        category = st.selectbox("Expense Allocation Category:", ["Food & Dining", "Travel & Transit", "Lodging & Stay", "Entertainment", "Utilities & Misc"])
        
        if st.form_submit_button("⚡ Append to Ledger"):
            if description and amount > 0:
                if not participants:
                    st.error("An expense must be shared by at least 1 group member.")
                else:
                    new_expense = {
                        "description": description,
                        "amount": amount,
                        "payer": payer,
                        "participants": participants,
                        "category": category
                    }
                    data["expenses"].append(new_expense)
                    save_data(data)
                    st.success(f"Saved entry for '{description}' cleanly!")
                    st.rerun()
            else:
                st.error("Please fill in a description title and valid transaction amount value.")

    # --- CATEGORY DATA VISUALISATION CHART FEATURE ---
    st.markdown("---")
    st.subheader("📊 Spend Segmentation Analysis")
    if expenses_list:
        category_totals = {}
        for e in expenses_list:
            cat = e.get("category", "Utilities & Misc")
            category_totals[cat] = category_totals.get(cat, 0.0) + float(e["amount"])
        
        # Pure native Streamlit dynamic charting layout
        st.bar_chart(category_totals)
    else:
        st.info("Log group expenses to populate spending analysis visual charts.")

with col_right:
    # --- REAL-TIME OPTIMAL SETTLEMENT SCHEDULE ENGINE ---
    st.subheader("📊 Balanced Settlement Resolution")
    current_balances = calculate_balances(expenses_list)
    optimal_transfers = simplify_debts(current_balances)
    
    if optimal_transfers:
        st.info("The application algorithm engine has structured the absolute minimal debt clearing transactions required:")
        for idx, tx in enumerate(optimal_transfers):
            c_box, c_lnk = st.columns([3, 1])
            with c_box:
                st.error(f"🔴 **{tx['from']}** owes **{tx['to']}** → **{curr} {tx['amount']}**")
            with c_lnk:
                upi_url = f"upi://pay?pa={tx['to'].lower()}@upi&pn={tx['to']}&am={tx['amount']}&cu=INR"
                st.markdown(f"[📲 Pay Intent]({upi_url})")
    else:
        st.success("🎉 Group account balances perfectly absolute! No clearing transactions required.")

    st.markdown("---")

    # --- INTERACTIVE ACTIVE HISTORY ARCHIVE REGISTRY ---
    st.subheader("📑 Itemised Transaction History Logs")
    if expenses_list:
        # Loop safe list mapping backwards to show newest items up front
        for original_idx, exp in reversed(list(enumerate(expenses_list))):
            h_col1, h_col2 = st.columns([4, 1])
            with h_col1:
                st.markdown(
                    f"**{exp['description']}** • `{exp.get('category', 'General')}`<br>"
                    f"Paid by **{exp['payer']}**: **{curr} {float(exp['amount']):,.2f}**<br>"
                    f"<small>Shared between: {', '.join(exp['participants'])}</small>", 
                    unsafe_allow_html=True
                )
            with h_col2:
                # Target delete utilizing persistent original index locations
                if st.button("🗑️ Delete", key=f"del_item_{original_idx}"):
                    data["expenses"].pop(original_idx)
                    save_data(data)
                    st.success("Entry pulled from records!")
                    st.rerun()
            st.markdown("<hr style='margin: 0.5em 0; border: 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
    else:
        st.info("No transaction line items currently registered in ledger history log files.")
        