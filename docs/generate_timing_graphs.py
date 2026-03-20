"""
Generate timing/performance graphs for ModbusX documentation.
Produces 4 PNG figures in the docs/ directory.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Resolve output directory relative to this script
DOCS_DIR = os.path.dirname(os.path.abspath(__file__))

# Consistent color palette
COLOR_TEAL = "#2a9d8f"
COLOR_BLUE = "#264653"
COLOR_RED = "#e76f51"
COLOR_CORAL = "#e76f51"
COLOR_GREEN = "#2a9d8f"
COLOR_GRAY = "#adb5bd"
COLOR_DARK_GRAY = "#6c757d"
COLOR_BAR_STARTUP = "#264653"
COLOR_LINE_LATENCY = "#e76f51"

STYLE = "seaborn-v0_8-whitegrid"
DPI = 150


def graph_multi_slave_latency():
    """Graph 1: Multi-Slave Load Test - dual-axis line+bar chart."""
    plt.style.use(STYLE)
    fig, ax1 = plt.subplots(figsize=(10, 6))

    slave_counts = [5, 10, 20, 50, 100]
    startup_times = [0.5, 0.8, 1.5, 3, 8]
    avg_latencies = [3.5, 5, 8.5, 14, 29]

    x = np.arange(len(slave_counts))
    bar_width = 0.5

    # Bar chart on left axis
    bars = ax1.bar(x, startup_times, bar_width, color=COLOR_BAR_STARTUP,
                   alpha=0.85, label="Server Startup Time (s)", zorder=3)
    ax1.set_xlabel("Slave Count", fontsize=12, fontweight="medium")
    ax1.set_ylabel("Server Startup Time (s)", fontsize=12, color=COLOR_BAR_STARTUP,
                   fontweight="medium")
    ax1.set_xticks(x)
    ax1.set_xticklabels([str(s) for s in slave_counts], fontsize=11)
    ax1.tick_params(axis="y", labelcolor=COLOR_BAR_STARTUP)

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2, height + 0.15,
                 f"{height:.1f}s", ha="center", va="bottom", fontsize=9,
                 color=COLOR_BAR_STARTUP, fontweight="bold")

    # Line chart on right axis
    ax2 = ax1.twinx()
    line = ax2.plot(x, avg_latencies, color=COLOR_LINE_LATENCY, marker="o",
                    linewidth=2.5, markersize=8, label="Avg Response Latency (ms)",
                    zorder=4)
    ax2.set_ylabel("Avg Response Latency (ms)", fontsize=12,
                   color=COLOR_LINE_LATENCY, fontweight="medium")
    ax2.tick_params(axis="y", labelcolor=COLOR_LINE_LATENCY)

    # Add value labels on line points
    for i, val in enumerate(avg_latencies):
        ax2.annotate(f"{val} ms", (x[i], val), textcoords="offset points",
                     xytext=(0, 12), ha="center", fontsize=9,
                     color=COLOR_LINE_LATENCY, fontweight="bold")

    # NFR02 threshold line
    ax2.axhline(y=100, color="red", linestyle="--", linewidth=1.5, alpha=0.7,
                zorder=2)
    ax2.text(x[-1], 102, "NFR02 Threshold (100ms)", ha="right", va="bottom",
             fontsize=10, color="red", fontstyle="italic")
    ax2.set_ylim(0, 120)

    # Title removed — use report figure caption instead

    # Combined legend
    lines_labels_1 = ax1.get_legend_handles_labels()
    lines_labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_labels_1[0] + lines_labels_2[0],
               lines_labels_1[1] + lines_labels_2[1],
               loc="upper left", fontsize=10, framealpha=0.9)

    fig.tight_layout()
    path = os.path.join(DOCS_DIR, "graph_multi_slave_latency.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def graph_optimization_before_after():
    """Graph 2: Before/After QAbstractTableModel Migration - horizontal bar chart."""
    plt.style.use(STYLE)
    fig, ax = plt.subplots(figsize=(10, 5))

    metrics = [
        "Group Selection Time (ms)",
        "Peak Memory - Table (MB)",
        "Value Edit to Sync (ms)",
    ]
    before_vals = [7500, 18, 500]
    after_vals = [142, 2, 10]

    y = np.arange(len(metrics))
    bar_height = 0.35

    bars_before = ax.barh(y + bar_height / 2, before_vals, bar_height,
                          color=COLOR_CORAL, alpha=0.85,
                          label="Before (QStandardItemModel)", zorder=3)
    bars_after = ax.barh(y - bar_height / 2, after_vals, bar_height,
                         color=COLOR_GREEN, alpha=0.85,
                         label="After (QAbstractTableModel)", zorder=3)

    ax.set_xscale("log")
    ax.set_xlabel("Value (log scale)", fontsize=12, fontweight="medium")
    ax.set_yticks(y)
    ax.set_yticklabels(metrics, fontsize=11)
    ax.invert_yaxis()

    # Value labels
    for bar, val in zip(bars_before, before_vals):
        ax.text(val * 1.15, bar.get_y() + bar.get_height() / 2,
                f"{val:,}", va="center", ha="left", fontsize=10,
                color=COLOR_CORAL, fontweight="bold")
    for bar, val in zip(bars_after, after_vals):
        ax.text(val * 1.15, bar.get_y() + bar.get_height() / 2,
                f"{val:,}", va="center", ha="left", fontsize=10,
                color=COLOR_GREEN, fontweight="bold")

    # Title removed — use report figure caption instead
    ax.legend(loc="lower right", fontsize=10, framealpha=0.9)

    fig.tight_layout()
    path = os.path.join(DOCS_DIR, "graph_optimization_before_after.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def graph_task_completion():
    """Graph 3: Task Completion Times with Targets - grouped bar chart."""
    plt.style.use(STYLE)
    fig, ax = plt.subplots(figsize=(10, 6))

    tasks = [
        "Launch to\nServer",
        "Add Slave +\nRegisters",
        "Set Value\n(Decimal)",
        "Set Value\n(Hex)",
        "Find Log\nEntry",
    ]
    targets = [60, 90, 10, 15, 30]
    means = [38, 62, 6, 11, 24]
    # Ranges as (min, max)
    ranges = [(28, 52), (45, 85), (4, 9), (8, 14), (12, 41)]

    # Compute error bars: lower = mean - min, upper = max - mean
    err_lower = [m - r[0] for m, r in zip(means, ranges)]
    err_upper = [r[1] - m for m, r in zip(means, ranges)]

    x = np.arange(len(tasks))
    bar_width = 0.32

    bars_target = ax.bar(x - bar_width / 2, targets, bar_width,
                         color=COLOR_GRAY, alpha=0.8, label="Target",
                         zorder=3)
    bars_observed = ax.bar(x + bar_width / 2, means, bar_width,
                           color=COLOR_TEAL, alpha=0.9, label="Observed Mean",
                           yerr=[err_lower, err_upper],
                           error_kw=dict(lw=1.5, capsize=4, capthick=1.2,
                                         color=COLOR_BLUE),
                           zorder=3)

    # Value labels on target bars
    for bar, val in zip(bars_target, targets):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 1.5,
                f"{val}s", ha="center", va="bottom", fontsize=9,
                color=COLOR_DARK_GRAY, fontweight="bold")

    # Value labels on observed bars
    for bar, val in zip(bars_observed, means):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 1.5,
                f"{val}s", ha="center", va="bottom", fontsize=9,
                color=COLOR_TEAL, fontweight="bold")

    ax.set_xlabel("Task", fontsize=12, fontweight="medium")
    ax.set_ylabel("Time (seconds)", fontsize=12, fontweight="medium")
    ax.set_xticks(x)
    ax.set_xticklabels(tasks, fontsize=10)
    # Title removed — use report figure caption instead
    ax.legend(fontsize=10, framealpha=0.9)

    fig.tight_layout()
    path = os.path.join(DOCS_DIR, "graph_task_completion.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def graph_tool_comparison():
    """Graph 4: Comparative Workflow Timing - horizontal bar chart."""
    plt.style.use(STYLE)
    fig, ax = plt.subplots(figsize=(10, 5))

    tools = ["Modbus Slave\nEmulator", "ModScan32", "ModbusX"]
    times = [210, 190, 141]
    colors = [COLOR_GRAY, COLOR_GRAY, COLOR_TEAL]

    baseline = 141  # ModbusX time

    bars = ax.barh(tools, times, color=colors, alpha=0.88, height=0.5, zorder=3)

    # Value labels and percentage labels
    for bar, t, tool in zip(bars, times, tools):
        # Value label
        ax.text(t + 2, bar.get_y() + bar.get_height() / 2,
                f"{t}s", va="center", ha="left", fontsize=11, fontweight="bold",
                color=COLOR_BLUE)
        # Percentage label for competitors
        if t > baseline:
            pct = ((t - baseline) / baseline) * 100
            ax.text(t / 2, bar.get_y() + bar.get_height() / 2,
                    f"+{pct:.0f}%", va="center", ha="center", fontsize=12,
                    fontweight="bold", color="white")

    ax.set_xlabel("Time (seconds)", fontsize=12, fontweight="medium")
    # Title removed — use report figure caption instead
    ax.set_xlim(0, max(times) * 1.15)

    fig.tight_layout()
    path = os.path.join(DOCS_DIR, "graph_tool_comparison.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def graph_memory_allocation_breakdown():
    """Graph 5: Memory allocation breakdown - QStandardItemModel vs QAbstractTableModel.
    Supports Section 7.9.1 with a stacked bar showing where memory goes."""
    plt.style.use(STYLE)
    fig, ax = plt.subplots(figsize=(10, 6))

    categories = ["100\nregisters", "500\nregisters", "1,000\nregisters", "5,000\nregisters", "10,000\nregisters"]
    register_counts = [100, 500, 1000, 5000, 10000]

    # QStandardItemModel: 6 QStandardItem objects per row, ~250 bytes each = 1500 bytes/row
    # Plus RegisterEntry objects ~200 bytes each
    qsi_item_mem = [n * 6 * 250 / 1e6 for n in register_counts]     # QStandardItem wrappers (MB)
    qsi_entry_mem = [n * 200 / 1e6 for n in register_counts]        # RegisterEntry objects (MB)
    qsi_qt_overhead = [n * 50 / 1e6 for n in register_counts]       # Qt internal buffers (MB)

    # QAbstractTableModel: NO QStandardItem objects, only RegisterEntry + minimal overhead
    qat_entry_mem = [n * 200 / 1e6 for n in register_counts]        # RegisterEntry objects (MB)
    qat_overhead = [0.05 for _ in register_counts]                   # Minimal model overhead (MB)

    x = np.arange(len(categories))
    bar_width = 0.35

    # QStandardItemModel - stacked bars (left)
    b1 = ax.bar(x - bar_width / 2, qsi_item_mem, bar_width,
                color="#e76f51", alpha=0.9, label="Before: QStandardItem wrappers", zorder=3)
    b2 = ax.bar(x - bar_width / 2, qsi_entry_mem, bar_width,
                bottom=qsi_item_mem, color="#f4a261", alpha=0.9,
                label="Before: RegisterEntry objects", zorder=3)
    b3 = ax.bar(x - bar_width / 2, qsi_qt_overhead, bar_width,
                bottom=[a + b for a, b in zip(qsi_item_mem, qsi_entry_mem)],
                color="#e9c46a", alpha=0.9, label="Before: Qt rendering buffers", zorder=3)

    # QAbstractTableModel - stacked bars (right)
    b4 = ax.bar(x + bar_width / 2, qat_entry_mem, bar_width,
                color="#2a9d8f", alpha=0.9, label="After: RegisterEntry (shared)", zorder=3)
    b5 = ax.bar(x + bar_width / 2, qat_overhead, bar_width,
                bottom=qat_entry_mem, color="#264653", alpha=0.9,
                label="After: Model overhead", zorder=3)

    # Total labels
    for i, n in enumerate(register_counts):
        total_qsi = qsi_item_mem[i] + qsi_entry_mem[i] + qsi_qt_overhead[i]
        total_qat = qat_entry_mem[i] + qat_overhead[i]
        ax.text(x[i] - bar_width / 2, total_qsi + 0.3,
                f"{total_qsi:.1f} MB", ha="center", va="bottom", fontsize=8,
                fontweight="bold", color="#e76f51")
        if total_qat >= 0.15:
            ax.text(x[i] + bar_width / 2, total_qat + 0.3,
                    f"{total_qat:.1f} MB", ha="center", va="bottom", fontsize=8,
                    fontweight="bold", color="#2a9d8f")

    # Add subtitle clarifying left/right bar groupings
    ax.text(0.5, -0.12,
            "Left bars = QStandardItemModel (Before)    |    Right bars = QAbstractTableModel (After)",
            transform=ax.transAxes, ha="center", va="top", fontsize=9,
            fontstyle="italic", color="#555555")

    ax.set_xlabel("Register Group Size", fontsize=12, fontweight="medium")
    ax.set_ylabel("Memory Usage (MB)", fontsize=12, fontweight="medium")
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=10)
    # Title removed — use report figure caption instead
    ax.legend(fontsize=9, loc="upper left", framealpha=0.9, ncol=2)

    fig.tight_layout()
    path = os.path.join(DOCS_DIR, "graph_memory_breakdown.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def graph_selection_time_scaling():
    """Graph 6: Selection time scaling curve - how group selection time
    grows with register count for both models. Supports Section 7.9.1-7.9.3."""
    plt.style.use(STYLE)
    fig, ax = plt.subplots(figsize=(10, 6))

    register_counts = [100, 500, 1000, 2000, 5000, 7500, 10000]

    # QStandardItemModel: O(6n) allocations, roughly linear scaling
    # Based on report data: 10,000 registers = 5-10s (use 7.5s midpoint)
    # Linear extrapolation: time ≈ 0.00075 * n seconds * 1000 for ms
    qsi_times = [n * 0.75 for n in register_counts]  # ms

    # QAbstractTableModel: O(n) list comprehension + beginResetModel/endResetModel
    # Based on report: 10,000 registers = 142ms mean (23ms std dev)
    # Much flatter curve: time ≈ 0.0142 * n ms
    qat_times = [max(5, n * 0.0142) for n in register_counts]  # ms

    ax.plot(register_counts, qsi_times, color=COLOR_CORAL, marker="s",
            linewidth=2.5, markersize=8, label="QStandardItemModel (O(6n) allocations)",
            zorder=4)
    ax.plot(register_counts, qat_times, color=COLOR_TEAL, marker="o",
            linewidth=2.5, markersize=8, label="QAbstractTableModel (O(n) filter only)",
            zorder=4)

    # Shade the "acceptable" zone (< 200ms)
    ax.axhspan(0, 200, alpha=0.08, color="green", zorder=1)
    ax.axhline(y=200, color="green", linestyle="--", linewidth=1.2, alpha=0.6, zorder=2)
    ax.text(register_counts[-1], 220, "NFR19 Target (< 200ms)", ha="right",
            fontsize=10, color="green", fontstyle="italic")

    # Annotate key data points from report
    ax.annotate("5-10s freeze\n(report observed)", xy=(10000, 7500),
                xytext=(7000, 6000), fontsize=9, color=COLOR_CORAL,
                arrowprops=dict(arrowstyle="->", color=COLOR_CORAL, lw=1.5),
                fontweight="bold")
    ax.annotate("142ms mean\n(23ms std dev)", xy=(10000, 142),
                xytext=(7000, 1200), fontsize=9, color=COLOR_TEAL,
                arrowprops=dict(arrowstyle="->", color=COLOR_TEAL, lw=1.5),
                fontweight="bold")

    ax.set_xlabel("Number of Registers in Group", fontsize=12, fontweight="medium")
    ax.set_ylabel("Group Selection Time (ms)", fontsize=12, fontweight="medium")
    # Title removed — use report figure caption instead
    ax.legend(fontsize=10, loc="upper left", framealpha=0.9)
    ax.set_xlim(0, 10500)
    ax.set_ylim(0, 8500)

    # Format y-axis with comma separators
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    fig.tight_layout()
    path = os.path.join(DOCS_DIR, "graph_selection_time_scaling.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def graph_rendering_strategy_comparison():
    """Graph 7: Visualise how QStandardItemModel vs QAbstractTableModel
    differ in object creation and rendering work per group selection."""
    plt.style.use(STYLE)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    register_counts = [100, 500, 1000, 2000, 5000, 10000]
    visible_rows = 30  # Typical visible rows on a 1080p display
    columns = 6        # Register Type, Address, Alias, Value, Type, Comment

    # --- Left panel: Objects created at population time ---
    qsi_objects = [n * columns for n in register_counts]          # 6 QStandardItems per row
    qat_objects = [0 for _ in register_counts]                     # Zero — no item objects created

    ax1.bar([i - 0.2 for i in range(len(register_counts))],
            qsi_objects, width=0.35, color=COLOR_CORAL, alpha=0.9,
            label="QStandardItemModel")
    ax1.bar([i + 0.2 for i in range(len(register_counts))],
            qat_objects, width=0.35, color=COLOR_TEAL, alpha=0.9,
            label="QAbstractTableModel")

    # Value labels on QStandardItemModel bars
    for i, val in enumerate(qsi_objects):
        ax1.text(i - 0.2, val + 500, f"{val:,}", ha="center", va="bottom",
                 fontsize=8, fontweight="bold", color=COLOR_CORAL)

    # "0" labels on QAbstractTableModel bars
    for i in range(len(register_counts)):
        ax1.text(i + 0.2, 200, "0", ha="center", va="bottom",
                 fontsize=9, fontweight="bold", color=COLOR_TEAL)

    ax1.set_xticks(range(len(register_counts)))
    ax1.set_xticklabels([f"{n:,}" for n in register_counts], fontsize=9)
    ax1.set_xlabel("Total Registers in Group", fontsize=11, fontweight="medium")
    ax1.set_ylabel("Objects Created at Population Time", fontsize=11, fontweight="medium")
    ax1.legend(fontsize=9, loc="upper left", framealpha=0.9)
    ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    # --- Right panel: data() calls per frame (rendering work) ---
    qsi_calls = [n * columns for n in register_counts]            # All rows pre-rendered
    qat_calls = [visible_rows * columns for _ in register_counts]  # Only visible rows

    ax2.plot(register_counts, qsi_calls, color=COLOR_CORAL, marker="s",
             linewidth=2.5, markersize=8,
             label=f"QStandardItemModel\n(all {columns} cols × n rows)", zorder=4)
    ax2.plot(register_counts, qat_calls, color=COLOR_TEAL, marker="o",
             linewidth=2.5, markersize=8,
             label=f"QAbstractTableModel\n({columns} cols × {visible_rows} visible rows)", zorder=4)

    # Shade the constant region
    ax2.fill_between(register_counts, 0, qat_calls, alpha=0.1, color=COLOR_TEAL)

    # Annotate the constant line
    ax2.annotate(f"Constant: {visible_rows * columns} calls\n(viewport-driven)",
                 xy=(7500, visible_rows * columns),
                 xytext=(5500, 12000), fontsize=9, color=COLOR_TEAL,
                 arrowprops=dict(arrowstyle="->", color=COLOR_TEAL, lw=1.5),
                 fontweight="bold")

    # Annotate the linear line
    ax2.annotate(f"Linear: {10000 * columns:,} calls\n(all rows materialised)",
                 xy=(10000, 10000 * columns),
                 xytext=(6000, 45000), fontsize=9, color=COLOR_CORAL,
                 arrowprops=dict(arrowstyle="->", color=COLOR_CORAL, lw=1.5),
                 fontweight="bold")

    ax2.set_xlabel("Total Registers in Group", fontsize=11, fontweight="medium")
    ax2.set_ylabel("Cells Rendered per Group Selection", fontsize=11, fontweight="medium")
    ax2.legend(fontsize=9, loc="upper left", framealpha=0.9)
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax2.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    fig.tight_layout(w_pad=3)
    path = os.path.join(DOCS_DIR, "graph_rendering_strategy.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


if __name__ == "__main__":
    print("Generating timing/performance graphs...")
    graph_multi_slave_latency()
    graph_optimization_before_after()
    graph_task_completion()
    graph_tool_comparison()
    graph_memory_allocation_breakdown()
    graph_selection_time_scaling()
    graph_rendering_strategy_comparison()
    print("All graphs generated successfully in docs/")
