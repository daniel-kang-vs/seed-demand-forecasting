# app.py
import dash
from dash import Dash, html
import dash_bootstrap_components as dbc

external_stylesheets = [
    dbc.themes.BOOTSTRAP,
    "https://use.fontawesome.com/releases/v5.15.4/css/all.css",
    # Do NOT include "/assets/custom.css" here; Dash auto-serves files in ./assets
]

app = Dash(
    __name__,
    use_pages=True,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True,  # important for Dash Pages
)

# Optional: raise upload size limit (default Flask limit can be small)
app.server.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

app.layout = html.Div([
    dbc.NavbarSimple(
        children=[
            dbc.NavItem(dbc.NavLink('Descriptive Analytics', href='/')),
            dbc.NavItem(dbc.NavLink('Predictions Analytics', href='/predictions')),
            dbc.NavItem(dbc.NavLink('Upload Data', href='/upload')),
        ],
        brand=dbc.Row(
            [
                dbc.Col(html.Img(src="/assets/hubner_logo.png", height="50px")),
                dbc.Col(
                    "Seed Demand Forecasting Analytics Dashboard",
                    style={"fontWeight": "bold", "color": "#333", "marginLeft": "10px"}
                ),
            ],
            align="center",
            className="g-0"
        ),
        brand_href="/",
        color="light",
        dark=False
    ),
    dash.page_container
])

if __name__ == "__main__":
    app.run(debug=True)
