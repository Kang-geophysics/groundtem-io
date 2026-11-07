# groundtem-io

Unofficial Python reader and plotting utilities for GroundTEM time-domain electromagnetic (TDEM) data files:

- **`.stb` binary stack files** (`read_stb`, `StbFile`) — extracts processed gate center times, GPS coordinates, and all individual Low-Moment (LM) and High-Moment (HM) stack records and instrument-reported relative standard deviations.
- **`.stn` station metadata files** (`read_stn`) — parses station/line numbers and GPS coordinates.
- **Survey directories** (`read_sounding_dir`, `read_survey`) — aggregates an entire GroundTEM survey directory into a `pandas.DataFrame` with automatic local metric coordinates (`x_m`, `y_m`) and cumulative profile distance (`dist_m`).
- **`.sts` survey protocol files** (`read_protocol`, `summarize_protocols`, `Protocol`) — parses loop geometry, turn-off ramp duration, current, waveform timings, gate tables, and effective dipole moments.
- **Decay curve & SNR plotting** (`plot_decay`, `plot_station`, `sem`) — visualizes LM/HM transient decay curves, raw stack scatter, SEM noise floor, and gate-by-gate Signal-to-Noise Ratio (SNR).

> **Disclaimer:** This is an independent, unofficial open-source library for reading GroundTEM data files for scientific and interoperability purposes. It is not affiliated with, endorsed by, or sponsored by ABEM or Guideline Geo.

---

## Installation

Install directly from PyPI using `pip` or `uv`:

```bash
pip install groundtem-io
```

```bash
uv add groundtem-io
```

For local development (editable install):

```bash
uv venv
uv pip install -e .
```

---

## Quick Start & Visual Examples

### 1. Single-Station Inspection (`read_stb`, `read_stn`, `plot_station`)

```python
import matplotlib.pyplot as plt
from groundtem_io import read_stb, read_stn, plot_station

# Read station metadata (.stn)
stn = read_stn("path/to/station.stn")
print(stn["StationNo"], stn["Latitude"], stn["Longitude"])

# Read stacked LM / HM decay records (.stb)
stb = read_stb("path/to/sounding.stb")
print("LM gate times (s):", stb.gate_times["LM"])
print("LM stacks shape (n_stacks, n_gates):", stb.data("LM").shape)
print("HM stacks shape (n_stacks, n_gates):", stb.data("HM").shape)

# Plot LM & HM decay curves (with individual stacks) and SNR
fig, axs = plot_station(stb, snr_min=3.0, stacks=True)
plt.show()
```

![Single Station Decay and SNR Plot](https://raw.githubusercontent.com/Kang-geophysics/groundtem-io/main/docs/images/station_plot.png)

#### How to Interpret the `plot_station` / `plot_decay` Figures

- **Left Panel — Transient Decay Curves ($\log\text{–}\log$)**
  - **Solid lines with filled circles (`LM mean`, `HM mean`)**: Mean transient decay response ($|\partial B / \partial t| \cdot I \cdot N_{\text{tx}}$ in $\text{V/m}^2$) averaged across all saved stacks, plotted with $\pm 1\text{ SEM}$ vertical error bars.
  - **Open (unfilled) circles**: Late-time gates where the mean signal reverses sign (negative values plotted at their absolute magnitude $|-d|$ on the logarithmic axis), indicating noise dominance or sign reversal.
  - **Translucent dots (`stacks=True`)**: Individual raw stack realizations stored in the `.stb` file (subsampled by `stack_stride`), illustrating stack-to-stack repeatability and ambient electromagnetic noise scatter.
  - **Colored dashed lines (`LM SEM (noise)`, `HM SEM (noise)`)**: Gate-by-gate **Standard Error of the Mean ($\text{SEM}$)**, representing the effective noise floor for each moment:
    $$\text{SEM} = \max\!\left(\text{SEM}_{\text{emp}},\, \text{SEM}_{\text{rep}}\right)$$
    where $\text{SEM}_{\text{emp}} = s / \sqrt{N}$ is the empirical standard error across $N$ stacks and $\text{SEM}_{\text{rep}}$ is the propagated instrument-reported stack uncertainty. Where the solid decay curve meets the dashed SEM line, the signal has reached the noise floor.
- **Right Panel — Signal-to-Noise Ratio ($\text{SNR} = \text{mean} / \text{SEM}$)**
  - **Blue / Red curves (`LM`, `HM`)**: Gate-by-gate SNR plotted on a symmetric log (`symlog`) vertical scale so both high-SNR early gates and negative/near-zero late gates are clearly visible.
  - **Black dotted horizontal line (`SNR = 3 threshold`)**: Minimum quality threshold controlled by `snr_min` (default `3.0`).
    - **Above the dotted line ($\text{SNR} \ge 3$)**: Reliable data gates where the mean signal amplitude is at least $3\times$ the standard error.
    - **Below the dotted line ($\text{SNR} < 3$)**: Noise-dominated late-time gates that should typically be culled (masked) prior to 1D/2D geophysical inversion.

---

### 2. Multi-Station Survey Loading & Grid Plotting (`read_survey`, `plot_decay`)

`read_survey` scans a GroundTEM survey folder (automatically detecting a `Data/` subfolder if present) and returns a `pandas.DataFrame` with one row per sounding:

```python
import matplotlib.pyplot as plt
from groundtem_io import read_survey, plot_decay

# Load all soundings under the survey directory
df = read_survey("path/to/survey_folder")
print(df[["sounding", "station", "line", "n_lm", "n_hm", "dist_m"]].head())

# Plot a 2x3 grid of the first 6 stations
fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharex=True, sharey=True)
for idx, ax in enumerate(axes.flat):
    row = df.iloc[idx]
    plot_decay(ax, row, stacks=True)
    ax.set_title(f"Stn {row['station']} ({row['sounding']})\nLM={row['n_lm']}, HM={row['n_hm']}", fontsize=9)
    ax.grid(True, which="both", ls=":", alpha=0.4)
    if idx == 0:
        ax.legend(fontsize=8)

fig.tight_layout()
plt.show()
```

![Survey Overview Grid Plot](https://raw.githubusercontent.com/Kang-geophysics/groundtem-io/main/docs/images/survey_overview.png)

---

### 3. Reading `.sts` Survey Protocol Files (`read_protocol`, `summarize_protocols`)

```python
from groundtem_io import read_protocol, summarize_protocols

proto = read_protocol("path/to/Protocol.sts")
print("Protocol name:", proto.name)
print("Tx loop size (m):", proto.tx_size, "Turns:", proto.tx_turns)
print("Rx effective area (m^2):", proto.rx_area)
print("LM dipole moment (A*m^2):", proto.dipole_moment("LM"))
print("HM dipole moment (A*m^2):", proto.dipole_moment("HM"))

# Or summarize multiple .sts files into a DataFrame
summary_df = summarize_protocols("path/to/survey_folder")
print(summary_df)
```

---

## API Overview

| Function / Class | Description |
| :--- | :--- |
| `read_stb(path)` | Parse a `.stb` file and return an `StbFile` object (`gate_times`, `stacks`, `header`, `.data(moment)`, `.rel_std(moment)`, `.summary(moment)`). |
| `read_stn(path)` | Parse a `.stn` station file into a dictionary (`StationNo`, `LineNo`, `Latitude`, `Longitude`, etc.). |
| `read_sounding_dir(dir)` | Read a single sounding folder containing `*.stn` and `*.stb` into a summary dictionary. |
| `read_survey(root, pattern="*/*")` | Read all sounding directories under `root` (or `root/Data`) into a `pandas.DataFrame` with `x_m`, `y_m`, and `dist_m`. |
| `read_protocol(path)` | Parse a `.sts` XML protocol file into a `Protocol` dataclass (`tx_size`, `tx_turns`, `rx_area`, `lm`, `hm`, `gates`, `.dipole_moment()`). |
| `summarize_protocols(paths)` | Summarize all `.sts` protocol files in a directory or list into a `pandas.DataFrame`. |
| `plot_decay(ax, source, ...)` | Plot LM and HM decay curves, SEM noise floor, and optional raw stacks on a Matplotlib `Axes`. |
| `plot_station(source, snr_min=3.0, ...)` | Create a two-panel figure showing LM/HM decay curves (left) and gate-by-gate SNR with threshold line (right). |
| `sem(record, moment)` | Compute $\max(\text{SEM}_{\text{emp}}, \text{SEM}_{\text{rep}})$ for a station row dictionary or `pandas.Series`. |

---

## Acknowledgments

Developed with the assistance of **Google Antigravity**.

---

## License

Released under the [MIT License](LICENSE).
