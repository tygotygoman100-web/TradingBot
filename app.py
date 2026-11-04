import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import json
import os
from concurrent.futures import ThreadPoolExecutor

# --- PAGINA INSTELLINGEN ---
st.set_page_config(
    page_title="Terminal Pro | AI Trading Hub",
    page_icon="⚡",
    layout="wide"
)

# --- TERMINAL PRO DESIGN & STYLING ---
st.markdown("""
    <style>
    .stApp {
        background-color: #090d16;
        color: #e5e7eb;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    [data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #1e293b;
        padding-top: 10px;
    }
    .stButton > button {
        width: 100%;
        background-color: #1e293b;
        color: #94a3b8;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 10px 16px;
        font-weight: 600;
        text-align: left;
        transition: all 0.2s ease;
        margin-bottom: 4px;
    }
    .stButton > button:hover {
        background-color: #334155;
        color: #ffffff;
        border-color: #3b82f6;
    }
    .hub-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
        position: relative;
        overflow: hidden;
        margin-bottom: 15px;
    }
    .hub-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, #3b82f6, #6366f1);
    }
    .hub-card-title {
        font-size: 12px;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 8px;
    }
    .hub-card-value {
        font-size: 24px;
        font-weight: 800;
        color: #f8fafc;
    }
    .market-box {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        margin-bottom: 12px;
        position: relative;
    }
    .market-box::before {
        content: '';
        position: absolute;
        top: 0; left: 0; bottom: 0;
        width: 4px;
        background: #3b82f6;
        border-top-left-radius: 12px;
        border-bottom-left-radius: 12px;
    }
    .status-badge-open {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid #10b981;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
    }
    .status-badge-idle {
        background-color: rgba(100, 116, 139, 0.15);
        color: #94a3b8;
        border: 1px solid #475569;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
    }
    .status-badge-alert {
        background-color: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid #ef4444;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
    }
    h1, h2, h3 { color: #f8fafc !important; font-weight: 700; }
    hr { border-color: #1e293b; }
    </style>
""", unsafe_allow_html=True)

# --- CONFIG & STATE ---
VAST_KAPITAAL_PER_MARKT = 1000.0
STATE_FILE = "trading_bot_data_terminal_pro.json"
beschikbare_tickers = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD"]

def load_all_states():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_all_states(states):
    with open(STATE_FILE, "w") as f:
        json.dump(states, f, indent=4)

all_states = load_all_states()
for t_sym in beschikbare_tickers:
    if t_sym not in all_states:
        all_states[t_sym] = {
            "kasgeld": VAST_KAPITAAL_PER_MARKT,
            "aantal_aandelen": 0.0,
            "gekocht_voor": 0.0,
            "instap_prijs": 0.0,
            "hoogste_prijs": 0.0,
            "noodstop_actief": False,
            "trades": []
        }
save_all_states(all_states)

# Session state defaults
if "actieve_pagina" not in st.session_state:
    st.session_state.actieve_pagina = "dashboard"
if "fast_window" not in st.session_state:
    st.session_state.fast_window = 3
if "slow_window" not in st.session_state:
    st.session_state.slow_window = 10
if "stop_loss_pct" not in st.session_state:
    st.session_state.stop_loss_pct = 2.5
if "take_profit_pct" not in st.session_state:
    st.session_state.take_profit_pct = 8.0
if "gebruik_partial_tp" not in st.session_state:
    st.session_state.gebruik_partial_tp = True
if "gebruik_atr" not in st.session_state:
    st.session_state.gebruik_atr = True
if "circuit_breaker_pct" not in st.session_state:
    st.session_state.circuit_breaker_pct = 5.0

# --- SLIMME & SNELLE DATA FUNCTIE (GECACHE) ---
@st.cache_data(ttl=20)
def get_market_data(symbol):
    try:
        df = yf.download(symbol, period="1d", interval="1m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df_daily = yf.download(symbol, period="5d", interval="1d", progress=False)
        if isinstance(df_daily.columns, pd.MultiIndex):
            df_daily.columns = df_daily.columns.get_level_values(0)
            
        dag_trend_groen = True
        if not df_daily.empty and len(df_daily) >= 2:
            dag_trend_groen = float(df_daily['Close'].iloc[-1]) > float(df_daily['Close'].iloc[-2])
            
        return df, dag_trend_groen
    except:
        return pd.DataFrame(), True

def get_all_markets_parallel(tickers):
    with ThreadPoolExecutor(max_workers=len(tickers)) as executor:
        futures = {t: executor.submit(get_market_data, t) for t in tickers}
        return {t: future.result() for t, future in futures.items()}

all_market_data = get_all_markets_parallel(beschikbare_tickers)


# ==========================================
# BOT MOTOR (LOGICA MET PRO UPGRADES)
# ==========================================
def run_bot_cycle():
    for t_sym in beschikbare_tickers:
        t_state = all_states[t_sym]
        if t_state.get("noodstop_actief", False):
            continue
            
        df_t, dag_trend_groen = all_market_data.get(t_sym, (pd.DataFrame(), True))
        
        if not df_t.empty and len(df_t) >= st.session_state.slow_window:
            df_t['Fast_MA'] = df_t['Close'].rolling(window=st.session_state.fast_window).mean()
            df_t['Slow_MA'] = df_t['Close'].rolling(window=st.session_state.slow_window).mean()
            
            delta = df_t['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df_t['RSI'] = 100 - (100 / (1 + rs))
            
            high_low = df_t['High'] - df_t['Low']
            high_close = (df_t['High'] - df_t['Close'].shift()).abs()
            low_close = (df_t['Low'] - df_t['Close'].shift()).abs()
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df_t['ATR'] = true_range.rolling(window=14).mean()
            
            huidige_prijs = float(df_t['Close'].iloc[-1])
            huidige_fast = float(df_t['Fast_MA'].iloc[-1])
            huidige_slow = float(df_t['Slow_MA'].iloc[-1])
            huidige_rsi = float(df_t['RSI'].iloc[-1]) if not pd.isna(df_t['RSI'].iloc[-1]) else 50.0
            huidige_atr = float(df_t['ATR'].iloc[-1]) if ('ATR' in df_t.columns and not pd.isna(df_t['ATR'].iloc[-1])) else (huidige_prijs * 0.01)
            nu_tijd = datetime.now().strftime('%H:%M:%S')

            MA_koop_signaal = (huidige_fast > (huidige_slow * 1.0005)) and (huidige_rsi < 72) and dag_trend_groen
            
            # Circuit breaker
            if t_state["instap_prijs"] > 0:
                dag_verlies_pct = ((huidige_prijs - t_state["instap_prijs"]) / t_state["instap_prijs"]) * 100
                if dag_verlies_pct <= -st.session_state.circuit_breaker_pct:
                    opbrengst = t_state["aantal_aandelen"] * huidige_prijs
                    t_state["kasgeld"] = opbrengst
                    t_state["aantal_aandelen"] = 0.0
                    t_state["noodstop_actief"] = True
                    t_state["trades"].insert(0, {"Ticker": t_sym, "Tijdstip": nu_tijd, "Actie": "🚨 CIRCUIT BREAKER", "Prijs": f"${huidige_prijs:.2f}", "Inleg": f"${opbrengst:,.2f}", "Resultaat": "VEILIG"})
                    save_all_states(all_states)
                    continue

            trigger_verkoop = False
            reden = ""
            trigger_partial = False
            
            if t_state["aantal_aandelen"] > 0 and t_state["instap_prijs"] > 0:
                if huidige_prijs > t_state.get("hoogste_prijs", huidige_prijs):
                    t_state["hoogste_prijs"] = huidige_prijs
                
                hoogste_punt = t_state["hoogste_prijs"]
                trailing_stop = hoogste_punt - (huidige_atr * 1.5) if st.session_state.gebruik_atr else hoogste_punt * (1 - (st.session_state.stop_loss_pct / 100))
                rend_pct = ((huidige_prijs - t_state["instap_prijs"]) / t_state["instap_prijs"]) * 100
                
                if huidige_prijs <= trailing_stop:
                    trigger_verkoop = True
                    reden = "🛑 Trailing Stop"
                elif rend_pct >= st.session_state.take_profit_pct:
                    if st.session_state.gebruik_partial_tp and not t_state.get("al_gedeeltelijk", False):
                        trigger_partial = True
                    else:
                        trigger_verkoop = True
                        reden = f"🎯 TP (+{rend_pct:.1f}%)"

            # Partial TP uitvoering
            if trigger_partial and t_state["aantal_aandelen"] > 0:
                helft = t_state["aantal_aandelen"] / 2.0
                opb_helft = helft * huidige_prijs
                winst_helft = opb_helft - (t_state["gekocht_voor"] / 2.0)
                t_state["kasgeld"] += opb_helft
                t_state["aantal_aandelen"] -= helft
                t_state["gekocht_voor"] /= 2.0
                t_state["al_gedeeltelijk"] = True
                t_state["trades"].insert(0, {"Ticker": t_sym, "Tijdstip": nu_tijd, "Actie": "🎯 GEDEELTELIJKE TP (50%)", "Prijs": f"${huidige_prijs:.2f}", "Inleg": f"${opb_helft:,.2f}", "Resultaat": f"${winst_helft:+,.2f}"})
                save_all_states(all_states)

            # Koop / Verkoop uitvoering
            if MA_koop_signaal and t_state["aantal_aandelen"] == 0 and t_state["kasgeld"] > 0:
                inleg = t_state["kasgeld"]
                t_state["aantal_aandelen"] = inleg / huidige_prijs
                t_state["gekocht_voor"] = inleg
                t_state["instap_prijs"] = huidige_prijs
                t_state["hoogste_prijs"] = huidige_prijs
                t_state["al_gedeeltelijk"] = False
                t_state["kasgeld"] = 0.0
                t_state["trades"].insert(0, {"Ticker": t_sym, "Tijdstip": nu_tijd, "Actie": "🟢 KOOP (Momentum)", "Prijs": f"${huidige_prijs:.2f}", "Inleg": f"${inleg:,.2f}", "Resultaat": "-"})
                save_all_states(all_states)

            elif (huidige_fast < huidige_slow or trigger_verkoop) and t_state["aantal_aandelen"] > 0:
                opbrengst = t_state["aantal_aandelen"] * huidige_prijs
                winst = opbrengst - t_state["gekocht_voor"]
                t_state["kasgeld"] += opbrengst
                t_state["aantal_aandelen"] = 0.0
                t_state["instap_prijs"] = 0.0
                t_state["hoogste_prijs"] = 0.0
                t_state["al_gedeeltelijk"] = False
                t_state["trades"].insert(0, {"Ticker": t_sym, "Tijdstip": nu_tijd, "Actie": f"🔴 VERKOOP ({reden})", "Prijs": f"${huidige_prijs:.2f}", "Inleg": f"${opbrengst:,.2f}", "Resultaat": f"${winst:+,.2f}"})
                save_all_states(all_states)

run_bot_cycle()

# --- BEREKEN TOTAAL WAARDE ---
totaal_start = len(beschikbare_tickers) * VAST_KAPITAAL_PER_MARKT
totaal_waarde = 0.0
for t_sym in beschikbare_tickers:
    st_item = all_states[t_sym]
    if st_item["aantal_aandelen"] > 0:
        df_i, _ = all_market_data.get(t_sym, (pd.DataFrame(), True))
        p = float(df_i['Close'].iloc[-1]) if not df_i.empty else st_item["gekocht_voor"]
        totaal_waarde += st_item["aantal_aandelen"] * p
    else:
        totaal_waarde += st_item["kasgeld"]
totaal_winst = totaal_waarde - totaal_start
totaal_rendement = (totaal_winst / totaal_start) * 100


# ==========================================
# STIJLVOLLE ZIJKANT MENU
# ==========================================
st.sidebar.markdown("<h2 style='text-align: center; color: #3b82f6 !important;'>⚡ TERMINAL PRO</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; color: #64748b; font-size: 11px;'>AI MULTI-MARKET HUB</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.markdown("<p style='color: #475569; font-size: 11px; font-weight: 700;'>NAVIGATIE</p>", unsafe_allow_html=True)

if st.sidebar.button("📊 Live Dashboard"):
    st.session_state.actieve_pagina = "dashboard"
if st.sidebar.button("📋 Transactie Logboek"):
    st.session_state.actieve_pagina = "logboek"
if st.sidebar.button("🔬 Vaste Backtest"):
    st.session_state.actieve_pagina = "backtest"
if st.sidebar.button("⚙️ Bot Instellingen"):
    st.session_state.actieve_pagina = "settings"

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Handmatig Vernieuwen"):
    st.rerun()


# ==========================================
# PAGINA 1: LIVE DASHBOARD (TERMINAL STIJL)
# ==========================================
if st.session_state.actieve_pagina == "dashboard":
    st.markdown("<h1>📊 Live Portefeuille Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("Professioneel overzicht van je actieve crypto-momentum bot met Pro Upgrades.", unsafe_allow_html=True)
    st.markdown("---")
    
    # 4 Hoofd Hub-Kaarten bovenin
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
            <div class="hub-card">
                <div class="hub-card-title">Startkapitaal</div>
                <div class="hub-card-value">${totaal_start:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
            <div class="hub-card">
                <div class="hub-card-title">Portefeuille Waarde</div>
                <div class="hub-card-value">${totaal_waarde:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with c3:
        w_kleur = "#10b981" if totaal_winst >= 0 else "#ef4444"
        st.markdown(f"""
            <div class="hub-card">
                <div class="hub-card-title">Totaal Winst / Verlies</div>
                <div class="hub-card-value" style="color: {w_kleur};">${totaal_winst:+,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    with c4:
        heeft_nood = any(s.get("noodstop_actief", False) for s in all_states.values())
        b_html = '<span class="status-badge-alert">🚨 NOODSTOP</span>' if heeft_nood else '<span class="status-badge-open">🟢 PRO ULTRA</span>'
        st.markdown(f"""
            <div class="hub-card">
                <div class="hub-card-title">Systeem Status</div>
                <div style="margin-top: 8px;">{b_html}</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><h3>🪙 Alle 5 Markten in Realtime</h3>", unsafe_allow_html=True)
    
    # 5 Stijlvolle Market Boxes naast elkaar
    grid_cols = st.columns(5)
    for idx, t_sym in enumerate(beschikbare_tickers):
        t_st = all_states[t_sym]
        df_m, _ = all_market_data.get(t_sym, (pd.DataFrame(), True))
        huidige_p = float(df_m['Close'].iloc[-1]) if not df_m.empty else 0.0
        
        is_in_trade = t_st["aantal_aandelen"] > 0
        status_badge = '<span class="status-badge-open">IN TRADE</span>' if is_in_trade else '<span class="status-badge-idle">IN KAS</span>'
        huidige_waarde_munt = t_st['kasgeld'] if not is_in_trade else (t_st['aantal_aandelen'] * huidige_p)
        
        with grid_cols[idx]:
            st.markdown(f"""
                <div class="market-box">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-weight: 700; color: #f8fafc; font-size: 15px;">{t_sym}</span>
                        {status_badge}
                    </div>
                    <div style="font-size: 20px; font-weight: 800; color: #38bdf8; margin-bottom: 8px;">${huidige_p:,.2f}</div>
                    <div style="font-size: 12px; color: #94a3b8;">
                        Waarde: <b style="color: #f8fafc;">${huidige_waarde_munt:,.0f}</b>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📈 Gedetailleerde Grafiek Focus")
    kies_focus = st.selectbox("Kies markt voor grafiekweergave", beschikbare_tickers)
    df_f, _ = all_market_data.get(kies_focus, (pd.DataFrame(), True))
    if not df_f.empty and len(df_f) >= st.session_state.slow_window:
        df_f['Fast'] = df_f['Close'].rolling(window=st.session_state.fast_window).mean()
        df_f['Slow'] = df_f['Close'].rolling(window=st.session_state.slow_window).mean()
        st.line_chart(df_f[['Close', 'Fast', 'Slow']])


# ==========================================
# PAGINA 2: TRANSACTIE LOGBOEK
# ==========================================
elif st.session_state.actieve_pagina == "logboek":
    st.markdown("<h1>📋 Transactie Logboek</h1>", unsafe_allow_html=True)
    st.markdown("Overzicht van alle uitgevoerde trades, gedeeltelijke winsten en noodstops.")
    st.markdown("---")
    
    alle_trades = []
    for t_sym, data in all_states.items():
        for tr in data.get("trades", []):
            item = tr.copy()
            item["Ticker"] = t_sym
            alle_trades.append(item)
            
    if alle_trades:
        df_trades = pd.DataFrame(alle_trades)
        filter_m = st.selectbox("🔍 Filter op markt:", ["Alle markten"] + beschikbare_tickers)
        if filter_m != "Alle markten":
            df_trades = df_trades[df_trades["Ticker"] == filter_m]
        st.dataframe(df_trades, use_container_width=True, height=500)
    else:
        st.info("Nog geen transacties geregistreerd.")


# ==========================================
# PAGINA 3: VASTE BACKTEST
# ==========================================
elif st.session_state.actieve_pagina == "backtest":
    st.markdown("<h1>🔬 Vaste Historische Backtest (1 Aug - 1 Nov)</h1>", unsafe_allow_html=True)
    st.markdown("Test strategieën over een vaste periode van 3 maanden.")
    st.markdown("---")
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        test_ticker = st.selectbox("Kies markt", beschikbare_tickers)
    with b_col2:
        st.info("📌 Vaste periode: 2026-08-01 tot 2026-11-01")
        
    if st.button("🚀 Start Vaste Backtest"):
        with st.spinner("Bezig met simuleren..."):
            df_h = yf.download(test_ticker, start="2026-08-01", end="2026-11-01", interval="1h", progress=False)
            if isinstance(df_h.columns, pd.MultiIndex):
                df_h.columns = df_h.columns.get_level_values(0)
            if not df_h.empty:
                df_h['Fast'] = df_h['Close'].rolling(3).mean()
                df_h['Slow'] = df_h['Close'].rolling(10).mean()
                df_h = df_h.dropna()
                
                kas = 1000.0
                aandelen = 0.0
                sim_t = []
                for i in range(1, len(df_h)):
                    p = float(df_h['Close'].iloc[i])
                    if df_h['Fast'].iloc[i] > df_h['Slow'].iloc[i] and aandelen == 0 and kas > 0:
                        aandelen = kas / p
                        kas = 0.0
                        sim_t.append({"Tijd": str(df_h.index[i]), "Actie": "KOOP", "Prijs": f"${p:.2f}"})
                    elif df_h['Fast'].iloc[i] < df_h['Slow'].iloc[i] and aandelen > 0:
                        kas = aandelen * p
                        winst = kas - 1000.0
                        aandelen = 0.0
                        sim_t.append({"Tijd": str(df_h.index[i]), "Actie": "VERKOOP", "Winst": f"${winst:+,.2f}"})
                        
                eind = kas if aandelen == 0 else (aandelen * float(df_h['Close'].iloc[-1]))
                st.success(f"Backtest voltooid! Eindbedrag: **${eind:,.2f}** (Netto Winst: **${eind-1000:+,.2f}**)")
                st.line_chart(df_h[['Close', 'Fast', 'Slow']])
                if sim_t:
                    st.dataframe(pd.DataFrame(sim_t), use_container_width=True)


# ==========================================
# PAGINA 4: INSTELLINGEN
# ==========================================
elif st.session_state.actieve_pagina == "settings":
    st.markdown("<h1>⚙️ Bot & Risico Instellingen</h1>", unsafe_allow_html=True)
    st.markdown("Beheer indicatoren en geavanceerde risicobeheersing.")
    st.markdown("---")
    c_i1, c_i2 = st.columns(2)
    with c_i1:
        st.subheader("📈 Indicatoren")
        st.session_state.fast_window = st.slider("Snelle MA", 2, 10, st.session_state.fast_window)
        st.session_state.slow_window = st.slider("Trage MA", 5, 25, st.session_state.slow_window)
    with c_i2:
        st.subheader("🛡️ Pro Risicobeheer")
        st.session_state.take_profit_pct = st.slider("Take-Profit %", 2.0, 20.0, st.session_state.take_profit_pct)
        st.session_state.circuit_breaker_pct = st.slider("Circuit Breaker Noodstop %", 2.0, 15.0, st.session_state.circuit_breaker_pct)
        st.session_state.gebruik_partial_tp = st.checkbox("Gedeeltelijke Take-Profit (50%)", value=st.session_state.gebruik_partial_tp)
        st.session_state.gebruik_atr = st.checkbox("ATR Dynamische Stop-Loss", value=st.session_state.gebruik_atr)
        
    st.markdown("---")
    if st.button("🔄 Reset Alle Markten & Noodstops"):
        for t_sym in beschikbare_tickers:
            all_states[t_sym] = {"kasgeld": VAST_KAPITAAL_PER_MARKT, "aantal_aandelen": 0.0, "gekocht_voor": 0.0, "instap_prijs": 0.0, "hoogste_prijs": 0.0, "noodstop_actief": False, "trades": []}
        save_all_states(all_states)
        st.success("Alles gereset naar schone start!")
        st.rerun()