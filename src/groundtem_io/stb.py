"""Parse GroundTEM ``.stb`` stack files and ``.stn`` station files.

File layout:

* ASCII header (protocol ``[Gate]``, ``[RxTxSpecs]``, ``[ProcessedGateTimes]``, ``[InstrumentInfo]`` ...)
* Binary stack records, each terminated by ``b"$" * 8``. The record type is given by byte 0
  (0 = LM, 1 = HM) and the number of processed gates by the ``uint16`` at byte 2.
  Record tail: ``uint32 stack_size`` + ``float32 data[n]`` + ``float32 rel_std_percent[n]``.
  GPS latitude / longitude are ``float64`` at byte offsets 33 / 41.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
import struct
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd

_TERMINATOR = b"$" * 8
_LAT_OFFSET, _LON_OFFSET = 33, 41


@dataclass
class StbFile:
    path: Path
    gate_times: Dict[str, np.ndarray]  # {"LM": s, "HM": s} gate centre times [s] after turn-off start
    stacks: Dict[str, pd.DataFrame]  # {"LM": DataFrame, "HM": DataFrame}, one row per saved stack
    header: Dict[str, str] = field(default_factory=dict)

    def data(self, moment: str) -> np.ndarray:
        """Return (n_stack, n_gate) array of dB/dt data for ``moment`` ('LM' or 'HM')."""
        return np.vstack(self.stacks[moment]["data"].to_list())

    def rel_std(self, moment: str) -> np.ndarray:
        """Return (n_stack, n_gate) array of per-stack relative std [%] for ``moment``."""
        return np.vstack(self.stacks[moment]["rel_std"].to_list())

    def summary(self, moment: str, polarity: Optional[int] = None) -> Dict[str, np.ndarray]:
        """Compute mean decay curve and standard error estimates for ``moment``.

        Parameters
        ----------
        moment : {"LM", "HM"}
            Transmitter moment key.
        polarity : {1, -1}, optional
            Sign multiplier applied to ``data``. If ``None``, inferred automatically
            from the sign of the first 5 early-time gates.
        """
        D_raw = self.data(moment)
        if polarity is None:
            polarity = -1 if D_raw.mean(0)[:5].mean() < 0 else 1
        D = D_raw * polarity
        S = self.rel_std(moment) / 100.0 * np.abs(D)
        n = len(D)
        sem_emp = D.std(0, ddof=1) / np.sqrt(n) if n > 1 else np.zeros(D.shape[1])
        sem_rep = np.sqrt((S**2).sum(0)) / n
        return {
            "t": self.gate_times[moment],
            "d": D.mean(0),
            "sem_emp": sem_emp,
            "sem_rep": sem_rep,
            "sem": np.fmax(sem_emp, sem_rep),
            "stacks": D,
            "polarity": polarity,
        }


def _read_header(raw: bytes):
    start = raw.find(b"[InstrumentInfo]")
    end = raw.find(b"ControllerVersion", start)
    end = raw.find(b"\n", end) + 1
    text = raw[:end].decode("latin1")
    out = {}
    for key in ("LM_DataFactor", "HM_DataFactor", "LM_GateTimeShift", "HM_GateTimeShift", "InstrumentID"):
        m = re.search(rf"{key}=(\S+)", text)
        if m:
            out[key] = m.group(1)
    times = {}
    for mom in ("LM", "HM"):
        m = re.search(rf"{mom}_ChA_CenterTime=([^\r\n]+)", text)
        times[mom] = np.array([float(x) for x in m.group(1).split(",")]) * 1e-6
    return text, end, times, out


def read_stb(path: Union[str, Path]) -> StbFile:
    """Read a ``.stb`` stack file. Truncated trailing records are dropped."""
    path = Path(path)
    raw = path.read_bytes()
    _, hdr_end, times, header = _read_header(raw)
    body = raw[hdr_end:]
    rows = {"LM": [], "HM": []}
    pos = 0
    while True:
        idx = body.find(_TERMINATOR, pos)
        if idx < 0:
            break
        rec = body[pos:idx]
        pos = idx + len(_TERMINATOR)
        for mom, code in (("LM", 0), ("HM", 1)):
            n = len(times[mom])
            full = _record_length(n)
            if len(rec) < full:
                continue
            # locate record start from the tail (the first record carries a file preamble)
            r = rec[-full:]
            if r[0] != code or struct.unpack_from("<H", r, 2)[0] != n:
                continue
            rows[mom].append(
                dict(
                    stack_size=struct.unpack_from("<I", r, full - 8 * n - 4)[0],
                    lat=struct.unpack_from("<d", r, _LAT_OFFSET)[0],
                    lon=struct.unpack_from("<d", r, _LON_OFFSET)[0],
                    data=np.frombuffer(r, "<f4", n, full - 8 * n).astype(float),
                    rel_std=np.frombuffer(r, "<f4", n, full - 4 * n).astype(float),
                )
            )
            break
    stacks = {m: pd.DataFrame(v) for m, v in rows.items()}
    return StbFile(path=path, gate_times=times, stacks=stacks, header=header)


def _record_length(n: int) -> int:
    """Record body length (without terminator): 231 fixed bytes + uint32 count + 2 float32 arrays."""
    return 235 + 8 * n


def read_stn(path: Union[str, Path]) -> dict:
    """Read a ``.stn`` station file (key=value text)."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    for k in ("LineNo", "StationNo"):
        if k in out:
            out[k] = int(out[k])
    for k in ("Latitude", "Longitude"):
        if k in out:
            out[k] = float(out[k])
    return out


def read_sounding_dir(directory: Union[str, Path]) -> Optional[dict]:
    """Read a single sounding directory containing ``*.stn`` and ``*.stb`` files."""
    d = Path(directory)
    stb_files, stn_files = sorted(d.glob("*.stb")), sorted(d.glob("*.stn"))
    if not stn_files:
        return None
    st = read_stn(stn_files[0])
    row = {
        "sounding": d.name,
        "station": st.get("StationNo"),
        "line": st.get("LineNo"),
        "lat": st.get("Latitude"),
        "lon": st.get("Longitude"),
    }
    if not stb_files:
        return {**row, "n_lm": 0, "n_hm": 0}
    s = read_stb(stb_files[0])
    row.update(n_lm=len(s.stacks["LM"]), n_hm=len(s.stacks["HM"]), polarity=1)
    if row["n_hm"] > 0 and s.data("HM").mean(0)[:5].mean() < 0:
        row["polarity"] = -1
    for m in ("LM", "HM"):
        row[f"t_{m}"] = s.gate_times[m]
        if len(s.stacks[m]) == 0:
            continue
        D = s.data(m) * row["polarity"]
        S = s.rel_std(m) / 100.0 * np.abs(D)
        n = len(D)
        row[f"d_{m}"] = D.mean(0)
        row[f"sem_emp_{m}"] = D.std(0, ddof=1) / np.sqrt(n) if n > 1 else np.zeros(D.shape[1])
        row[f"sem_rep_{m}"] = np.sqrt((S**2).sum(0)) / n
        row[f"stacks_{m}"] = D
    return row


def read_survey(data_root: Union[str, Path], pattern: str = "*/*") -> pd.DataFrame:
    """Read all sounding directories under ``data_root`` into a DataFrame."""
    root = Path(data_root)
    if (root / "Data").is_dir():
        root = root / "Data"
    rows = []
    for d in sorted(root.glob(pattern)):
        if d.is_dir():
            rec = read_sounding_dir(d)
            if rec is not None:
                rows.append(rec)
    df = pd.DataFrame(rows)
    if not df.empty and "lat" in df and "lon" in df:
        df["x_m"] = (df.lon - df.lon.iloc[0]) * 111320 * np.cos(np.deg2rad(df.lat.iloc[0]))
        df["y_m"] = (df.lat - df.lat.iloc[0]) * 110574
        df["dist_m"] = np.r_[0, np.cumsum(np.hypot(np.diff(df.x_m), np.diff(df.y_m)))]
    return df
