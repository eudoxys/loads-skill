"""Agent-facing helpers around `eudoxys/loads`.

`loads` builds hourly county-level US electric load models. `loadskill` adds
the pieces a workflow needs around it: place-name resolution, explicit
`Total` modes, contract validation, summaries, calibration, nodal
aggregation and provenance-carrying export. It never changes the model.

Modules that need `loads` data (`fetch`) import it lazily; everything else
works offline on any frame with `loads` columns.
"""

from .aggregate import allocate, conservation_error, nearest_nodes
from .calibrate import fit_energy_peak, scale_monthly, scale_to_energy
from .export import read_csv, to_csv, to_long, to_player
from .fetch import (
    BatchResult,
    batch,
    check_credentials,
    configure,
    county_loads,
    series,
    training,
)
from .locations import County, counties, resolve
from .summarize import (
    coincident_peak,
    daily_profile,
    duration_curve,
    energy,
    load_factor,
    peaks,
    summary,
    temperature_response,
)
from .timeaxis import hourly_range, to_local, to_local_standard
from .validate import Report, validate

__version__ = "0.1.0"

__all__ = [
    "BatchResult", "County", "Report", "allocate", "batch", "check_credentials",
    "coincident_peak", "configure", "conservation_error", "counties", "county_loads",
    "daily_profile", "duration_curve", "energy", "fit_energy_peak", "hourly_range",
    "load_factor", "nearest_nodes", "peaks", "read_csv", "resolve", "scale_monthly",
    "scale_to_energy", "series", "summary", "temperature_response", "to_csv",
    "to_local", "to_local_standard", "to_long", "to_player", "training", "validate",
]
