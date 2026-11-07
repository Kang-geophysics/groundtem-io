"""Parse a GroundTEM ``.sts`` protocol file into structured dataclasses."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, Tuple, Union

import numpy as np
import pandas as pd

DEFAULT_SAMPLE_PERIOD = 0.25e-6


@dataclass
class Moment:
    name: str
    on_time: float  # [s]
    period_time: float  # [s]
    stack_size: int
    target_current: float  # [A]
    wave_time: np.ndarray  # [s], 0 = start of turn-off ramp
    wave_amp: np.ndarray  # normalised amplitude [0, 1]
    gate_start: np.ndarray  # [s] after end of on-time (start of turn-off ramp)
    gate_end: np.ndarray  # [s] after end of on-time
    tap_start: float  # [s] start of the tapered (log-spaced) gates
    damper_time: Tuple[float, float] = (0.0, 0.0)  # (on, off) [s]

    @property
    def gate_center(self) -> np.ndarray:
        """Raw gate center times [s] after turn-off start."""
        return 0.5 * (self.gate_start + self.gate_end)

    @property
    def gate_width(self) -> np.ndarray:
        """Raw gate widths [s]."""
        return self.gate_end - self.gate_start

    @property
    def turnoff_duration(self) -> float:
        """Duration of the turn-off ramp [s] (from t=0 to final zero-current node)."""
        return float(self.wave_time[-1])

    def tapered_times(self, per_decade: int = 10, include_early: bool = False) -> np.ndarray:
        """Log-spaced gate centres (matching the '[Tapering]' section) in [s]."""
        t0 = max(self.tap_start, float(self.gate_center[0]))
        t1 = float(self.gate_center[-1])
        n = int(np.floor(np.log10(t1 / t0) * per_decade)) + 1
        t_tap = t0 * 10.0 ** (np.arange(n) / per_decade)
        if include_early:
            early_mask = (self.gate_center > self.turnoff_duration) & (self.gate_center < t0)
            if np.any(early_mask):
                return np.r_[self.gate_center[early_mask], t_tap]
        return t_tap


@dataclass
class Protocol:
    name: str
    filepath: Path
    sample_freq_hz: float
    tx_xyz: np.ndarray
    tx_size: Tuple[float, float]  # (x length, y length) [m]
    tx_turns: int
    rx_xyz: np.ndarray
    rx_area: float  # effective area [m^2]
    lp_filters: Tuple[float, ...]  # first-order low-pass cut-off frequencies [Hz]
    gate_per_decade: int = 10
    auto_sign: str = "InLoop"
    powerline_freq: float = 60.0
    moments: Dict[str, Moment] = field(default_factory=dict)

    @property
    def tx_area(self) -> float:
        """Single-turn transmitter loop area [m^2]."""
        return float(self.tx_size[0] * self.tx_size[1])

    @property
    def offset(self) -> float:
        """Horizontal center-to-center distance between Tx and Rx [m]."""
        return float(np.linalg.norm(self.rx_xyz[:2] - self.tx_xyz[:2]))

    @property
    def is_inloop(self) -> bool:
        """True if central/in-loop configuration (zero horizontal offset)."""
        return self.offset < 1e-6

    def dipole_moment(self, moment_name: str) -> float:
        """Transmitter magnetic dipole moment I * N_tx * A_tx [A*m^2]."""
        mom = self.moments[moment_name.upper()]
        return float(mom.target_current * self.tx_turns * self.tx_area)


def _read_sts(path: Union[str, Path]) -> dict:
    out = {}
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if lines and lines[0].startswith(";[ProtocolDesigner]"):
        m = re.search(r"SampleFrequencyMHz\s*=\s*([0-9.]+)", lines[0])
        if m:
            out["SampleFrequencyMHz"] = float(m.group(1))
    for line in lines:
        if line.startswith((";", "[")) or "=" not in line:
            continue
        k, v = (s.strip() for s in line.split("=", 1))
        try:
            out[k] = np.array([float(x) for x in v.split(",")])
        except ValueError:
            out[k] = v
    return out


def read_protocol(path: Union[str, Path], channel: str = "A") -> Protocol:
    """Read a GroundTEM ``.sts`` protocol file."""
    path = Path(path)
    d = _read_sts(path)
    sample_freq_hz = float(d.get("SampleFrequencyMHz", 4.0)) * 1e6
    sample_period = 1.0 / sample_freq_hz

    p = Protocol(
        name=path.stem,
        filepath=path,
        sample_freq_hz=sample_freq_hz,
        tx_xyz=d["TxLoop_XYZPos"],
        tx_size=tuple(float(x) for x in d["TxLoop_XYLength"]),
        tx_turns=int(d["TxLoop_NTurns"][0]),
        rx_xyz=d["RxCoil_XYZPos"],
        rx_area=float(d[f"RxCoil_Area{'Ch' + channel}"][0]),
        lp_filters=tuple(float(x) for x in d["LPFilter_1order"]),
        gate_per_decade=int(d.get(f"Ch{channel}_GatePerDecade", [10])[0]),
        auto_sign=str(d.get("AutoSignDetection", "InLoop")),
        powerline_freq=float(d.get("PowerLineMonitorFreq", [60.0])[0]),
    )
    for m in ("LM", "HM"):
        on_time = float(d[f"{m}_OnTime"][0]) * 1e-6
        period_time = float(d[f"{m}_PeriodTime"][0]) * 1e-6
        stack_size = int(d[f"{m}_StackSize"][0])
        damper_on = float(d.get(f"{m}_Damper_TimeOn", [on_time * 1e6])[0]) * 1e-6
        damper_off = float(d.get(f"{m}_Damper_TimeOff", [on_time * 1e6])[0]) * 1e-6
        g0 = d[f"{m}_Ch{channel}_GateIndex0"][1:]
        g1 = d[f"{m}_Ch{channel}_GateIndex1"][1:]
        p.moments[m] = Moment(
            name=m,
            on_time=on_time,
            period_time=period_time,
            stack_size=stack_size,
            target_current=float(d[f"{m}_Tx_TargetCurrent"][0]),
            wave_time=d[f"{m}_Waveform_Time"] * 1e-6,
            wave_amp=d[f"{m}_Waveform_Amplitude"],
            gate_start=g0 * sample_period - on_time,
            gate_end=g1 * sample_period - on_time,
            tap_start=float(d[f"{m}_Ch{channel}_TapStartTime"][0]) * 1e-6,
            damper_time=(damper_on, damper_off),
        )
    return p


def summarize_protocols(protocols: Dict[str, Protocol]) -> pd.DataFrame:
    """Build a summary table of survey configurations from loaded protocols."""
    rows = []
    for label, proto in protocols.items():
        geom_type = (
            f"In-Loop (Offset {proto.offset:.0f} m)"
            if proto.is_inloop
            else f"Offset Loop (Center Offset {proto.offset:.1f} m)"
        )
        for mname, mom in proto.moments.items():
            t_tap = mom.tapered_times(per_decade=proto.gate_per_decade)
            rows.append(
                {
                    "Configuration": f"{label} - {mname}",
                    "Protocol File": proto.filepath.name,
                    "Geometry": geom_type,
                    "Tx Loop (m)": f"{proto.tx_size[0]:.0f}x{proto.tx_size[1]:.0f} ({proto.tx_turns} turn{'s' if proto.tx_turns > 1 else ''})",
                    "Rx Pos (x, y, z) [m]": f"({proto.rx_xyz[0]:.1f}, {proto.rx_xyz[1]:.1f}, {proto.rx_xyz[2]:.1f})",
                    "Rx Eff. Area (m²)": proto.rx_area,
                    "Moment": mname,
                    "Current (A)": mom.target_current,
                    "Tx Moment (A·m²)": proto.dipole_moment(mname),
                    "On-Time (µs)": mom.on_time * 1e6,
                    "Turn-off Ramp (µs)": mom.turnoff_duration * 1e6,
                    "Period (µs)": mom.period_time * 1e6,
                    "Stack Size": mom.stack_size,
                    "Raw Gates": len(mom.gate_center),
                    "Raw Gate Range (µs)": f"{mom.gate_center[0]*1e6:.2f} – {mom.gate_center[-1]*1e6:.1f}",
                    "Tapering Start (µs)": mom.tap_start * 1e6,
                    "Tapered Gates": len(t_tap),
                    "Tapered Range (µs)": f"{t_tap[0]*1e6:.1f} – {t_tap[-1]*1e6:.1f}",
                    "LP Filters (kHz)": f"{proto.lp_filters[0]/1e3:.0f}, {proto.lp_filters[1]/1e3:.0f}",
                }
            )
    return pd.DataFrame(rows)
