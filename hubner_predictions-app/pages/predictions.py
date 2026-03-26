# pages/descriptive.py
from __future__ import annotations
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

# Register page
dash.register_page(__name__, name="Predictions Analytics", path="/predictions")

layout = dbc.Container([
    html.H1("Predictions Analytics", className="mt-4 mb-4"),

    html.P(
        "These visuals are temporary placeholders provided by the Data Science team "
        "to represent the upcoming machine learning model integration.",
        className="mb-4"
    ),

    # ---- Image Grid ----
    dbc.Row([
        dbc.Col([
            html.H4("Model Comparison – Test R² (2024)"),
            html.Img(
                src="/assets/model_comparison_r_squared.png",
                style={"width": "100%", "border": "1px solid #ccc", "borderRadius": "5px"}
            )
        ], md=6),

        dbc.Col([
            html.H4("Model Comparison – RMSE / Mean (2024)"),
            html.Img(
                src="/assets/model_comparison_rmse.png",
                style={"width": "100%", "border": "1px solid #ccc", "borderRadius": "5px"}
            )
        ], md=6),
    ], className="mb-5"),

    dbc.Row([
        dbc.Col([
            html.H4("Elbow Method for Optimal k (PLF Binning)"),
            html.Img(
                src="/assets/elbow_method.png",
                style={"width": "100%", "border": "1px solid #ccc", "borderRadius": "5px"}
            )
        ], md=6),

        dbc.Col([
            html.H4("Actual vs Predicted Quantity by PLF Bin (2024)"),
            html.Img(
                src="/assets/mean_actual_vs_predicted_quantity.png",
                style={"width": "100%", "border": "1px solid #ccc", "borderRadius": "5px"}
            )
        ], md=6),
    ], className="mb-5"),

], fluid=True)
