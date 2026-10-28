from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)


class ConstraintEngine:
    """
    Z3-based symbolic constraint solver for the cognitive architecture.

    Provides three capabilities:
    1. Road safety verification  — kinematic stopping-distance model
    2. Optimal safe speed        — linear optimisation via Z3 Optimize
    3. Logical consistency       — mutual-exclusion axiom checking
    """

    # Known domain axioms: sets of facts that cannot all be true simultaneously
    _MUTUAL_EXCLUSIONS: list[frozenset[str]] = [
        frozenset({"road_slippery", "road_clear"}),
    ]

    # ── Safety Check ────────────────────────────────────────────────────────

    def check_road_safety(
        self,
        speed_kmh: float,
        friction_coefficient: float,
        visibility_meters: float,
    ) -> dict:
        """
        Verify driving safety using Z3.

        Kinematic model: stopping_distance = v² / (2μg)
        Safe iff stopping_distance ≤ visibility_meters.

        Z3 is used to *certify* (or refute) the safety claim rather than
        just computing arithmetic, giving a formal guarantee.
        """
        try:
            from z3 import Not, Real, Solver, sat, unsat

            s = Solver()
            speed = Real("speed_ms")
            mu = Real("friction")
            vis = Real("visibility")
            sd = Real("stopping_distance")

            speed_ms = speed_kmh / 3.6
            g = 9.81

            s.add(speed == speed_ms)
            s.add(mu == friction_coefficient)
            s.add(vis == visibility_meters)
            # sd * 2 * mu * g = speed² (avoids division in Z3)
            s.add(sd * 2 * mu * g == speed * speed)

            # Can safety be violated? (i.e., sd > vis)
            s.add(Not(sd <= vis))
            result = s.check()

            sd_val = speed_ms ** 2 / (2 * friction_coefficient * g)
            safe_speed_ms = math.sqrt(2 * friction_coefficient * g * visibility_meters)
            safe_speed_kmh = safe_speed_ms * 3.6

            if result == unsat:
                return {
                    "safe": True,
                    "message": "Safety constraints satisfied — stopping distance within visibility",
                    "speed_kmh": speed_kmh,
                    "stopping_distance_m": round(sd_val, 2),
                    "visibility_m": visibility_meters,
                    "max_safe_speed_kmh": round(safe_speed_kmh, 1),
                    "margin_m": round(visibility_meters - sd_val, 2),
                    "z3_solver_result": "unsat (safe)",
                }
            elif result == sat:
                return {
                    "safe": False,
                    "message": "SAFETY VIOLATION — stopping distance exceeds visibility",
                    "speed_kmh": speed_kmh,
                    "stopping_distance_m": round(sd_val, 2),
                    "visibility_m": visibility_meters,
                    "max_safe_speed_kmh": round(safe_speed_kmh, 1),
                    "margin_m": round(visibility_meters - sd_val, 2),
                    "z3_solver_result": "sat (unsafe)",
                }
            else:
                return {
                    "safe": None,
                    "message": "Z3 returned unknown — inconclusive",
                    "z3_solver_result": "unknown",
                }

        except Exception as exc:
            logger.exception("Z3 safety check failed")
            raise RuntimeError(f"Z3 safety check error: {exc}") from exc

    # ── Speed Optimisation ───────────────────────────────────────────────────

    def optimize_speed(
        self,
        max_speed_kmh: float,
        friction_coefficient: float,
        visibility_meters: float,
    ) -> dict:
        """
        Find the maximum speed that satisfies both the legal limit and the
        kinematic safety constraint, using Z3 Optimize (linear real arithmetic).
        """
        try:
            from z3 import Optimize, Real, sat

            g = 9.81
            # v_max_safe = sqrt(2μg·d) — precomputed; constraint becomes linear
            max_safe_ms = math.sqrt(2 * friction_coefficient * g * visibility_meters)
            max_requested_ms = max_speed_kmh / 3.6

            opt = Optimize()
            speed = Real("speed_ms")

            opt.add(speed >= 0)
            opt.add(speed <= max_requested_ms)   # legal / hardware cap
            opt.add(speed <= max_safe_ms)         # kinematic safety cap (linear)
            opt.maximize(speed)

            result = opt.check()

            if result == sat:
                model = opt.model()
                val = model[speed]
                # Extract numeric value robustly
                try:
                    frac = val.as_fraction()
                    optimal_ms = frac.numerator / frac.denominator
                except Exception:
                    optimal_ms = float(val.as_decimal(8).rstrip("?"))

                optimal_kmh = optimal_ms * 3.6
                sd = optimal_ms ** 2 / (2 * friction_coefficient * g)
                return {
                    "feasible": True,
                    "optimal_speed_kmh": round(optimal_kmh, 1),
                    "optimal_speed_ms": round(optimal_ms, 2),
                    "stopping_distance_m": round(sd, 2),
                    "input_max_speed_kmh": max_speed_kmh,
                    "visibility_m": visibility_meters,
                    "friction_coefficient": friction_coefficient,
                    "z3_verified": True,
                }
            else:
                return {
                    "feasible": False,
                    "message": "No feasible speed found — conditions may be unsafe for any speed",
                    "z3_verified": True,
                }

        except Exception as exc:
            logger.exception("Z3 speed optimisation failed")
            raise RuntimeError(f"Z3 optimise error: {exc}") from exc

    # ── Logical Consistency ──────────────────────────────────────────────────

    def check_logical_consistency(self, facts: list[str]) -> dict:
        """
        Assert a set of symbolic facts and check whether they are mutually
        consistent given the domain axioms (e.g. road_slippery ∧ road_clear
        is a contradiction).
        """
        try:
            from z3 import And, Bool, Not, Solver, sat

            s = Solver()
            known = {
                "road_slippery": Bool("road_slippery"),
                "road_clear": Bool("road_clear"),
                "traffic_congestion": Bool("traffic_congestion"),
                "obstacle_detected": Bool("obstacle_detected"),
                "emergency_alert": Bool("emergency_alert"),
                "low_visibility": Bool("low_visibility"),
                "general_observation": Bool("general_observation"),
            }

            # Encode mutual-exclusion axioms
            violated_axioms: list[str] = []
            for excl_set in self._MUTUAL_EXCLUSIONS:
                bools = [known[f] for f in excl_set if f in known]
                if len(bools) >= 2:
                    s.add(Not(And(*bools)))

            # Assert provided facts
            for fact in facts:
                if fact in known:
                    s.add(known[fact])

            result = s.check()
            consistent = result == sat

            if not consistent:
                for excl_set in self._MUTUAL_EXCLUSIONS:
                    if excl_set.issubset(set(facts)):
                        violated_axioms.append(
                            f"Mutual exclusion: {{{', '.join(sorted(excl_set))}}}"
                        )

            return {
                "consistent": consistent,
                "facts": facts,
                "violated_axioms": violated_axioms,
                "solver_result": str(result),
            }

        except Exception as exc:
            logger.exception("Z3 consistency check failed")
            raise RuntimeError(f"Z3 consistency error: {exc}") from exc
