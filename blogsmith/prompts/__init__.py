"""Prompt layer.

Authored, versioned default system prompts for every pipeline stage
(:mod:`~blogsmith.prompts.defaults`) plus the assembly logic that layers a
site's brand voice and per-stage custom prompts on top
(:mod:`~blogsmith.prompts.assemble`).
"""

from blogsmith.prompts.assemble import PROMPT_VERSION, build_system_prompt

__all__ = ["PROMPT_VERSION", "build_system_prompt"]
