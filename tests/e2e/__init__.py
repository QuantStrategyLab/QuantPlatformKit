"""End-to-end integration tests for QuantStrategyLab.

Tests verify cross-repo interactions:
- Strategy catalog → entrypoint → build_target_weights chain
- Risk engine → signal aggregation → risk assessment
- Data version → manifest → release packaging
- Broker adapter → market data → portfolio → execution flow
"""
