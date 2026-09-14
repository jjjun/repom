"""Fixture package that imports cleanly but defines zero models.

Used to test the catastrophic case where model_locations points at a package
that discovers zero tables despite importing without any failure.
"""
