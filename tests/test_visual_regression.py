from __future__ import annotations

from pathlib import Path

import app
from modules.services import verify_visual_glassmorphism_contract


def test_glassmorphism_contract_on_app_css():
    source = Path(app.__file__).read_text(encoding="utf-8")
    contract = verify_visual_glassmorphism_contract(source)
    assert contract["has_backdrop_blur"] is True
    assert contract["has_border_radius"] is True
    assert contract["has_glow_or_gradient"] is True


def test_glassmorphism_contract_negative_case():
    plain_html = "<div style='color: black;'>Simple Text</div>"
    contract = verify_visual_glassmorphism_contract(plain_html)
    assert contract["has_backdrop_blur"] is False
    assert contract["has_border_radius"] is False
    assert contract["has_glow_or_gradient"] is False
