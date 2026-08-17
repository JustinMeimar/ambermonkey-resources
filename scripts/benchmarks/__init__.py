"""Shared parsers for Raptor-driven benchmarks (Speedometer 3, JetStream 3).

Fossil analysis scripts should import from this package to avoid
re-implementing the same stdout-slurp + suite-lookup logic that has drifted
across ambermonkey fossils.

Usage:

    import os, sys
    sys.path.insert(0, os.environ["FOSSIL_PROJECT_DIR"] + "/scripts")
    from benchmarks import manifest, raptor, speedometer3, jetstream3
"""
