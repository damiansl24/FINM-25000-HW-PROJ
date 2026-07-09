"""Chart generation: equity curve, drawdown, PCA explained variance, signal overlay."""
import matplotlib

matplotlib.use("Agg")  # headless-safe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config


def plot_equity(ticker, bt: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(bt.index, bt["ml_equity"], label="ML Signal", linewidth=1.8)
    ax.plot(bt.index, bt["bh_equity"], label="Buy & Hold", linewidth=1.8, alpha=0.8)
    ax.axhline(config.INITIAL_CAPITAL, color="gray", linestyle="--", linewidth=0.8)
    ax.set_title(f"Equity Curve — {ticker} (out-of-sample)")
    ax.set_ylabel("Portfolio value ($)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return _save(fig, f"equity_curve_{ticker}.png")


def plot_drawdown(ticker, bt: pd.DataFrame):
    dd = bt["ml_equity"] / bt["ml_equity"].cummax() - 1.0
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.fill_between(dd.index, dd.values, 0, color="crimson", alpha=0.4)
    ax.plot(dd.index, dd.values, color="crimson", linewidth=1.0)
    ax.set_title(f"ML Strategy Drawdown — {ticker}")
    ax.set_ylabel("Drawdown")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return _save(fig, f"drawdown_{ticker}.png")


def plot_pca_variance(ticker, pca):
    ratios = pca.explained_variance_ratio_
    cum = np.cumsum(ratios)
    x = np.arange(1, len(ratios) + 1)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.bar(x, ratios, alpha=0.6, label="Individual")
    ax.plot(x, cum, marker="o", color="black", label="Cumulative")
    ax.axhline(config.PCA_VARIANCE_TARGET, color="green", linestyle="--",
               label=f"{config.PCA_VARIANCE_TARGET:.0%} target")
    ax.set_title(f"PCA Explained Variance — {ticker}")
    ax.set_xlabel("Principal component")
    ax.set_ylabel("Explained variance ratio")
    ax.set_xticks(x)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return _save(fig, f"pca_variance_{ticker}.png")


def plot_signal(ticker, bt: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(bt.index, bt["price"], color="steelblue", linewidth=1.2, label="Close")
    longs = bt[bt["position"] == 1]
    ax.scatter(longs.index, longs["price"], s=8, color="green", alpha=0.5, label="Long (in market)")
    ax.set_title(f"Price with ML Long Signal — {ticker}")
    ax.set_ylabel("Price ($)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return _save(fig, f"signal_{ticker}.png")


def _save(fig, filename):
    path = f"{config.CHARTS_DIR}/{filename}"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_all(ticker, bt, pca):
    paths = [
        plot_equity(ticker, bt),
        plot_drawdown(ticker, bt),
        plot_pca_variance(ticker, pca),
        plot_signal(ticker, bt),
    ]
    for p in paths:
        print(f"      saved {p}")
    return paths
