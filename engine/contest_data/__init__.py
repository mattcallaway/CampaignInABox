"""
engine/contest_data/__init__.py

Canonical contest data package.
Provides one authoritative path resolver and intake workflow for all
election-result/contest data in Campaign In A Box.
"""
from engine.contest_data.contest_resolver import ContestResolver
from engine.contest_data.contest_intake   import ContestIntake
from engine.contest_data.contest_health   import ContestHealthChecker

__all__ = ["ContestResolver", "ContestIntake", "ContestHealthChecker"]
