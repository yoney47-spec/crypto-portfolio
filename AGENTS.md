# Repository instructions

Before changing UI, layout, CSS, Plotly charts, icons, animation, or user-facing copy,
read and follow `DESIGN.md`.

- `DESIGN.md` is the design contract.
- `styles/main.css` contains browser-facing design tokens.
- `components/design_tokens.py` contains matching Plotly/Python tokens.
- Keep shared token values aligned across those files.
- Prefer existing tokens over new literal colors, spacing, radii, fonts, or shadows.
- Preserve public read-only behavior, admin authentication clarity, selected-currency
  formatting, responsive layouts, and the sidebar reopen control.
- For currency UI changes, verify both JPY and USD behavior.
- Run the relevant tests before committing.
