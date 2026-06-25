// Patina PS1 shader (TDD 5.4) — minimal, in-house, no vendored code.
//
// Implements the four signature PS1 tells. Written from scratch so the licence
// is unambiguously yours; if you'd rather wrap an MIT/CC0 pack (per TDD 9),
// drop it in beside this and point the addon at it — honour that pack's licence.
//
// FIRST-RUN-IN-ENGINE: drafted against known-good Godot 4 patterns and confirmed
// to compile-shape only. Walk it in Godot 4.7 to confirm the look. The affine
// term is the part most likely to need a per-version tweak (Godot does not
// expose a `noperspective` qualifier, so affine is approximated); densify in the
// asset pass is the standard mitigation if it over-warps.

shader_type spatial;
render_mode vertex_lighting, diffuse_lambert, specular_disabled,
            shadows_disabled, ambient_light_disabled, cull_back;

uniform sampler2D albedo_tex : source_color, filter_nearest, repeat_enable;
uniform bool use_texture = false;
uniform float jitter = 64.0;             // snap grid; lower = chunkier wobble
uniform float affine_strength : hint_range(0.0, 1.0) = 0.85;
uniform int color_depth = 16;            // levels per channel
uniform bool dither = true;
uniform vec3 ambient_color : source_color = vec3(1.0);  // white ambient

varying vec2 v_uv_affine;
varying float v_w;

void vertex() {
    // --- vertex snapping (jitter): the #1 PS1 tell ---
    vec4 clip = PROJECTION_MATRIX * MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
    vec2 grid = vec2(jitter, jitter);
    vec2 ndc = clip.xy / clip.w;
    ndc = round(ndc * grid) / grid;
    clip.xy = ndc * clip.w;
    POSITION = clip;

    // --- affine texture mapping (approximate): pass UV*w, divide in fragment ---
    v_w = clip.w;
    v_uv_affine = UV * clip.w;
}

// 4x4 ordered (Bayer) dither matrix, normalised to 0..1.
float bayer4(vec2 p) {
    int x = int(mod(p.x, 4.0));
    int y = int(mod(p.y, 4.0));
    int m[16] = {0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5};
    return float(m[y * 4 + x]) / 16.0;
}

void fragment() {
    // Blend perspective-correct UV (UV) with the affine approximation.
    vec2 uv_affine = v_uv_affine / v_w;
    vec2 uv = mix(UV, uv_affine, affine_strength);

    vec3 col = COLOR.rgb;                          // vertex colour = the lighting
    if (use_texture) {
        col *= texture(albedo_tex, uv).rgb;
    }
    col *= ambient_color;

    // --- colour-depth limit + ordered dithering: the grainy banded look ---
    float levels = float(max(color_depth, 2));
    if (dither) {
        float d = (bayer4(FRAGCOORD.xy) - 0.5) / levels;
        col += vec3(d);
    }
    col = floor(col * levels + 0.5) / levels;

    ALBEDO = clamp(col, 0.0, 1.0);
}
