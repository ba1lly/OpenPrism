"""OpenPrism — many diverse model voices, split and recombined into one judged answer.

A panel of models (your own provider keys, or any model in opencode) runs in
parallel; a judge model reconciles them. Two modes:
  - research: Fusion-style synthesis (consensus / contradictions / gaps -> grounded answer)
  - code:     best-of-N selection + repair into one final solution
"""

__version__ = "0.1.0"
