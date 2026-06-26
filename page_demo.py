from datetime import datetime, timedelta
import random

from dash import Dash, Input, Output, dcc, html
import plotly.graph_objects as go


BUCKET_MINUTES = 5
HOURS = 24
BUCKET_COUNT = HOURS * 60 // BUCKET_MINUTES
REFRESH_MS = 60_000

SERVICES = [
    "gateway",
    "auth-api",
    "order-api",
    "payment-api",
    "inventory-api",
    "search-api",
    "notification",
    "reporting",
]

# z values are normalized by zmin/zmax, so these stops map meaningful latency
# thresholds into a continuous red/yellow/green scale.
LATENCY_COLORSCALE = [
    [0.00, "#e8f7dd"],
    [0.08, "#22c55e"],  # about 100 ms
    [0.25, "#f4d35e"],  # about 300 ms
    [0.42, "#f97316"],  # about 500 ms
    [1.00, "#991b1b"],  # 1200 ms+
]


def floor_to_5_minutes(value):
    minute = value.minute - (value.minute % BUCKET_MINUTES)
    return value.replace(minute=minute, second=0, microsecond=0)


def generate_demo_data():
    end_time = floor_to_5_minutes(datetime.now())
    timestamps = [
        end_time - timedelta(minutes=BUCKET_MINUTES * (BUCKET_COUNT - index - 1))
        for index in range(BUCKET_COUNT)
    ]

    matrix = []
    details = []

    for service_index, service in enumerate(SERVICES):
        baseline = 45 + service_index * 18
        service_values = []
        service_details = []

        for index, timestamp in enumerate(timestamps):
            hour = timestamp.hour
            business_hour_pressure = 80 if 9 <= hour <= 18 else 0
            wave = 35 * (1 + random.random()) if index % 37 < 10 else 0
            incident = random.randint(350, 850) if random.random() < 0.015 else 0
            jitter = random.randint(-20, 75)
            latency = max(5, int(baseline + business_hour_pressure + wave + incident + jitter))

            service_values.append(latency)
            service_details.append(
                [
                    service,
                    timestamp.strftime("%Y-%m-%d %H:%M"),
                    status_for_latency(latency),
                ]
            )

        matrix.append(service_values)
        details.append(service_details)

    return timestamps, matrix, details


def status_for_latency(latency):
    if latency < 100:
        return "good"
    if latency < 500:
        return "warning"
    return "slow"


def build_figure():
    timestamps, matrix, details = generate_demo_data()

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=timestamps,
            y=SERVICES,
            customdata=details,
            zmin=0,
            zmax=1200,
            colorscale=LATENCY_COLORSCALE,
            colorbar={
                "title": "Latency",
                "ticksuffix": " ms",
                "tickvals": [0, 100, 300, 500, 800, 1200],
            },
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Time: %{customdata[1]}<br>"
                "Latency: %{z} ms<br>"
                "Status: %{customdata[2]}"
                "<extra></extra>"
            ),
            xgap=1,
            ygap=2,
        )
    )

    fig.update_layout(
        title={
            "text": "Last 24 Hours Latency Heatmap",
            "x": 0.02,
            "xanchor": "left",
            "font": {"size": 20},
        },
        margin={"l": 110, "r": 40, "t": 70, "b": 55},
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        height=520,
        xaxis={
            "title": "Time, 5-minute buckets",
            "tickformat": "%H:%M",
            "nticks": 25,
            "showgrid": False,
        },
        yaxis={
            "title": "",
            "autorange": "reversed",
            "showgrid": False,
        },
        font={"family": "Arial, sans-serif", "color": "#172033"},
    )

    return fig


app = Dash(__name__)
app.title = "Latency Monitor Demo"

app.layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.H1("24h Latency Monitor"),
                        html.P(
                            "Each cell represents one service in a 5-minute time bucket. "
                            "Color depth follows the concrete latency value."
                        ),
                    ],
                    className="title-block",
                ),
                html.Div(
                    [
                        html.Div([html.Span(className="dot green"), " <100 ms"]),
                        html.Div([html.Span(className="dot yellow"), " 100-499 ms"]),
                        html.Div([html.Span(className="dot red"), " >=500 ms"]),
                    ],
                    className="legend",
                ),
            ],
            className="header",
        ),
        dcc.Graph(
            id="latency-heatmap",
            figure=build_figure(),
            config={"displayModeBar": True, "responsive": True},
        ),
        html.Div(id="last-updated", className="updated"),
        dcc.Interval(id="refresh", interval=REFRESH_MS, n_intervals=0),
    ],
    className="page",
)

app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                margin: 0;
                background: #f4f6f8;
                color: #172033;
                font-family: Arial, sans-serif;
            }
            .page {
                max-width: 1280px;
                margin: 0 auto;
                padding: 24px;
            }
            .header {
                align-items: flex-end;
                display: flex;
                gap: 24px;
                justify-content: space-between;
                margin-bottom: 16px;
            }
            h1 {
                font-size: 26px;
                line-height: 1.2;
                margin: 0 0 6px;
            }
            p {
                color: #5b6472;
                font-size: 14px;
                margin: 0;
            }
            .legend {
                align-items: center;
                display: flex;
                flex-wrap: wrap;
                gap: 14px;
                color: #3c4656;
                font-size: 13px;
                white-space: nowrap;
            }
            .dot {
                border-radius: 50%;
                display: inline-block;
                height: 10px;
                margin-right: 5px;
                width: 10px;
            }
            .green { background: #22c55e; }
            .yellow { background: #f4d35e; }
            .red { background: #991b1b; }
            .updated {
                color: #6b7280;
                font-size: 12px;
                margin-top: 8px;
                text-align: right;
            }
            @media (max-width: 760px) {
                .page {
                    padding: 16px;
                }
                .header {
                    align-items: flex-start;
                    flex-direction: column;
                }
                h1 {
                    font-size: 22px;
                }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""


@app.callback(
    Output("latency-heatmap", "figure"),
    Output("last-updated", "children"),
    Input("refresh", "n_intervals"),
)
def refresh_heatmap(_):
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return build_figure(), f"Last updated: {updated_at}"


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
