from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data" / "processed" / "public"

st.set_page_config(page_title="Customer Retention Intelligence", page_icon="📈", layout="wide")
st.title("Customer Retention Intelligence")
st.caption("A time-aware, portfolio-scale repeat-purchase inactivity monitor")


@st.cache_data

def load_artifacts(artifact_version: int) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required = [
        "metrics.json", "monthly_performance.csv", "segment_performance.csv",
        "retention_cohorts.csv", "risk_deciles.csv", "feature_summary.csv",
    ]
    missing = [name for name in required if not (PUBLIC / name).exists()]
    if missing:
        raise FileNotFoundError(
            "Reviewed public artifacts are missing: " + ", ".join(missing)
            + ". Run `uv run python scripts/run_pipeline.py` from the project root."
        )
    metrics = json.loads((PUBLIC / "metrics.json").read_text(encoding="utf-8-sig"))
    return (
        metrics,
        pd.read_csv(PUBLIC / "monthly_performance.csv"),
        pd.read_csv(PUBLIC / "segment_performance.csv"),
        pd.read_csv(PUBLIC / "retention_cohorts.csv"),
        pd.read_csv(PUBLIC / "risk_deciles.csv"),
        pd.read_csv(PUBLIC / "feature_summary.csv"),
    )


try:
    artifact_version = (PUBLIC / "metrics.json").stat().st_mtime_ns if (PUBLIC / "metrics.json").exists() else 0
    metrics, monthly, segments, cohorts, deciles, features = load_artifacts(artifact_version)
except (FileNotFoundError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

source = metrics["source"]
test = metrics["locked_temporal_test"]
model = test["model"]
recency = test["recency_only_ranker"]
prevalence_ap = test["prevalence_baseline_average_precision"]
latest = source["last_purchase_date"]

st.warning(
    "Historical public demo: one UK giftware retailer, 2009–2011. The target is **90-day purchase inactivity**, "
    "not a confirmed cancellation. This dashboard supports analysis and model review; it does not send offers, "
    "estimate causal campaign uplift, or represent Amex/cardmember data."
)

with st.sidebar:
    st.header("Scope and data")
    st.write(f"**Source years:** {source['first_purchase_date'][:4]}–{latest[:4]}")
    st.write(f"**Eligible source customers:** {source['identified_customers']:,}")
    st.write(f"**Historical monthly snapshots:** {metrics['snapshot_count']}")
    st.write(f"**Locked test starts:** {metrics['time_split']['locked_test_from']}")
    st.caption("The hosted app reads reviewed aggregate artifacts only. Raw transaction rows, customer IDs, and fitted weights stay out of the public repository.")
    st.markdown("[UCI dataset page](https://archive.ics.uci.edu/dataset/502/online+retail+ii) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)")

st.subheader("Decision view")
c1, c2 = st.columns(2)
c1.metric("Test inactivity rate", f"{model['inactivity_prevalence']:.1%}", help="90-day inactivity rate among eligible customer-month episodes in the later holdout.")
c2.metric("Average precision", f"{model['average_precision']:.3f}", help="Compared with the test-set inactivity prevalence baseline and a recency-only ranker.")
c3, c4 = st.columns(2)
c3.metric("Lift in highest-risk 10%", f"{model['lift_at_10pct']:.2f}×", help="Precision in the top score decile divided by overall temporal-test inactivity prevalence.")
c4.metric("Temporal test episodes", f"{model['rows']:,}", help="Repeated customer-month episodes; not unique customers.")

if model["average_precision"] > prevalence_ap:
    st.success(f"The selected ranking beats the no-skill prevalence baseline (AP {prevalence_ap:.3f}) on the locked later-period sample.")
else:
    st.info(f"The selected ranking does not beat the no-skill prevalence baseline (AP {prevalence_ap:.3f}) on this locked later-period sample.")
if model["brier_score"] > test["constant_prevalence_brier_score"]:
    st.info("Probability calibration is weaker than a constant-prevalence forecast on this holdout. Use the score for cautious ranking research, not individual probability promises.")

main_tab, segment_tab, cohort_tab, model_tab, scenario_tab, method_tab = st.tabs([
    "Overview", "Customer segments", "Cohort retention", "Model validation", "Decision scenario", "Method & limits"
])

with main_tab:
    st.markdown("#### Later-period model performance")
    monthly_long = monthly.melt(
        id_vars=["snapshot_month"],
        value_vars=["model_average_precision", "recency_baseline_average_precision"],
        var_name="ranker", value_name="average_precision",
    )
    monthly_long["ranker"] = monthly_long["ranker"].map({
        "model_average_precision": "Selected model",
        "recency_baseline_average_precision": "Recency-only baseline",
    })
    fig = px.line(
        monthly_long, x="snapshot_month", y="average_precision", color="ranker",
        markers=True, labels={"snapshot_month": "Snapshot month", "average_precision": "Average precision", "ranker": "Ranking"},
        color_discrete_map={"Selected model": "#176b87", "Recency-only baseline": "#bd6b25"},
    )
    fig.add_hline(y=prevalence_ap, line_dash="dot", line_color="#65758b", annotation_text=f"Prevalence baseline {prevalence_ap:.2f}")
    fig.update_layout(height=360, legend=dict(orientation="h", y=-0.25), margin=dict(l=10, r=10, t=15, b=40))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Risk deciles in the locked temporal test")
    chart = deciles.sort_values("risk_decile", ascending=True)
    fig = px.bar(
        chart, x="risk_decile", y="inactivity_rate", color="avg_predicted_risk",
        color_continuous_scale="Blues", labels={"risk_decile": "Score decile (1 = highest risk)", "inactivity_rate": "Observed 90-day inactivity", "avg_predicted_risk": "Mean model score"},
        hover_data={"eligible_episodes": True, "avg_spend_180d_gbp": ":.2f"},
    )
    fig.update_layout(height=360, coloraxis_showscale=False, margin=dict(l=10, r=10, t=15, b=30))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Monthly test slices can be noisy. Scores rank historical inactivity risk; they do not identify customers who would respond to an offer.")

with segment_tab:
    st.markdown("#### Where observed inactivity concentrates")
    dimension = st.selectbox("Segment by", segments["dimension"].drop_duplicates().tolist())
    segment_view = segments.loc[segments["dimension"].eq(dimension)].sort_values("inactivity_rate")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=segment_view["inactivity_rate"], y=segment_view["segment"], orientation="h",
        marker_color="#176b87", error_x=dict(
            type="data", symmetric=False,
            array=segment_view["ci_95_high"] - segment_view["inactivity_rate"],
            arrayminus=segment_view["inactivity_rate"] - segment_view["ci_95_low"],
        ),
        customdata=segment_view[["eligible_episodes", "avg_spend_180d_gbp"]],
        hovertemplate="%{y}<br>Inactivity: %{x:.1%}<br>Eligible episodes: %{customdata[0]:,}<br>Mean historical 180-day gross sales: £%{customdata[1]:,.0f}<extra></extra>",
    ))
    fig.update_layout(height=max(300, 58 * len(segment_view)), xaxis_tickformat=".0%", xaxis_title="Observed 90-day inactivity", yaxis_title="", margin=dict(l=10, r=15, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Intervals are Wilson 95% intervals for descriptive rates. Segments are not causal drivers; small groups are suppressed below 50 episodes.")
    st.dataframe(segment_view[["segment", "eligible_episodes", "inactivity_rate", "ci_95_low", "ci_95_high", "avg_spend_180d_gbp"]].style.format({
        "inactivity_rate": "{:.1%}", "ci_95_low": "{:.1%}", "ci_95_high": "{:.1%}", "avg_spend_180d_gbp": "£{:,.2f}"
    }), use_container_width=True, hide_index=True)

with cohort_tab:
    st.markdown("#### Repeat-purchase rates by first-purchase cohort")
    cohort_long = cohorts.melt(
        id_vars=["cohort_month", "customers"],
        value_vars=["repeat_rate_30d", "repeat_rate_90d", "repeat_rate_180d", "repeat_rate_365d"],
        var_name="window", value_name="repeat_rate",
    )
    cohort_long["window"] = cohort_long["window"].map({
        "repeat_rate_30d": "30 days", "repeat_rate_90d": "90 days",
        "repeat_rate_180d": "180 days", "repeat_rate_365d": "365 days",
    })
    fig = px.line(
        cohort_long, x="cohort_month", y="repeat_rate", color="window", markers=True,
        hover_data={"customers": True},
        labels={"cohort_month": "First-purchase cohort", "repeat_rate": "Repeat-purchase rate", "window": "Follow-up window", "customers": "Customers"},
        color_discrete_sequence=["#e39b3d", "#1f8a70", "#176b87", "#6a63a8"],
    )
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    fig.update_layout(height=380, xaxis_tickangle=-35, legend=dict(orientation="h", y=-0.35), margin=dict(l=10, r=10, t=15, b=70))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Only cohorts with the full follow-up window are reported. A purchase in the window is a repeat-purchase signal, not a measured retention intervention effect.")

with model_tab:
    st.markdown("#### Locked temporal evaluation")
    st.write(f"**Selected model:** `{metrics['model_selection']['selected_model']}`; chosen using validation average precision only.")
    st.write(f"**Validation months:** {metrics['time_split']['validation_from'][:7]} to before {metrics['time_split']['validation_before'][:7]} · **Test months:** {', '.join(metrics['time_split']['test_months'])}.")
    table = pd.DataFrame([
        {"Ranking": "Selected model", **model},
        {"Ranking": "Recency-only baseline", **recency},
    ])
    keep = ["Ranking", "rows", "inactivity_prevalence", "average_precision", "roc_auc", "brier_score", "log_loss", "precision_at_10pct", "recall_at_10pct", "lift_at_10pct"]
    st.dataframe(table[keep].style.format({
        "inactivity_prevalence": "{:.1%}", "average_precision": "{:.3f}", "roc_auc": "{:.3f}",
        "brier_score": "{:.3f}", "log_loss": "{:.3f}", "precision_at_10pct": "{:.1%}",
        "recall_at_10pct": "{:.1%}", "lift_at_10pct": "{:.2f}×",
    }), use_container_width=True, hide_index=True)
    st.markdown("#### Mean predicted versus observed inactivity by score decile")
    calibration = deciles.sort_values("avg_predicted_risk")
    calibration_fig = go.Figure()
    calibration_fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration",
        line=dict(color="#7b8794", dash="dash"),
    ))
    calibration_fig.add_trace(go.Scatter(
        x=calibration["avg_predicted_risk"], y=calibration["inactivity_rate"],
        mode="markers+lines+text", text=calibration["risk_decile"],
        textposition="top center", name="Observed decile rate",
        marker=dict(size=10, color="#176b87"),
        hovertemplate="Decile: %{text}<br>Mean predicted: %{x:.1%}<br>Observed: %{y:.1%}<extra></extra>",
    ))
    calibration_fig.update_layout(
        height=340, xaxis=dict(title="Mean predicted probability", tickformat=".0%", range=[0, 1]),
        yaxis=dict(title="Observed inactivity rate", tickformat=".0%", range=[0, 1]),
        legend=dict(orientation="h", y=-0.25), margin=dict(l=10, r=10, t=10, b=40),
    )
    st.plotly_chart(calibration_fig, use_container_width=True)
    st.caption("Decile calibration is an aggregate diagnostic. Do not interpret each episode probability as a promise or deploy a business threshold from this sample.")
    st.markdown("#### Aggregate model signals")
    if "coefficient" in features.columns:
        signal = features.head(12).sort_values("coefficient")
        fig = px.bar(signal, x="coefficient", y="feature", orientation="h", color="direction", color_discrete_sequence=["#176b87", "#bd6b25"], labels={"coefficient": "Standardized model coefficient", "feature": "Point-in-time feature", "direction": "Association direction"})
    else:
        signal = features.head(12).sort_values("importance")
        fig = px.bar(signal, x="importance", y="feature", orientation="h", error_x="importance_std" if "importance_std" in signal else None, color_discrete_sequence=["#176b87"], labels={"importance": "Permutation importance (AP decrease)", "feature": "Point-in-time feature"})
    fig.update_layout(height=420, showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Model signals describe predictive association. They are not causal explanations or retention levers.")

with scenario_tab:
    st.markdown("#### Capacity and economics: assumptions, not measured uplift")
    st.write("This scenario shows what an intervention would need to achieve to cover its costs. The dataset has no offer history or randomized control group, so campaign response and savings are unknown.")
    top_count = int(deciles.loc[deciles["risk_decile"].eq(1), "eligible_episodes"].sum())
    top_count = max(top_count, 1)
    col1, col2 = st.columns(2)
    with col1:
        review_share = st.slider("Share of highest-risk episodes a team can review", 10, 100, 50, 5)
        contact_cost = st.number_input("Contact cost per targeted customer (£)", min_value=0.0, value=1.0, step=0.5)
    with col2:
        offer_cost = st.number_input("Offer/service cost per targeted customer (£)", min_value=0.0, value=8.0, step=1.0)
        contribution_value = st.number_input("Assumed contribution value per incremental retained customer (£)", min_value=1.0, value=100.0, step=10.0)
    assumed_lift = st.slider("Assumed incremental retention lift", 0, 30, 5, 1) / 100
    recipients = top_count * review_share / 100
    break_even = min(1.0, (contact_cost + offer_cost) / contribution_value)
    expected_incremental = recipients * assumed_lift
    scenario_net = recipients * (assumed_lift * contribution_value - contact_cost - offer_cost)
    a, b, c = st.columns(3)
    a.metric("Illustrative reviewed episodes", f"{recipients:,.0f}")
    b.metric("Break-even incremental lift", f"{break_even:.1%}")
    net_label = f"-£{abs(scenario_net):,.0f}" if scenario_net < 0 else f"£{scenario_net:,.0f}"
    c.metric("Scenario net contribution", net_label)
    st.caption(f"At the entered assumptions, this would imply about {expected_incremental:,.0f} incremental retained episodes. Every value above is user-entered scenario math; none is estimated or validated by this dataset.")

with method_tab:
    st.markdown("#### Prediction contract")
    contract = metrics["prediction_contract"]
    st.write(f"- **Unit:** {contract['unit']}.")
    st.write(f"- **Snapshot:** {contract['snapshot']}.")
    st.write(f"- **Outcome:** {contract['target']}.")
    st.write(f"- **Inputs:** {contract['features']}.")
    st.markdown("#### Data and model boundaries")
    st.markdown(
        "- UCI describes this as a real two-year UK online-retail dataset, mostly giftware, with many wholesalers. "
        "It is historical (2009–2011), from one company, and not representative of a current card portfolio.\n"
        "- Missing customer IDs and cancellation/return lines are excluded from purchase episodes. The public app uses grouped outputs; no customer-level IDs or scores are published.\n"
        "- Monthly snapshots overlap by customer. The later test evaluates future periods for a historical retailer, not independent institutions or the current economy.\n"
        "- A no-purchase proxy is not a confirmed cancellation, and a high inactivity score does not imply that a campaign will prevent it.\n"
        "- Amex relevance is limited to transferable analytics workflow: customer behavior features, risk ranking, temporal validation, capacity planning, and model governance."
    )
    st.markdown("#### Sources and attribution")
    st.markdown("- Chen, D. (2012). [Online Retail II, UCI Machine Learning Repository](https://doi.org/10.24432/C5CG6D), licensed CC BY 4.0.")
    st.markdown("- Rebuild locally with `uv sync` followed by `uv run python scripts/run_pipeline.py`. See the repository README and model card for the complete runbook.")

st.divider()
st.caption("Customer Retention Intelligence · public portfolio decision-support prototype · data and model vintage are shown above")
