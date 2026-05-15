# CORA general introduction deck

Reusable ~30-min introduction to CORA for any synchrotron-adjacent venue.
Lead motivator: AI / autonomous experimentation needs a unified record to
reason from. Reproducibility, FAIR data, and debugging come along for free.

## Run locally

```bash
npm install
npm run dev    # http://localhost:3030
```

## Build / export

```bash
npm run build  # static site → ./dist/
npm run export # → cora-intro.pdf
```

## Customize before presenting

- [ ] Slide 2 (who I am): tune the bullets to the audience. A tomography venue gets specific instruments; a software venue gets the open-source angle.
- [ ] Slide 3 (why I'm building this): adjust the opening sentence to your background.
- [ ] Slide 7 (concrete example): if your audience has a different AI touchpoint than exposure tuning, swap the example.
- [ ] Slide 10 (what I'd want from you): drop the columns that don't apply; expand the one that does.

## Title slide

The title slide uses `hero-bloom.webp` (copied from `docs/assets/`) as a
full-bleed background with white text. To swap, replace
`public/hero-bloom.webp` and update the `background:` line in the
frontmatter of `slides.md`.

## Audience tuning

The deck is built so the same slides work for three audience types:

| Audience | Lean into |
|---|---|
| Beamline scientists | Slides 6, 7. What CORA is *not*, the AI-decision example as a stand-in for human decision-making. |
| Software / RSE crowd | Slide 8. The three-layer architecture, event sourcing, adapter pattern. |
| AI-for-science crowd | Slides 3, 7, 10. The AI-needs-context framing, the agent example, the "what context do your agents need" ask. |

Speaker notes (HTML comments at the bottom of each slide) include
adjustment hints per audience type.

## Theme

Currently `default`. Swap to `seriph` (more academic feel) by changing
line 2 of `slides.md`:

```yaml
theme: seriph
```
