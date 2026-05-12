import streamlit as st
import pandas as pd
import random
from collections import defaultdict
import glob

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="FRC Dashboard", layout="wide")

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Settings")

MY_TEAM = int(st.sidebar.number_input("Team Number", value=4607))
NUM_SIMS = st.sidebar.slider("Simulations", 10, 200, 50)
RANDOMNESS = st.sidebar.slider("Randomness", 5, 30, 15)

VIEW_MODE = st.sidebar.radio("Match View", ["Your Matches", "All Matches"])

# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_data():
    schedule = pd.read_csv("new.csv")

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
# EVENT TEAM LIST
# =========================
schedule_teams = set()

for _, row in schedule.iterrows():
    schedule_teams.update([
        row["Blue1"], row["Blue2"], row["Blue3"],
        row["Red1"], row["Red2"], row["Red3"]
    ])

# =========================
# LOAD COPR FILES
# =========================
@st.cache_data
def load_stats():
    files = glob.glob("team_stats_*.csv")
    dfs = []

    for f in files:
        df = pd.read_csv(f)
        df["Event"] = f.replace("team_stats_", "").replace(".csv", "")
        dfs.append(df)

    if not dfs:
        return None

    df = pd.concat(dfs, ignore_index=True)
    df = df[df["Team"].isin(schedule_teams)]
    df = df.drop_duplicates(subset="Team", keep="last")

    return df

stats_df = load_stats()

# =========================
# HELPER: GET STAT
# =========================
def get_stat(team, stat):
    if stats_df is None:
        return None

    row = stats_df[stats_df["Team"] == team]
    if row.empty:
        return None

    val = row.iloc[0].get(stat)
    if pd.isna(val):
        return None

    return round(val, 1)

# =========================
# HEADER
# =========================
st.title(f"Team {MY_TEAM} Dashboard")

# =========================
# TABS
# =========================
tab1, tab2, tab3 = st.tabs(["Match Predictions", "Simulation", "Team Stats"])

# =========================
# MATCH TAB
# =========================
with tab1:
    st.subheader("Matches")

    stat_options = [
        "OPR",
        "Hub Total Fuel Count",
        "Hub First Active Shift Count",
        "Hub Second Active Shift Count",
        "Minor Foul Count",
        "Major Foul Count"
    ]

    selected_stat = st.selectbox("Stat to display", stat_options)

    rows = []

    for _, row in schedule.iterrows():
        blue = [row["Blue1"], row["Blue2"], row["Blue3"]]
        red = [row["Red1"], row["Red2"], row["Red3"]]

        if VIEW_MODE == "Your Matches" and MY_TEAM not in blue + red:
            continue

        blue_score = sum(get_epa(t) for t in blue)
        red_score = sum(get_epa(t) for t in red)

        diff = blue_score - red_score
        prob_blue = 1 / (1 + 10 ** (-diff / 25))

        if MY_TEAM in blue:
            win_prob = prob_blue
        elif MY_TEAM in red:
            win_prob = 1 - prob_blue
        else:
            win_prob = prob_blue

        rows.append({
            "Match": row["Match"],
            "Time": row["Time"],

            "Blue1": f"{blue[0]} ({get_stat(blue[0], selected_stat)})",
            "Blue2": f"{blue[1]} ({get_stat(blue[1], selected_stat)})",
            "Blue3": f"{blue[2]} ({get_stat(blue[2], selected_stat)})",

            "Red1": f"{red[0]} ({get_stat(red[0], selected_stat)})",
            "Red2": f"{red[1]} ({get_stat(red[1], selected_stat)})",
            "Red3": f"{red[2]} ({get_stat(red[2], selected_stat)})",

            "Win %": f"{round(win_prob * 100)}%",
            "Score Est": f"{int(blue_score)}–{int(red_score)}"
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True)

# =========================
# SIMULATION TAB
# =========================
with tab2:
    st.subheader("Simulation")

    if st.button("Run Simulation"):

        results = defaultdict(list)

        def simulate():
            rp = defaultdict(int)

            for _, row in schedule.iterrows():
                blue = [row["Blue1"], row["Blue2"], row["Blue3"]]
                red = [row["Red1"], row["Red2"], row["Red3"]]

                blue_score = random.gauss(sum(get_epa(t) for t in blue), RANDOMNESS)
                red_score = random.gauss(sum(get_epa(t) for t in red), RANDOMNESS)

                if blue_score > red_score:
                    for t in blue:
                        rp[t] += 2
                else:
                    for t in red:
                        rp[t] += 2

            return sorted(rp.items(), key=lambda x: x[1], reverse=True)

        for _ in range(NUM_SIMS):
            ranking = simulate()

            for rank, (team, _) in enumerate(ranking):
                results[team].append(rank + 1)

        avg = [(t, sum(r)/len(r)) for t, r in results.items()]
        avg.sort(key=lambda x: x[1])

        df = pd.DataFrame(avg, columns=["Team", "Average Rank"])

        if MY_TEAM in results:
            my = results[MY_TEAM]

            col1, col2 = st.columns(2)
            col1.metric("Average Rank", f"{sum(my)/len(my):.2f}")
            col2.metric("Top 8 Chance", f"{sum(r <= 8 for r in my)/len(my)*100:.0f}%")

        st.dataframe(df, use_container_width=True)

# =========================
# TEAM STATS TAB
# =========================
with tab3:
    st.subheader("Team Statistics")

    if stats_df is None or stats_df.empty:
        st.error("No valid team stats found.")
    else:
        df = stats_df.copy()

        st.write(f"Showing {len(df)} teams in event")

        df["⭐"] = df["Team"].apply(lambda t: "⭐" if t == MY_TEAM else "")

        sort_col = st.selectbox("Sort by", df.columns)
        df = df.sort_values(by=sort_col, ascending=False)

        def color_series(s):
            colors = []
            for val in s:
                if pd.isna(val):
                    colors.append("")
                    continue

                v = max(min(val, 1), -1)

                if v > 0:
                    intensity = int(255 - v * 150)
                    colors.append(f"background-color: rgb({intensity},255,{intensity})")
                elif v < 0:
                    intensity = int(255 - abs(v) * 150)
                    colors.append(f"background-color: rgb(255,{intensity},{intensity})")
                else:
                    colors.append("")
            return colors

        styled = df.style.apply(color_series, subset=["Minor Foul Count"])
        styled = styled.apply(color_series, subset=["Major Foul Count"])

        if MY_TEAM in df["Team"].values:
            my = df[df["Team"] == MY_TEAM].iloc[0]

            col1, col2, col3 = st.columns(3)
            col1.metric("OPR", f"{my['OPR']:.1f}")
            col2.metric("Fuel", f"{my['Hub Total Fuel Count']:.1f}")
            col3.metric("Fouls", f"{my['Minor Foul Count']:.2f}")

        st.write(styled)