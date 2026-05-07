import streamlit as st
import pandas as pd
import random
from collections import defaultdict

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="FRC Dashboard", layout="wide")

# =========================
# SIDEBAR SETTINGS
# =========================
st.sidebar.header("Settings")

MY_TEAM = int(st.sidebar.number_input("Team Number", value=2530))
NUM_SIMS = st.sidebar.slider("Simulations", 10, 200, 50)
RANDOMNESS = st.sidebar.slider("Randomness", 5, 30, 15)

VIEW_MODE = st.sidebar.radio(
    "Match View",
    ["Your Matches", "All Matches"]
)

# ✅ NEW: row control
ROW_LIMIT = st.sidebar.selectbox(
    "Rows to Show",
    ["All", "10", "20", "50"],
    index=0
)

# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_data():
    schedule = pd.read_csv("frc_schedule.csv")

    epa_data = pd.read_csv("2026_insights.csv")
    epa_data.columns = [c.replace('"', '').strip() for c in epa_data.columns]

    team_epa = dict(zip(
        epa_data["num"].astype(int),
        epa_data["total_epa"].astype(float)
    ))

    return schedule, team_epa

schedule, team_epa = load_data()

def get_epa(team):
    return team_epa.get(int(team), 30)

# =========================
# HEADER
# =========================
st.title(f"Team {MY_TEAM} Dashboard")

# =========================
# MATCH TABLE
# =========================
st.subheader("Matches")

match_rows = []

for _, row in schedule.iterrows():
    blue = [row["Blue1"], row["Blue2"], row["Blue3"]]
    red = [row["Red1"], row["Red2"], row["Red3"]]

    if VIEW_MODE == "Your Matches" and MY_TEAM not in blue + red:
        continue

    blue_epa = sum(get_epa(t) for t in blue)
    red_epa = sum(get_epa(t) for t in red)

    diff = blue_epa - red_epa
    prob_blue = 1 / (1 + 10 ** (-diff / 25))

    if MY_TEAM in blue:
        win_prob = prob_blue
        alliance_color = "Blue"
        alliance_teams = blue
        opponents = red
    elif MY_TEAM in red:
        win_prob = 1 - prob_blue
        alliance_color = "Red"
        alliance_teams = red
        opponents = blue
    else:
        win_prob = prob_blue
        alliance_color = "-"
        alliance_teams = blue
        opponents = red

    my_total = sum(get_epa(t) for t in alliance_teams)
    opp_total = sum(get_epa(t) for t in opponents)

    if win_prob >= 0.65:
        status = "✅"
    elif win_prob <= 0.35:
        status = "⚠️"
    else:
        status = "➖"

    match_rows.append({
        "Match": row["Match"],
        "Time": row["Time"],
        "Alliance": alliance_color,
        "Alliance Teams": ", ".join(map(str, alliance_teams)),
        "Opponents": ", ".join(map(str, opponents)),
        "Win %": f"{round(win_prob * 100)}%",
        "Score Est": f"{int(my_total)}–{int(opp_total)}",
        "Outlook": status
    })

match_df = pd.DataFrame(match_rows)

# ✅ apply row limit
if ROW_LIMIT != "All":
    match_df = match_df.head(int(ROW_LIMIT))

st.dataframe(match_df, use_container_width=True)

# =========================
# SIMULATION
# =========================
if st.button("Run Simulation"):

    results = defaultdict(list)

    def simulate_event():
        rp = defaultdict(int)

        for _, row in schedule.iterrows():
            blue = [row["Blue1"], row["Blue2"], row["Blue3"]]
            red = [row["Red1"], row["Red2"], row["Red3"]]

            blue_epa = sum(get_epa(t) for t in blue)
            red_epa = sum(get_epa(t) for t in red)

            blue_score = random.gauss(blue_epa, RANDOMNESS)
            red_score = random.gauss(red_epa, RANDOMNESS)

            if blue_score > red_score:
                for t in blue:
                    rp[t] += 2
            else:
                for t in red:
                    rp[t] += 2

        return sorted(rp.items(), key=lambda x: x[1], reverse=True)

    for _ in range(NUM_SIMS):
        ranking = simulate_event()

        for rank, (team, _) in enumerate(ranking):
            results[team].append(rank + 1)

    avg = []
    for team, ranks in results.items():
        avg_rank = sum(ranks) / len(ranks)
        avg.append((team, avg_rank))

    avg.sort(key=lambda x: x[1])
    results_df = pd.DataFrame(avg, columns=["Team", "Average Rank"])

    if MY_TEAM in results:
        my = results[MY_TEAM]
        avg_rank = sum(my) / len(my)
        top8 = sum(1 for r in my if r <= 8) / len(my)

        col1, col2 = st.columns(2)
        col1.metric("Average Rank", f"{avg_rank:.2f}")
        col2.metric("Top 8 Chance", f"{top8*100:.0f}%")

    st.subheader("Predicted Rankings")
    st.dataframe(results_df, use_container_width=True)
