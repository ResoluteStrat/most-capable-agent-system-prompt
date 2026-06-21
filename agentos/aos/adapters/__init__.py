"""Adapter slots — vendor-neutral seams the core depends on via stable interfaces.

Today: `model` (model-routing/economics). Tomorrow: browser, desktop, exec
sandbox. Keeping these behind adapters is what lets the runtime/model/provider be
swapped without rewriting the engine.
"""
