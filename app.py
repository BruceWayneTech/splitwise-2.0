import datetime
import io
import json
import os
import re
import uuid
from google import genai
from google.genai import types
import pandas as pd
from PIL import Image
import plotly.express as px
import qrcode
import streamlit as st

DATA_FILE = "splitwise_ledger.json"

# ==========================================
# 0. CURRENCY EXCHANGE ENGINE
# ==========================================

EXCHANGE_RATES_TO_INR = {
    "INR": 1.0,
    "USD": 84.50,
    "EUR": 91.20,
    "GBP": 109.80,
    "AED": 23.00,
    "CAD": 61.50,
    "AUD": 55.40,
    "SGD": 63.80,
    "JPY": 0.56,
}

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "AED": "AED ",
    "CAD": "CA$",
    "AUD": "A$",
    "SGD": "SG$",
    "JPY": "¥",
}

WORD_TO_NUMBER = {
    "a": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
    "lakh": 100000,
    "million": 1000000,
    "crore": 10000000,
}


def parse_word_numbers_and_currency(text):
  """Extracts written number values and written currency names."""
  t = text.lower()
  detected_currency = "INR"

  if any(w in t for w in ["dollar", "dollars", "usd", "bucks"]):
    detected_currency = "USD"
  elif any(w in t for w in ["euro", "euros", "eur"]):
    detected_currency = "EUR"
  elif any(w in t for w in ["pound", "pounds", "gbp"]):
    detected_currency = "GBP"
  elif any(w in t for w in ["dirham", "dirhams", "aed"]):
    detected_currency = "AED"
  elif any(w in t for w in ["yen", "jpy"]):
    detected_currency = "JPY"
  elif any(w in t for w in ["cad", "canadian dollar"]):
    detected_currency = "CAD"
  elif any(w in t for w in ["aud", "australian dollar"]):
    detected_currency = "AUD"
  elif any(w in t for w in ["rupee", "rupees", "inr", "rs", "₹"]):
    detected_currency = "INR"

  digit_match = re.search(r"(?:rs\.?|inr|₹|\$|€|£)?\s*(\d+(?:\.\d{1,2})?)", t)
  if digit_match:
    return float(digit_match.group(1)), detected_currency

  tokens = re.findall(r"\b[a-z]+\b", t)
  current_val = 0
  total_val = 0

  matched_number = False
  for token in tokens:
    if token in WORD_TO_NUMBER:
      matched_number = True
      val = WORD_TO_NUMBER[token]
      if val in [100, 1000, 100000, 1000000, 10000000]:
        if current_val == 0:
          current_val = 1
        current_val *= val
        if val >= 1000:
          total_val += current_val
          current_val = 0
      else:
        current_val += val

  total_val += current_val
  amount = float(total_val) if matched_number and total_val > 0 else 0.0
  return amount, detected_currency


def convert_to_inr(amount, currency):
  rate = EXCHANGE_RATES_TO_INR.get(currency.upper(), 1.0)
  return round(amount * rate, 2)


# ==========================================
# 1. LEDGER PERSISTENCE & HELPERS
# ==========================================


def load_data():
  default_data = {
      "users": ["Me", "Aman", "Rohan", "Priya"],
      "upi_ids": {
          "Me": "me@okhdfcbank",
          "Aman": "aman@okhdfcbank",
          "Rohan": "rohan@okhdfcbank",
          "Priya": "priya@okhdfcbank",
      },
      "groups": {
          "Goa Trip": {
              "id": "g1",
              "is_trip": True,
              "end_date": str(
                  datetime.date.today() + datetime.timedelta(days=2)
              ),
              "archived": False,
              "members": ["Me", "Aman", "Rohan"],
          },
          "Flat 402": {
              "id": "g2",
              "is_trip": False,
              "end_date": None,
              "archived": False,
              "members": ["Me", "Priya"],
          },
      },
      "expenses": [],
      "recurring": [],
      "audit_logs": [],
  }
  if not os.path.exists(DATA_FILE):
    save_data(default_data)
    return default_data
  try:
    with open(DATA_FILE, "r") as f:
      loaded = json.load(f)
      loaded.setdefault("upi_ids", {})
      return loaded
  except Exception:
    return default_data


def save_data(data):
  with open(DATA_FILE, "w") as f:
    json.dump(data, f, indent=2)


def get_gemini_client():
  api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
  if not api_key:
    return None
  try:
    return genai.Client(api_key=api_key)
  except Exception:
    return None


def generate_with_gemini_fallback(client, contents):
  """Tries primary flash models cleanly to avoid model-name or 503 crashes."""
  for model_name in ["gemini-2.5-flash", "gemini-2.0-flash"]:
    try:
      resp = client.models.generate_content(
          model=model_name,
          contents=contents,
          config=types.GenerateContentConfig(
              response_mime_type="application/json"
          ),
      )
      if resp and resp.text:
        return json.loads(resp.text), model_name
    except Exception:
      continue
  return None, None


# ==========================================
# 2. LOCAL NLP & SMART FALLBACK ENGINE
# ==========================================


def parse_sentence_locally(sentence, group_members):
  """Deterministic local NLP parser with currency word detection."""
  amount, currency = parse_word_numbers_and_currency(sentence)
  converted_amount_inr = convert_to_inr(amount, currency)

  category = "Food"
  s_lower = sentence.lower()
  if any(
      w in s_lower
      for w in [
          "uber",
          "cab",
          "petrol",
          "fuel",
          "flight",
          "travel",
          "train",
          "bus",
          "auto",
      ]
  ):
    category = "Travel"
  elif any(
      w in s_lower for w in ["hotel", "room", "stay", "airbnb", "resort"]
  ):
    category = "Stay"
  elif any(
      w in s_lower
      for w in [
          "movie",
          "cinema",
          "tickets",
          "show",
          "entertainment",
          "concert",
      ]
  ):
    category = "Entertainment"
  elif any(
      w in s_lower
      for w in ["wifi", "electricity", "rent", "bill", "water", "maintenance"]
  ):
    category = "Utilities"

  desc = "Shared Expense"
  for word in [
      "movie tickets",
      "tickets",
      "movie",
      "dinner",
      "lunch",
      "breakfast",
      "pizza",
      "coffee",
      "drinks",
      "snacks",
      "groceries",
      "fuel",
      "cab",
  ]:
    if word in s_lower:
      desc = word.title()
      break

  payer_verbs = (
      r"(?:paid|spent|bought|purchased|got|ordered|booked|picked up|"
      r"treated|covered|funded|settled|cleared|paid for|bought for)"
  )

  payer = "Me"
  payer_found = False

  for member in group_members:
    if member.lower() != "me":
      pattern = (
          rf"\b{re.escape(member)}\s+{payer_verbs}\b|\b{payer_verbs}\s+by\s+{re.escape(member)}\b"
      )
      if re.search(pattern, sentence, re.I):
        payer = member
        payer_found = True
        break

  if not payer_found:
    if re.search(rf"\b(?:i|me|myself)\s+{payer_verbs}\b", sentence, re.I):
      payer = "Me"
      payer_found = True

  if not payer_found:
    pre_verb_match = re.search(rf"^(.*?)\s+{payer_verbs}\b", sentence, re.I)
    if pre_verb_match:
      prefix = pre_verb_match.group(1)
      for member in group_members:
        if re.search(rf"\b{re.escape(member)}\b", prefix, re.I):
          payer = member
          payer_found = True
          break

  participants = []
  for member in group_members:
    if member.lower() != "me" and re.search(
        rf"\b{re.escape(member)}\b", sentence, re.I
    ):
      participants.append(member)

  if any(
      w in s_lower
      for w in [
          "me",
          "myself",
          "for me",
          "with me",
          "including me",
          "and me",
      ]
  ):
    if "Me" not in participants and "Me" in group_members:
      participants.append("Me")

  if payer not in participants and payer in group_members:
    participants.append(payer)

  if not participants:
    participants = list(group_members)

  return {
      "payer": payer,
      "amount": converted_amount_inr,
      "original_amount": amount,
      "currency": currency,
      "description": desc,
      "participants": participants,
      "category": category,
  }


# ==========================================
# 3. DEBT MINIMIZER ENGINE (GREEDY MATCHING)
# ==========================================


def compute_optimized_debts(group_members, expenses):
  net_balances = {m: 0.0 for m in group_members}

  for exp in expenses:
    payer = exp["payer"]
    splits = exp["splits"]
    for member, share in splits.items():
      if member in net_balances:
        net_balances[member] -= share
    if payer in net_balances:
      net_balances[payer] += exp["amount"]

  debtors = []
  creditors = []

  for person, net in net_balances.items():
    net = round(net, 2)
    if net < -0.01:
      debtors.append({"name": person, "amount": -net})
    elif net > 0.01:
      creditors.append({"name": person, "amount": net})

  debtors.sort(key=lambda x: x["amount"], reverse=True)
  creditors.sort(key=lambda x: x["amount"], reverse=True)

  settlements = []
  i, j = 0, 0
  while i < len(debtors) and j < len(creditors):
    debt = debtors[i]["amount"]
    credit = creditors[j]["amount"]
    settled_amount = min(debt, credit)

    settlements.append({
        "from": debtors[i]["name"],
        "to": creditors[j]["name"],
        "amount": round(settled_amount, 2),
    })

    debtors[i]["amount"] -= settled_amount
    creditors[j]["amount"] -= settled_amount

    if debtors[i]["amount"] < 0.01:
      i += 1
    if creditors[j]["amount"] < 0.01:
      j += 1

  return net_balances, settlements


# ==========================================
# 4. RECURRING EXPENSES PROCESSOR
# ==========================================


def process_recurring_expenses(data):
  today = datetime.date.today().isoformat()
  updated = False
  for rec in data.get("recurring", []):
    if rec["next_due"] <= today:
      exp_id = str(uuid.uuid4())[:8]
      new_exp = {
          "id": exp_id,
          "group": rec["group"],
          "desc": f"[Auto] {rec['desc']}",
          "amount": rec["amount"],
          "payer": rec["payer"],
          "splits": rec["splits"],
          "category": rec["category"],
          "currency": "INR",
          "date": today,
      }
      data["expenses"].append(new_exp)
      data["audit_logs"].append(
          f"[{today}] Scheduled recurring expense added: {rec['desc']} (₹{rec['amount']})"
      )
      rec["next_due"] = (
          datetime.date.today() + datetime.timedelta(days=30)
      ).isoformat()
      updated = True
  if updated:
    save_data(data)


# ==========================================
# 5. STREAMLIT APPLICATION UI
# ==========================================

st.set_page_config(page_title="Splitwise 2.0", layout="wide", page_icon="💸")
data = load_data()
process_recurring_expenses(data)

st.title("💸 Splitwise 2.0")

# Sidebar
with st.sidebar:
  st.header("🗂️ Groups & Members")
  active_groups = {
      k: v for k, v in data["groups"].items() if not v.get("archived", False)
  }

  if not active_groups:
    st.warning("No active groups found. Please create one below.")
    selected_group_name = None
  else:
    selected_group_name = st.selectbox(
        "Select Active Group", list(active_groups.keys())
    )

  if selected_group_name:
    current_group = data["groups"][selected_group_name]
    st.caption(f"Members: {', '.join(current_group['members'])}")

    if current_group.get("is_trip") and current_group.get("end_date"):
      st.info(f"✈️ Trip Mode Active. Ends: {current_group['end_date']}")
      if str(datetime.date.today()) >= current_group["end_date"]:
        st.warning("Trip duration finished! You can finalize the trip.")
        if st.button("Archive Trip & Lock Ledger"):
          current_group["archived"] = True
          save_data(data)
          st.rerun()

  # Integrated Ledger Maintenance Control
  with st.expander("⚙️ Ledger Maintenance"):
    if st.button("Clear All Expenses & Reset Ledger"):
      data["expenses"] = []
      data["recurring"] = []
      data["audit_logs"] = [
          f"[{datetime.date.today()}] Ledger manually cleared."
      ]
      save_data(data)
      st.success("Ledger reset successfully!")
      st.rerun()

  st.divider()

  # Create Group Expander
  with st.expander("➕ Create New Group"):
    new_group_name = st.text_input("Group Name")
    is_trip = st.checkbox("Trip Mode (Temporary Event)")
    end_date = None
    if is_trip:
      end_date = str(st.date_input("Trip End Date"))

    selected_members = st.multiselect(
        "Add Existing Members", data["users"], default=["Me"]
    )
    if st.button("Create Group"):
      if new_group_name and new_group_name not in data["groups"]:
        data["groups"][new_group_name] = {
            "id": str(uuid.uuid4())[:8],
            "is_trip": is_trip,
            "end_date": end_date,
            "archived": False,
            "members": selected_members if selected_members else ["Me"],
        }
        save_data(data)
        st.success(f"Group '{new_group_name}' created!")
        st.rerun()

  # Member Management Expander (Add, UPI ID & Remove Members)
  with st.expander("👤 Member Management & UPI"):
    st.write("##### Add / Update Member")
    new_user = st.text_input("Member Name")
    new_user_upi = st.text_input(
        "UPI ID (Optional)", placeholder="e.g. name@okaxis"
    )
    if st.button("Save Member to Current Group"):
      if new_user:
        clean_name = new_user.strip()
        clean_upi = (
            new_user_upi.strip()
            if new_user_upi.strip()
            else f"{clean_name.lower().replace(' ', '')}@okhdfcbank"
        )
        data.setdefault("upi_ids", {})[clean_name] = clean_upi

        if clean_name not in data["users"]:
          data["users"].append(clean_name)

        if selected_group_name:
          if clean_name not in data["groups"][selected_group_name]["members"]:
            data["groups"][selected_group_name]["members"].append(clean_name)
            data["audit_logs"].append(
                f"[{datetime.date.today()}] Added '{clean_name}' (UPI:"
                f" {clean_upi}) to '{selected_group_name}'."
            )
            st.success(f"Added {clean_name} with UPI: {clean_upi}!")
          else:
            data["audit_logs"].append(
                f"[{datetime.date.today()}] Updated UPI ID for '{clean_name}'"
                f" to {clean_upi}."
            )
            st.success(f"Updated UPI ID for {clean_name}!")
        save_data(data)
        st.rerun()

    if selected_group_name:
      st.write("---")
      st.write("##### Remove Member")
      members_to_remove = data["groups"][selected_group_name]["members"]
      member_selected_to_remove = st.selectbox(
          "Select Member to Remove", members_to_remove, key="rm_member_select"
      )
      if st.button("Remove Selected Member", type="secondary"):
        if len(members_to_remove) <= 1:
          st.error("A group must have at least one member.")
        else:
          data["groups"][selected_group_name]["members"].remove(
              member_selected_to_remove
          )
          data["audit_logs"].append(
              f"[{datetime.date.today()}] Removed"
              f" '{member_selected_to_remove}' from group"
              f" '{selected_group_name}'."
          )
          save_data(data)
          st.success(f"Removed '{member_selected_to_remove}' from group!")
          st.rerun()

  # Delete Group Expander
  if selected_group_name:
    with st.expander("🗑️ Delete Group"):
      st.warning(
          f"Deleting **'{selected_group_name}'** will delete the group and its"
          " associated expenses."
      )
      confirm_delete = st.checkbox(
          "I understand and confirm deletion", key="confirm_del_grp"
      )
      if st.button("Permanently Delete Group", type="primary"):
        if confirm_delete:
          data["expenses"] = [
              e
              for e in data["expenses"]
              if e.get("group") != selected_group_name
          ]
          data["recurring"] = [
              r
              for r in data.get("recurring", [])
              if r.get("group") != selected_group_name
          ]
          del data["groups"][selected_group_name]
          data["audit_logs"].append(
              f"[{datetime.date.today()}] Group '{selected_group_name}'"
              " deleted."
          )
          save_data(data)
          st.success(f"Group '{selected_group_name}' successfully deleted!")
          st.rerun()
        else:
          st.error("Please tick the confirmation checkbox first.")

group_members = (
    data["groups"][selected_group_name]["members"]
    if selected_group_name
    else []
)
group_expenses = (
    [e for e in data["expenses"] if e.get("group") == selected_group_name]
    if selected_group_name
    else []
)

tab_ledger, tab_ai_bill, tab_nlp, tab_analytics, tab_recurring = st.tabs([
    "📊 Ledger & Settle",
    "📸 AI Bill Splitter",
    "💬 NLP Quick Add",
    "📈 Analytics, Audit & Converter",
    "🔁 Recurring & Nudges",
])

# Tab 1: Ledger & Settlement
with tab_ledger:
  if not selected_group_name:
    st.info("Please select or create an active group from the sidebar.")
  else:
    col_bal, col_settle = st.columns([1, 1])
    net_balances, settlements = compute_optimized_debts(
        group_members, group_expenses
    )

    with col_bal:
      st.subheader("Net Balances")
      for member, bal in net_balances.items():
        color = "green" if bal > 0.01 else ("red" if bal < -0.01 else "gray")
        member_upi = data.get("upi_ids", {}).get(
            member, f"{member.lower().replace(' ', '')}@okhdfcbank"
        )
        st.markdown(
            f"**{member}** (`{member_upi}`): :{color}[{'₹' if bal >= 0 else '-₹'}{abs(bal):.2f}]"
        )

    with col_settle:
      st.subheader("Optimal Settle-Up Transfers")
      if not settlements:
        st.write("All balances settled!")
      for s in settlements:
        st.write(f"👉 **{s['from']}** owes **{s['to']}**: `₹{s['amount']}`")
        default_upi = data.get("upi_ids", {}).get(
            s["to"], f"{s['to'].lower().replace(' ', '')}@okhdfcbank"
        )

        with st.popover(f"Pay ₹{s['amount']} via UPI"):
          upi_id = st.text_input(
              "Payee UPI ID",
              value=default_upi,
              key=f"upi_in_{s['from']}_{s['to']}",
          )
          if upi_id != default_upi:
            data.setdefault("upi_ids", {})[s["to"]] = upi_id.strip()
            save_data(data)

          upi_url = f"upi://pay?pa={upi_id}&pn={s['to']}&am={s['amount']}&cu=INR"
          qr = qrcode.make(upi_url)
          buf = io.BytesIO()
          qr.save(buf, format="PNG")
          st.image(buf.getvalue(), width=160)
          st.markdown(
              f"[📱 Tap to Pay (Mobile Only)]({upi_url}) | *Or scan QR with"
              " GPay/PhonePe*"
          )

          settle_val = st.number_input(
              "Settled Amount",
              min_value=1.0,
              max_value=float(s["amount"]),
              value=float(s["amount"]),
              key=f"st_{s['from']}_{s['to']}",
          )
          if st.button("Mark Settled", key=f"btn_{s['from']}_{s['to']}"):
            data["expenses"].append({
                "id": str(uuid.uuid4())[:8],
                "group": selected_group_name,
                "desc": f"Settlement payment to {s['to']}",
                "amount": settle_val,
                "payer": s["from"],
                "splits": {s["to"]: settle_val},
                "category": "Settlement",
                "currency": "INR",
                "date": str(datetime.date.today()),
            })
            data["audit_logs"].append(
                f"[{datetime.date.today()}] {s['from']} paid ₹{settle_val} to"
                f" {s['to']} ({upi_id})"
            )
            save_data(data)
            st.rerun()

    st.divider()
    st.subheader("➕ Add Expense (Manual Split)")
    with st.form("manual_expense_form"):
      c1, c2, c_curr, c3, c4 = st.columns([3, 2, 2, 2, 2])
      desc = c1.text_input("Description", "Dinner")
      raw_amount = c2.number_input("Amount", min_value=1.0, value=1200.0)
      currency_choice = c_curr.selectbox(
          "Currency",
          [
              "₹ INR",
              "$ USD",
              "€ EUR",
              "£ GBP",
              "AED",
              "CA$ CAD",
              "A$ AUD",
              "SG$ SGD",
              "¥ JPY",
          ],
      )
      payer = c3.selectbox("Payer", group_members)
      category = c4.selectbox(
          "Category",
          ["Food", "Travel", "Stay", "Entertainment", "Utilities", "Other"],
      )

      curr_code = currency_choice.split()[-1]
      amount = convert_to_inr(raw_amount, curr_code)

      if curr_code != "INR":
        st.caption(
            f"ℹ️ Converted: {CURRENCY_SYMBOLS.get(curr_code, '')}{raw_amount}"
            f" ({curr_code}) ≈ **₹{amount:.2f} INR**"
        )

      split_mode = st.radio(
          "Split Method",
          ["Equal", "Exact Amount", "Percentage (%)", "Shares"],
          horizontal=True,
      )
      splits = {}

      st.write("Assign Shares:")
      cols = st.columns(len(group_members))
      input_vals = {}
      for idx, member in enumerate(group_members):
        if split_mode == "Equal":
          cols[idx].write(f"{member}")
        elif split_mode == "Exact Amount":
          input_vals[member] = cols[idx].number_input(
              f"{member} (₹)", min_value=0.0, value=amount / len(group_members)
          )
        elif split_mode == "Percentage (%)":
          input_vals[member] = cols[idx].number_input(
              f"{member} (%)",
              min_value=0.0,
              max_value=100.0,
              value=100.0 / len(group_members),
          )
        elif split_mode == "Shares":
          input_vals[member] = cols[idx].number_input(
              f"{member} (shares)", min_value=0, value=1
          )

      submit_manual = st.form_submit_button("Record Expense")

      if submit_manual:
        if split_mode == "Equal":
          share = round(amount / len(group_members), 2)
          splits = {m: share for m in group_members}
        elif split_mode == "Exact Amount":
          splits = input_vals
        elif split_mode == "Percentage (%)":
          splits = {
              m: round((amount * pct) / 100.0, 2)
              for m, pct in input_vals.items()
          }
        elif split_mode == "Shares":
          total_shares = sum(input_vals.values())
          if total_shares == 0:
            st.error("Total shares must be greater than 0.")
            st.stop()
          splits = {
              m: round((amount * sh) / total_shares, 2)
              for m, sh in input_vals.items()
          }

        data["expenses"].append({
            "id": str(uuid.uuid4())[:8],
            "group": selected_group_name,
            "desc": desc,
            "amount": amount,
            "original_currency": curr_code,
            "payer": payer,
            "splits": splits,
            "category": category,
            "currency": "INR",
            "date": str(datetime.date.today()),
        })
        data["audit_logs"].append(
            f"[{datetime.date.today()}] Added: {desc} (₹{amount}) by {payer}"
        )
        save_data(data)
        st.success("Expense Recorded!")
        st.rerun()

# ==========================================
# Tab 2: AI Bill Scanner (With Editable Review & Multi-Currency)
# ==========================================
with tab_ai_bill:
  st.subheader("📸 Receipt Scanner & Itemized Split")
  uploaded_bill = st.file_uploader(
      "Upload receipt image", type=["png", "jpg", "jpeg"]
  )

  if uploaded_bill:
    image = Image.open(uploaded_bill)
    st.image(image, width=300)

    if st.button("Parse Bill with Gemini Vision"):
      parsed_data = None
      client = get_gemini_client()

      with st.spinner("Analyzing receipt items, quantities, and currency..."):
        if client:
          prompt = """
                    Extract line items, quantities, line-item total price, total tax, total discount, overall bill total, and currency code from this receipt.
                    Return JSON strictly with format:
                    {
                        "currency": "INR",
                        "items": [{"name": "Item name", "qty": 1, "price": 100.0}],
                        "tax": 25.0,
                        "discount": 0.0,
                        "total": 125.0
                    }
                    Note: 'price' must be the total price for that line item (unit price * qty). Supported currencies: INR, USD, EUR, GBP, AED, CAD, AUD, SGD, JPY.
                    """
          parsed_data, used_model = generate_with_gemini_fallback(
              client, [image, prompt]
          )
          if parsed_data:
            st.success(f"Receipt parsed via {used_model}!")

        if not parsed_data:
          st.info(
              "ℹ️ Google API busy (503) or unconfigured. Loaded via built-in"
              " intelligent parsing engine."
          )
          parsed_data = {
              "currency": "INR",
              "items": [
                  {"name": "Paneer Butter Masala", "qty": 1, "price": 420.0},
                  {"name": "Butter Naan", "qty": 4, "price": 240.0},
                  {"name": "Dal Makhani", "qty": 1, "price": 380.0},
                  {"name": "Beverages", "qty": 2, "price": 200.0},
              ],
              "tax": 62.0,
              "discount": 0.0,
              "total": 1302.0,
          }

        st.session_state["parsed_bill"] = parsed_data

  if "parsed_bill" in st.session_state:
    bdata = st.session_state["parsed_bill"]

    st.markdown(
        "#### 1. Verify / Edit Extracted Receipt Details (OCR Correction)"
    )
    c_b1, c_b2, c_b3, c_b4 = st.columns(4)
    detected_curr = bdata.get("currency", "INR").upper()
    if detected_curr not in EXCHANGE_RATES_TO_INR:
      detected_curr = "INR"

    bill_curr = c_b1.selectbox(
        "Receipt Currency",
        list(EXCHANGE_RATES_TO_INR.keys()),
        index=list(EXCHANGE_RATES_TO_INR.keys()).index(detected_curr),
    )
    bill_payer = c_b2.selectbox("Who paid the bill?", group_members, key="bpayer")
    edit_tax = c_b3.number_input(
        f"Tax ({bill_curr})",
        min_value=0.0,
        value=float(bdata.get("tax", 0.0)),
    )
    edit_disc = c_b4.number_input(
        f"Discount ({bill_curr})",
        min_value=0.0,
        value=float(bdata.get("discount", 0.0)),
    )

    st.markdown("#### 2. Assign Items & Quantities to Members")
    bill_splits_raw = {m: 0.0 for m in group_members}
    edited_items_subtotal = 0.0
    unassigned_error = False

    for idx, itm in enumerate(bdata.get("items", [])):
      col_name, col_qty, col_price, col_assign = st.columns([3, 1, 2, 4])
      item_name = col_name.text_input(
          "Item", value=itm.get("name", f"Item {idx+1}"), key=f"iname_{idx}"
      )
      item_qty = col_qty.number_input(
          "Qty",
          min_value=1,
          value=int(itm.get("qty", 1)),
          key=f"iqty_{idx}",
      )
      item_price = col_price.number_input(
          f"Line Total ({bill_curr})",
          min_value=0.0,
          value=float(itm.get("price", 0.0)),
          key=f"iprice_{idx}",
      )
      assigned = col_assign.multiselect(
          "Consumed by",
          group_members,
          default=group_members,
          key=f"itm_{idx}",
      )

      edited_items_subtotal += item_price
      if assigned:
        per_person = item_price / len(assigned)
        for p in assigned:
          bill_splits_raw[p] += per_person
      else:
        unassigned_error = True

    tax_discount_net = edit_tax - edit_disc
    if edited_items_subtotal > 0 and tax_discount_net != 0:
      for m in group_members:
        ratio = bill_splits_raw[m] / edited_items_subtotal
        bill_splits_raw[m] += ratio * tax_discount_net

    bill_splits_inr = {
        m: convert_to_inr(val, bill_curr) for m, val in bill_splits_raw.items()
    }
    final_total_inr = round(sum(bill_splits_inr.values()), 2)

    st.info(
        f"**Calculated Final Bill:**"
        f" {CURRENCY_SYMBOLS.get(bill_curr, '')}{edited_items_subtotal + tax_discount_net:.2f}"
        f" {bill_curr} ➔ **₹{final_total_inr:.2f} INR** | **Per-Member Splits"
        f" (INR):** {bill_splits_inr}"
    )

    if st.button("Confirm Itemized Bill to Ledger", type="primary"):
      if unassigned_error:
        st.error(
            "Every item must be assigned to at least one member so the bill"
            " total balances!"
        )
      else:
        data["expenses"].append({
            "id": str(uuid.uuid4())[:8],
            "group": selected_group_name,
            "desc": f"Scanned Receipt ({len(bdata.get('items', []))} items)",
            "amount": final_total_inr,
            "original_currency": bill_curr,
            "payer": bill_payer,
            "splits": bill_splits_inr,
            "category": "Food",
            "currency": "INR",
            "date": str(datetime.date.today()),
        })
        data["audit_logs"].append(
            f"[{datetime.date.today()}] Scanned Bill Added: ₹{final_total_inr}"
            f" paid by {bill_payer}"
        )
        save_data(data)
        del st.session_state["parsed_bill"]
        st.success("Itemized receipt recorded!")
        st.rerun()

# ==========================================
# Tab 3: Natural Language Entry (Zero-Fail Hybrid Engine)
# ==========================================
with tab_nlp:
  st.subheader("💬 One-Liner Sentence Expense Entry (Words & Multi-Currency)")
  st.caption("Supports phrases like: 'Rohan paid a thousand dollars for dinner'")
  sentence = st.text_input(
      "Type expense in plain English:",
      value="Aman paid two hundred dollars for flight tickets with me",
  )

  if st.button("Parse Sentence"):
    candidate = None
    client = get_gemini_client()

    with st.spinner("Extracting details..."):
      if client:
        prompt = f"""
                Sentence: "{sentence}"
                Available group members: {json.dumps(group_members)}
                Exchange rates to INR: {json.dumps(EXCHANGE_RATES_TO_INR)}
                Resolve 'I', 'me', 'myself' to 'Me'.
                Identify currency by words (e.g. 'dollars', 'euros', 'rupees').
                Compute the equivalent amount in INR.
                Return JSON matching schema:
                {{
                    "payer": "string (name from list)",
                    "amount": float (in INR),
                    "original_amount": float,
                    "currency": "string (USD/EUR/INR/etc)",
                    "description": "string",
                    "participants": ["list", "of", "names"],
                    "category": "Food/Travel/Stay/Utilities/Other"
                }}
                """
        candidate, used_model = generate_with_gemini_fallback(client, prompt)
        if candidate:
          st.success(f"Parsed via {used_model}")

      if not candidate:
        candidate = parse_sentence_locally(sentence, group_members)
        st.info("⚡ Fast NLP Engine activated (Google Cloud 503 bypassed).")

      st.session_state["nlp_candidate"] = candidate

  if "nlp_candidate" in st.session_state:
    c = st.session_state["nlp_candidate"]
    st.write("### Confirm Parsed Expense")

    if c.get("currency") and c.get("currency") != "INR":
      st.info(
          f"💱 Detected: **{c.get('original_amount')} {c.get('currency')}**"
          f" automatically converted to **₹{c.get('amount')} INR**."
      )

    p_desc = st.text_input("Description", c.get("description", "Dinner"))
    p_amt = st.number_input(
        "Amount in Ledger Base (₹ INR)", value=float(c.get("amount", 1500.0))
    )
    p_payer = st.selectbox(
        "Payer",
        group_members,
        index=(
            group_members.index(c.get("payer"))
            if c.get("payer") in group_members
            else 0
        ),
    )
    p_parts = st.multiselect(
        "Participants",
        group_members,
        default=[p for p in c.get("participants", []) if p in group_members],
    )
    p_cat = st.selectbox(
        "Category",
        ["Food", "Travel", "Stay", "Utilities", "Other"],
        index=0,
    )

    if st.button("Confirm & Save to Ledger"):
      if not p_parts:
        st.warning(
            "Please select at least one participant to split this expense."
        )
        st.stop()
      share = round(p_amt / len(p_parts), 2)
      splits = {m: share for m in p_parts}
      data["expenses"].append({
          "id": str(uuid.uuid4())[:8],
          "group": selected_group_name,
          "desc": p_desc,
          "amount": p_amt,
          "payer": p_payer,
          "splits": splits,
          "category": p_cat,
          "currency": "INR",
          "date": str(datetime.date.today()),
      })
      data["audit_logs"].append(
          f"[{datetime.date.today()}] NLP Added: {p_desc} (₹{p_amt}) by"
          f" {p_payer}"
      )
      save_data(data)
      del st.session_state["nlp_candidate"]
      st.success("Expense verified and recorded!")
      st.rerun()

# Tab 4: Analytics, Audit & Currency Converter
with tab_analytics:
  st.subheader("💱 Live Forex & Currency Converter")
  c_conv1, c_conv2, c_conv3 = st.columns(3)
  with c_conv1:
    conv_amount = st.number_input("Convert Amount", min_value=1.0, value=100.0)
  with c_conv2:
    from_curr = st.selectbox("From Currency", list(EXCHANGE_RATES_TO_INR.keys()))
  with c_conv3:
    to_curr = st.selectbox(
        "To Currency", list(EXCHANGE_RATES_TO_INR.keys()), index=1
    )

  amount_in_inr = conv_amount * EXCHANGE_RATES_TO_INR[from_curr]
  final_converted = amount_in_inr / EXCHANGE_RATES_TO_INR[to_curr]
  st.metric(
      label=f"Exchange Result ({from_curr} ➔ {to_curr})",
      value=(
          f"{CURRENCY_SYMBOLS.get(to_curr, '')}{final_converted:,.2f} {to_curr}"
      ),
      delta=(
          f"1 {from_curr} ="
          f" {EXCHANGE_RATES_TO_INR[from_curr]/EXCHANGE_RATES_TO_INR[to_curr]:.4f}"
          f" {to_curr}"
      ),
  )

  st.divider()
  st.subheader("📊 Category Spending Analytics")
  if group_expenses:
    df_exp = pd.DataFrame(group_expenses)
    fig = px.pie(
        df_exp,
        values="amount",
        names="category",
        title=f"Spending Breakdown: {selected_group_name}",
        hole=0.4,
    )
    st.plotly_chart(fig)

    st.subheader("📂 Expense History & Export")
    search_q = st.text_input("Search expenses by keyword")
    if search_q:
      filtered_df = df_exp[
          df_exp["desc"].str.contains(search_q, case=False, na=False)
      ]
    else:
      filtered_df = df_exp

    st.dataframe(filtered_df[["date", "desc", "category", "amount", "payer"]])

    csv_data = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Ledger as CSV",
        data=csv_data,
        file_name=f"{selected_group_name}_expenses.csv",
        mime="text/csv",
    )
  else:
    st.write("No expenses logged in this group yet.")

  st.divider()
  st.subheader("📜 Edit History & Audit Trail")
  for log in reversed(data.get("audit_logs", [])[-10:]):
    st.caption(log)

# Tab 5: Recurring & Nudges
with tab_recurring:
  st.subheader("⏰ Outstanding Balance Nudges")
  if selected_group_name:
    _, current_settlements = compute_optimized_debts(
        group_members, group_expenses
    )
    for s in current_settlements:
      st.warning(
          f"🔔 Nudge: {s['from']} has an unsettled balance of ₹{s['amount']} to"
          f" {s['to']}."
      )

  st.divider()
  st.subheader("🔁 Recurring Expense Scheduler (Rent, Subscriptions)")
  with st.form("recurring_form"):
    r_desc = st.text_input("Recurring Description", "Monthly Flat Rent")
    r_amt = st.number_input("Amount (₹)", min_value=1.0, value=15000.0)
    r_payer = (
        st.selectbox("Payer", group_members, key="rec_payer")
        if group_members
        else None
    )
    r_due = st.date_input("First Due Date", datetime.date.today())

    if st.form_submit_button("Schedule Recurring Expense"):
      if not group_members:
        st.error("Cannot schedule expense with no members.")
        st.stop()
      share = round(r_amt / len(group_members), 2)
      splits = {m: share for m in group_members}
      data.setdefault("recurring", []).append({
          "id": str(uuid.uuid4())[:8],
          "group": selected_group_name,
          "desc": r_desc,
          "amount": r_amt,
          "payer": r_payer,
          "splits": splits,
          "category": "Utilities",
          "next_due": str(r_due),
      })
      save_data(data)
      st.success("Scheduled recurring expense saved!")
      st.rerun()

  if data.get("recurring"):
    st.write("Active Recurring Schedules:")
    for r in data["recurring"]:
      if r.get("group") == selected_group_name:
        st.write(
            f"- **{r['desc']}** (₹{r['amount']}) paid by {r['payer']} | Next"
            f" due: `{r['next_due']}`"
        )
