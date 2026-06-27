from __future__ import annotations

from datetime import datetime
import logging
import math
import os
from pathlib import Path
import shutil

from dash import Dash, Input, Output, dcc, html
import plotly
import plotly.graph_objects as go

from inspect_core.config import AppConfig, ColorConfig, TargetConfig, load_config
from inspect_core.db import fetch_latest_results, fetch_results, init_db
from inspect_core.scheduler import ProbeScheduler
from inspect_core.time_utils import epoch_ms_to_label, epoch_ms_to_short_label, floor_epoch_ms, now_epoch_ms


# 【BUG 修复】：拉大负数特殊值区间，防止 Plotly 在 256 色纹理采样时将灰色与黑色融合
NO_DATA_VALUE = -1000
FAILURE_VALUE = -500
PAGE_REFRESH_MS = 15_000


def configure_logging() -> None:
    level_name = os.getenv("INSPECT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


configure_logging()
logger = logging.getLogger(__name__)


def ensure_plotly_asset() -> None:
    source = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
    target = Path(__file__).parent / "assets" / "plotly.min.js"
    if target.exists() and target.stat().st_size > 0:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    logger.info("Prepared Plotly asset: %s", target)


ensure_plotly_asset()

config_path = os.getenv("INSPECT_CONFIG", "config.yaml")
logger.info("Loading config: %s", config_path)
config = load_config(config_path)
init_db(config.global_config.database_path)
logger.info("SQLite database: %s", config.global_config.database_path)
scheduler = ProbeScheduler(config)
scheduler.start()

app = Dash(__name__)
app.title = "LLM API Inspect"
server = app.server


def build_layout() -> html.Div:
    enabled_count = len(config.enabled_targets)
    total_count = len(config.targets)
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H1("LLM API Inspect"),
                            html.P(
                                # f"{enabled_count}/{total_count} targets enabled · "
                                f"{config.global_config.interval_minutes} minute probe interval · "
                                f"{config.global_config.window_hours} hour window"
                            ),
                        ],
                        className="title-block",
                    ),
                    html.Div(
                        [
                            html.Div([html.Span(className="dot no-data"), " no data"]),
                            html.Div([html.Span(className="dot ok"), " low latency"]),
                            html.Div([html.Span(className="dot warn"), " medium"]),
                            html.Div([html.Span(className="dot bad"), " high"]),
                            html.Div([html.Span(className="dot fail"), " failed"]),
                        ],
                        className="legend",
                    ),
                ],
                className="header",
            ),
            dcc.Loading(
                html.Div(
                    id="latency-heatmap-container",
                    className="graph-container",
                ),
                type="default",
            ),
            html.Div(
                [
                    html.Div(id="last-updated", className="updated"),
                    html.Div(id="recent-results", className="recent"),
                ],
                className="below",
            ),
            html.Footer(
                [
                    html.A(
                        [
                            html.Img(src=app.get_asset_url("github.svg"), className="github-icon", alt="GitHub"),
                            "LLMApiInspect",
                        ],
                        href="https://github.com/ljdzxx/LLMApiInspect",
                        target="_blank",
                        rel="noreferrer",
                        className="footer-link",
                    ),
                    " Powered by ",
                    html.A("JuCodex.com", href="https://JuCodex.com", target="_blank", rel="noreferrer"),
                ],
                className="page-footer",
            ),
            dcc.Interval(id="refresh", interval=PAGE_REFRESH_MS, n_intervals=0),
        ],
        className="page",
    )


app.layout = build_layout()

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
                line-height: 1.5;
            }
            .page {
                max-width: 1320px; 
                margin: 0 auto;
                padding: 24px;
            }
            .header {
                display: flex;
                flex-direction: column;
                gap: 16px;
                margin-bottom: 28px;
                border-bottom: 1px solid #e1e5ea;
                padding-bottom: 20px;
            }
            .title-block {
                display: block;
                width: 100%;
                clear: both;
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
                margin-top: 4px;
            }
            .dot {
                border-radius: 50%;
                display: inline-block;
                height: 10px;
                margin-right: 5px;
                width: 10px;
            }
            /* 【已修复】：完全恢复为读取配置文件的动态拼接变量 */
            .no-data { background: """ + config.colors.no_data + """; }
            .ok { background: """ + config.colors.latency_scale[1].color + """; }
            .warn { background: """ + config.colors.latency_scale[min(2, len(config.colors.latency_scale) - 1)].color + """; }
            .bad { background: """ + config.colors.latency_scale[-2].color + """; }
            .fail { background: """ + config.colors.failure + """; }
            
            .graph-container {
                display: block;
                width: 100%;
                margin-bottom: 32px;
                clear: both;
            }
            
            /* 单个监控目标的服务状态卡片样式 */
            .target-row-item {
                background: #ffffff;
                border: 1px solid #e1e5ea;
                border-radius: 8px;
                padding: 16px 20px;
                margin-bottom: 24px; /* 拉大不同监控目标之间的垂直间距 */
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            }
            /* 目标名称单独一行，显示在左上角 */
            .target-row-title {
                font-size: 14px;
                font-weight: 700;
                color: #172033;
                margin-bottom: 12px; /* 与下方扁平化热力图分行，并留出间距 */
                text-align: left;
                word-break: break-all;
            }
            .below {
                display: grid;
                gap: 14px;
                grid-template-columns: minmax(0, 1fr);
            }
            .updated {
                color: #6b7280;
                font-size: 12px;
                text-align: right;
            }
            .recent {
                color: #3c4656;
                font-size: 13px;
            }
            .recent-title {
                font-weight: 700;
                margin: 0 0 8px;
            }
            .recent-grid {
                display: grid;
                gap: 8px;
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            }
            .recent-item {
                background: #ffffff;
                border: 1px solid #e1e5ea;
                border-radius: 8px;
                padding: 12px 14px;
            }
            .recent-item strong {
                display: block;
                margin-bottom: 6px;
            }
            .recent-item span {
                color: #6b7280;
                display: block;
                line-height: 1.5;
            }
            .page-footer {
                color: #6b7280;
                font-size: 12px;
                margin-top: 22px;
                text-align: center;
            }
            .page-footer a {
                color: #2563eb;
                font-weight: 700;
                text-decoration: none;
            }
            .page-footer a:hover {
                text-decoration: underline;
            }
            .footer-link {
                align-items: center;
                display: inline-flex;
                gap: 5px;
                vertical-align: middle;
            }
            .github-icon {
                height: 14px;
                width: 14px;
            }
            
            @media (max-width: 760px) {
                .page {
                    padding: 16px;
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
    Output("latency-heatmap-container", "children"),
    Output("last-updated", "children"),
    Output("recent-results", "children"),
    Input("refresh", "n_intervals"),
)
def refresh_dashboard(_):
    heatmap_components = build_heatmap_components(config)
    updated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    return heatmap_components, f"Page refreshed: {updated_at}", build_recent_results(config)


def build_heatmap_components(app_config: AppConfig) -> list[html.Div]:
    global_config = app_config.global_config
    end_ms = floor_epoch_ms(now_epoch_ms(), global_config.interval_minutes)
    bucket_ms = global_config.interval_minutes * 60 * 1000
    bucket_count = math.ceil(global_config.window_hours * 60 / global_config.interval_minutes) + 1
    start_ms = end_ms - (bucket_count - 1) * bucket_ms
    buckets = [start_ms + index * bucket_ms for index in range(bucket_count)]
    rows = fetch_results(global_config.database_path, start_ms, end_ms)

    targets = app_config.enabled_targets
    if not targets:
        return [
            html.Div(
                "No enabled targets. Edit config.yaml and set at least one target enabled: true.",
                style={"textAlign": "center", "color": "#5b6472", "padding": "40px"},
            )
        ]

    target_by_id = {target.id: target for target in targets}
    result_by_cell = {}
    for row in rows:
        target = target_by_id.get(row["target_id"])
        if target is None:
            continue
        key = (row["target_id"], row["bucket_start_ms"])
        result_by_cell[key] = row

    components = []
    x_labels = [epoch_ms_to_short_label(bucket) for bucket in buckets]

    for target in targets:
        z_row = []
        custom_row = []
        for bucket in buckets:
            row = result_by_cell.get((target.id, bucket))
            if row is None:
                value = NO_DATA_VALUE
                latency = None
                started = None
            elif row["success"]:
                value = row["latency_ms"]
                latency = row["latency_ms"]
                started = row["started_at_iso"]
            else:
                value = FAILURE_VALUE
                latency = None
                started = row["started_at_iso"]

            z_row.append(value)
            
            # customdata 中仅保留两行提示需要的数据：启动时间和延迟时长
            latency_str = "n/a" if latency is None else f"{latency} ms"
            started_str = started if started else "n/a"
            custom_row.append([started_str, latency_str])

        # 为当前目标构建独立的、单行的精美热力图
        fig = go.Figure(
            data=go.Heatmap(
                z=[z_row],
                x=x_labels,
                y=[target.label],
                customdata=[custom_row],
                zmin=NO_DATA_VALUE,
                zmax=app_config.colors.max_latency_ms,
                colorscale=build_plotly_colorscale(app_config.colors),
                showscale=False,  # 不在每行显示多余的颜色条
                # 精简后的悬停文字模版
                hovertemplate=(
                    "启动时间: %{customdata[0]}<br>"
                    "延迟: %{customdata[1]}"
                    "<extra></extra>"
                ),
                xgap=2,
                ygap=0,
            )
        )

        fig.update_layout(
            margin={"l": 10, "r": 10, "t": 5, "b": 20},
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            height=55,  # 垂直高度保持精致扁平
            xaxis={
                "showgrid": False,
                "tickfont": {"size": 9, "color": "#6b7280"},
                "nticks": min(20, len(x_labels)),
            },
            yaxis={"visible": False},  # 彻底隐藏 Y 轴坐标，避免文本挤压
            font={"family": "Arial, sans-serif", "color": "#172033"},
        )

        # 封装到卡片中：目标标题在上方（独占一行），热力图在下方
        components.append(
            html.Div(
                [
                    html.Div(target.label, className="target-row-title"),
                    dcc.Graph(
                        figure=fig,
                        config={"displayModeBar": False, "responsive": True},
                        style={"height": "55px"},
                    ),
                ],
                className="target-row-item",
            )
        )

    return components


def build_plotly_colorscale(colors: ColorConfig) -> list[list[float | str]]:
    zmin = NO_DATA_VALUE
    zmax = colors.max_latency_ms
    span = zmax - zmin # 由于 zmin 从 -2 变为了 -1000，整体 Span 变大，从而拉开了灰色和黑色的渲染坐标间距

    scale: list[list[float | str]] = [
        [0.0, colors.no_data],
        [max(0.0, ((FAILURE_VALUE - zmin) / span) - 0.0001), colors.no_data],
        [((FAILURE_VALUE - zmin) / span), colors.failure],
        [max(0.0, ((0 - zmin) / span) - 0.0001), colors.failure],
    ]

    for stop in colors.latency_scale:
        scale.append([((stop.latency_ms - zmin) / span), stop.color])

    scale.sort(key=lambda item: float(item[0]))
    return scale


def build_recent_results(app_config: AppConfig):
    rows = fetch_latest_results(app_config.global_config.database_path, limit=8)
    if not rows:
        return html.Div("No probe results yet.", className="recent-title")

    items = []
    for row in rows:
        status = "success" if row["success"] else "failed"
        latency = f"{row['latency_ms']} ms" if row["latency_ms"] is not None else "n/a"
        error = row["error"] or ""
        detail = f"{row['started_at_iso']} · {row['protocol']} · {row['model']} · {status} · {latency}"
        if error:
            detail = f"{detail} · {error[:160]}"
        items.append(
            html.Div(
                [
                    html.Strong(row["target_title"]),
                    html.Span(detail),
                ],
                className="recent-item",
            )
        )

    return html.Div(
        [
            html.Div("Recent probes", className="recent-title"),
            html.Div(items, className="recent-grid"),
        ]
    )


if __name__ == "__main__":
    host = os.getenv("INSPECT_HOST", "0.0.0.0")
    port = int(os.getenv("INSPECT_PORT", "8050"))
    debug = os.getenv("INSPECT_DEBUG", "1").lower() in {"1", "true", "yes", "on"}
    # 注意：修改代码后请手动在终端中重启服务以应用变更
    app.run(host=host, port=port, debug=debug, use_reloader=False)
