# Controlled Material Color Probes

Use when an unexpected render color suggests a node conversion or buffer issue.
Do not run for every material edit. Reuse the actual scene's renderer, color
management, and output pipeline; log their values and exact C4D/renderer versions.
Work in a disposable probe document or a copy, preserving the user's scene.

## Three-patch comparison

Choose a midtone test color away from clipping. Convert it once from its declared
source space to the document's rendering space. Create three large flat patches:

1. Send the converted color directly to an emissive material input.
2. Send the same converted color through the suspect node. For Maxon Noise, set
   both color inputs equal so the procedural pattern cannot change the result.
3. Send the original unconverted numeric values through that same node as a
   deliberately different control.

Use emission with base and reflection contributions disabled, no relevant light
or environment contribution, and an identical camera/output transform for all
patches. Confirm the queried node ports and connections; commit before read-back.
Avoid measuring a lit standard surface as a color-conversion test.

Render using the verified `cinema4d-c4dpy` buffer flags/settings and save the
result with exactly the intended view transform. Sample central interior regions
well away from boundaries, background, and antialiasing. Record sample rectangles,
the input values, output values, and transform state together. A patch missed by
the sample coordinate invalidates the measurement.

## Interpretation and evidence

In the 2026.3.3 briefcase experiment, the direct converted color and identical
color through Maxon Noise both produced RGB [123, 120, 156]. The unconverted
control produced [174, 173, 190]. Thus the tested Noise path did not introduce the
suspected extra conversion. This did not establish a rule for every color port,
node, renderer, or document configuration.

If the first two agree, investigate lighting, roughness, bump, coat, and tone
mapping in the actual beauty scene. If they disagree, first check graph wiring,
port semantics, sampling, and buffer transforms before attributing the result to
the renderer. Preserve the successful minimal probe and measured evidence when
adding a new compatibility rule.

This procedure is documentation distilled from a working project probe. It is
not a packaged executable or a compatibility test already run on all C4D builds.
