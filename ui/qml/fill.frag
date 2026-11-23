#version 440
// Paints the letters of a title with a slow flowing gradient of three colours and, now and then, a
// band of light sweeping across. Only the shape (alpha) of the letters is taken from the source.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float shine;
    float lift;
    vec4 c0;
    vec4 c1;
    vec4 c2;
};
layout(binding = 1) uniform sampler2D source;

void main() {
    vec2 uv = qt_TexCoord0;
    float a = texture(source, uv).a;
    float f = uv.x * 0.9 - uv.y * 0.25 + time * 0.07;
    float w0 = 0.5 + 0.5 * cos(6.28318 * f);
    float w1 = 0.5 + 0.5 * cos(6.28318 * (f - 0.3333));
    float w2 = 0.5 + 0.5 * cos(6.28318 * (f - 0.6667));
    vec3 col = (c0.rgb * w0 + c1.rgb * w1 + c2.rgb * w2) / max(0.001, w0 + w1 + w2);
    // Covers are often dark and muddy: take the hue at full brightness, then lift it towards white
    // so the title always reads.
    col = col / max(0.04, max(col.r, max(col.g, col.b)));
    col = mix(col, vec3(1.0), lift);
    float d = (uv.x + (uv.y - 0.5) * 0.35 - shine) / 0.07;
    col = mix(col, vec3(1.0), exp(-d * d) * 0.85);
    fragColor = vec4(col * a, a) * qt_Opacity;
}
