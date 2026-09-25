"""Static charts (PNG bytes) for the model development document.

Rendered with matplotlib's non-interactive Agg backend. Styling follows the
app's charts: thin 2px lines, a recessive hairline grid, a legend whenever
there are two or more series, and the same validated Train/Test/OOT colours.
"""
from __future__ import annotations

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SAMPLE_COLORS = {"train": "#2a78d6", "test": "#eb6834", "oot": "#1baf7a"}
SAMPLE_LABELS = {"train": "Train", "test": "Test", "oot": "OOT"}
ACCENT = "#2a78d6"
MUTED = "#b9b8bd"
TEXT = "#3d3b42"
GRID = "#e8e7ea"


def _figure(width: float = 6.4, height: float = 3.0):
    fig, ax = plt.subplots(figsize=(width, height), dpi=160)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=TEXT, labelsize=7.5, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def _png(fig) -> bytes:
    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png", facecolor="white")
    plt.close(fig)
    return buffer.getvalue()


def _legend(ax) -> None:
    ax.legend(frameon=False, fontsize=7.5, labelcolor=TEXT, loc="best")


def iv_chart(ivs: list[tuple[str, float, bool]], min_iv: float | None) -> bytes:
    """Horizontal IV bars, strongest at the top; selected variables in the
    accent colour, the rest muted, with the selection threshold marked."""
    ivs = sorted(ivs, key=lambda r: r[1])
    fig, ax = _figure(6.4, max(1.8, 0.24 * len(ivs) + 0.7))
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.barh(
        [name for name, _, _ in ivs],
        [iv for _, iv, _ in ivs],
        color=[ACCENT if selected else MUTED for _, _, selected in ivs],
        height=0.6,
    )
    if min_iv is not None:
        ax.axvline(min_iv, color=TEXT, linewidth=0.8, linestyle=(0, (3, 3)))
        ax.text(min_iv, len(ivs) - 0.4, f" min IV {min_iv}", fontsize=7, color=TEXT, va="bottom")
    ax.set_xlabel("Information value", fontsize=8, color=TEXT)
    return _png(fig)


def bad_rate_by_bin_chart(bins: list[dict[str, Any]]) -> bytes:
    """Bad rate per bin for one characteristic, in bin order."""
    fig, ax = _figure(6.4, 2.2)
    labels = [str(b["label"]) for b in bins]
    ax.bar(range(len(bins)), [b["bad_rate_pct"] for b in bins], color=ACCENT, width=0.6)
    ax.set_xticks(range(len(bins)), labels, rotation=30 if len(labels) > 4 else 0, ha="right" if len(labels) > 4 else "center")
    ax.set_ylabel("Bad rate %", fontsize=8, color=TEXT)
    return _png(fig)


def roc_chart(samples: dict[str, list[dict[str, float]]]) -> bytes:
    fig, ax = _figure(3.6, 3.4)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.plot([0, 1], [0, 1], color=MUTED, linewidth=0.8)
    for key, points in samples.items():
        if points:
            ax.plot([p["fpr"] for p in points], [p["tpr"] for p in points], color=SAMPLE_COLORS[key], linewidth=2, label=SAMPLE_LABELS[key])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("False positive rate", fontsize=8, color=TEXT)
    ax.set_ylabel("True positive rate", fontsize=8, color=TEXT)
    _legend(ax)
    return _png(fig)


def bucket_lines_chart(labels: list[str], samples: dict[str, list[float | None]], y_label: str) -> bytes:
    """One line per sample over shared categorical buckets (calibration
    or score distribution); None values leave a gap."""
    fig, ax = _figure(6.4, 2.8)
    x = list(range(len(labels)))
    for key, values in samples.items():
        ax.plot(
            x,
            [float("nan") if v is None else v for v in values],
            color=SAMPLE_COLORS[key],
            linewidth=2,
            marker="o",
            markersize=3,
            label=SAMPLE_LABELS[key],
        )
    step = 2 if len(labels) > 12 else 1
    ax.set_xticks(x[::step], labels[::step], rotation=30, ha="right")
    ax.set_ylabel(y_label, fontsize=8, color=TEXT)
    ax.set_ylim(bottom=0)
    if len(samples) > 1:
        _legend(ax)
    return _png(fig)
