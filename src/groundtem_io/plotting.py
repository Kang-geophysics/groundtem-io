"""Plotting utilities for GroundTEM LM and HM decay curves and SNR."""

from typing import Mapping, Optional, Union

import matplotlib.pyplot as plt
import numpy as np

from .stb import StbFile

DEFAULT_COLORS = {"LM": "tab:blue", "HM": "tab:red"}


def sem(record: Mapping, moment: str) -> np.ndarray:
    """Return the larger of empirical and instrument-reported SEM for a station record."""
    return np.fmax(record[f"sem_emp_{moment}"], record[f"sem_rep_{moment}"])


def plot_decay(
    ax: plt.Axes,
    source: Union[StbFile, Mapping],
    stacks: bool = False,
    stack_stride: int = 10,
    colors: Optional[Mapping[str, str]] = None,
) -> plt.Axes:
    """Plot LM and HM decay curves and noise floor on a log-log Axes.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    source : StbFile or dict/Series
        Either an ``StbFile`` returned by ``read_stb`` or a row dict/Series returned
        by ``read_sounding_dir`` / ``read_survey``.
    stacks : bool, default False
        If True, also plot individual raw stacks as light dots.
    stack_stride : int, default 10
        Stride used when plotting raw stacks.
    colors : mapping, optional
        Custom color mapping for ``{"LM": ..., "HM": ...}``.
    """
    col = colors or DEFAULT_COLORS
    if isinstance(source, StbFile):
        polarity = -1 if (len(source.stacks["HM"]) > 0 and source.data("HM").mean(0)[:5].mean() < 0) else 1
        summaries = {m: source.summary(m, polarity=polarity) for m in ("LM", "HM") if len(source.stacks[m]) > 0}
    else:
        summaries = {
            m: {
                "t": source[f"t_{m}"],
                "d": source[f"d_{m}"],
                "sem": sem(source, m),
                "stacks": source[f"stacks_{m}"],
            }
            for m in ("LM", "HM")
            if f"d_{m}" in source
        }

    for m, info in summaries.items():
        t, d, e = info["t"], info["d"], info["sem"]
        if stacks and "stacks" in info:
            for s in info["stacks"][::stack_stride]:
                ax.loglog(t, np.abs(s), ".", color=col[m], alpha=0.12, ms=3)
        pos = d > 0
        ax.errorbar(t[pos], d[pos], e[pos], fmt="o-", color=col[m], ms=3, lw=1, label=f"{m} mean")
        if np.any(~pos):
            ax.errorbar(t[~pos], -d[~pos], e[~pos], fmt="o", mfc="none", color=col[m], ms=4)
        ax.loglog(t, e, "--", color=col[m], lw=0.8, alpha=0.7, label=f"{m} SEM (noise)")

    ax.set_xscale("log")
    ax.set_yscale("log")
    return ax


def plot_station(
    source: Union[StbFile, Mapping],
    snr_min: float = 3.0,
    stacks: bool = True,
    title: Optional[str] = None,
):
    """Plot a two-panel figure showing LM/HM decay curves (with raw stacks) and SNR."""
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    plot_decay(axs[0], source, stacks=stacks)
    if title is None:
        if isinstance(source, StbFile):
            title = source.path.name
        else:
            title = f"Station {source.get('station', '')} ({source.get('sounding', '')})"
    axs[0].set_title(title)
    axs[0].set_xlabel("time (s)")
    axs[0].set_ylabel("|dB/dt| x I x N_tx (V/m²)")
    axs[0].legend(fontsize=8)

    if isinstance(source, StbFile):
        polarity = -1 if (len(source.stacks["HM"]) > 0 and source.data("HM").mean(0)[:5].mean() < 0) else 1
        for m in ("LM", "HM"):
            if len(source.stacks[m]) == 0:
                continue
            info = source.summary(m, polarity=polarity)
            axs[1].semilogx(info["t"], info["d"] / info["sem"], "o-", color=DEFAULT_COLORS[m], ms=3, label=m)
    else:
        for m in ("LM", "HM"):
            if f"d_{m}" not in source:
                continue
            axs[1].semilogx(
                source[f"t_{m}"],
                source[f"d_{m}"] / sem(source, m),
                "o-",
                color=DEFAULT_COLORS[m],
                ms=3,
                label=m,
            )

    axs[1].axhline(snr_min, color="k", ls=":", label=f"SNR = {snr_min:g} threshold")
    axs[1].set_yscale("symlog")
    axs[1].set_title("SNR = mean / SEM")
    axs[1].set_xlabel("time (s)")
    axs[1].set_ylabel("SNR")
    axs[1].legend(fontsize=8)
    fig.tight_layout()
    return fig, axs
