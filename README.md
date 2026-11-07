# groundtem-io

Unofficial Python reader and plotting utilities for GroundTEM time-domain electromagnetic (TDEM) data files:
- `.stb` binary stack files (`read_stb`)
- `.stn` station metadata files (`read_stn`)
- `.sts` survey protocol files (`read_protocol`)
- LM / HM decay curve and SNR plotting utilities (`plot_decay`, `plot_station`)

> **Disclaimer:** This is an independent, unofficial open-source library for reading GroundTEM data files for scientific and interoperability purposes. It is not affiliated with, endorsed by, or sponsored by ABEM or Guideline Geo.

---

## Installation

```bash
pip install groundtem-io
```

Or for local development with `uv`:

```bash
uv venv
uv pip install -e .
```

---

## Quick Start

### 1. Read `.stb` and `.stn` files directly

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
fig, axs = plot_station(stb)
plt.show()
```

### 2. Read an entire survey directory into a `pandas.DataFrame`

```python
from groundtem_io import read_survey, plot_decay
import matplotlib.pyplot as plt

df = read_survey("path/to/survey_folder")
print(df[["sounding", "station", "n_lm", "n_hm", "dist_m"]])

# Plot first station
fig, ax = plt.subplots(figsize=(5, 4))
plot_decay(ax, df.iloc[0], stacks=True)
ax.legend()
plt.show()
```

### 3. Read `.sts` protocol file

```python
from groundtem_io import read_protocol

proto = read_protocol("path/to/Protocol.sts")
print("Tx loop size (m):", proto.tx_size)
print("LM dipole moment (A*m^2):", proto.dipole_moment("LM"))
print("HM dipole moment (A*m^2):", proto.dipole_moment("HM"))
```

---

## Acknowledgments

Developed with the assistance of **Google Antigravity**.

---

## License

Released under the [MIT License](LICENSE).
