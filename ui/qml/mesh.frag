#version 440
// The colour field behind the now-playing screen: four soft blobs of the cover's colours drifting
// on slow paths, a light under the cover that swells with the bass, a vignette, and dithering of
// half a step so the dark gradients never show bands.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float bass;
    float aspect;
    vec4 c0;
    vec4 c1;
    vec4 c2;
    vec4 c3;
    vec4 spot;
    vec4 mood;
};

float blob(vec2 uv, vec2 centre, float radius) {
    vec2 d = uv - centre;
    d.x *= aspect;
    return exp(-dot(d, d) / (radius * radius));
}

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
    vec2 uv = qt_TexCoord0;
    vec3 colour = c3.rgb * 0.22;
    vec2 p0 = vec2(0.50 + 0.40 * sin(time * 0.060 + 0.0), 0.50 + 0.38 * cos(time * 0.090 + 0.0));
    vec2 p1 = vec2(0.50 + 0.42 * sin(time * 0.045 + 1.7), 0.50 + 0.36 * cos(time * 0.070 + 2.3));
    vec2 p2 = vec2(0.50 + 0.38 * sin(time * 0.080 + 3.4), 0.50 + 0.40 * cos(time * 0.050 + 4.6));
    vec2 p3 = vec2(0.50 + 0.44 * sin(time * 0.035 + 5.1), 0.50 + 0.34 * cos(time * 0.065 + 6.9));
    colour = mix(colour, c0.rgb, 0.85 * blob(uv, p0, 0.55 + 0.10 * bass));
    colour = mix(colour, c1.rgb, 0.75 * blob(uv, p1, 0.50));
    colour = mix(colour, c2.rgb, 0.70 * blob(uv, p2, 0.45));
    colour = mix(colour, c3.rgb, 0.55 * blob(uv, p3, 0.60));
    colour *= 0.55;
    // The light under the cover: spot.xy is where, spot.z how far it reaches, spot.w how strong.
    colour += mood.rgb * spot.w * blob(uv, spot.xy, spot.z) * (0.55 + 0.6 * bass);
    vec2 v = (uv - 0.5) * vec2(aspect, 1.0);
    colour *= mix(1.0, 0.35, smoothstep(0.35, 1.05, length(v)));
    colour += (hash(uv * vec2(1931.0, 1777.0) + fract(time)) - 0.5) / 255.0;
    fragColor = vec4(colour, 1.0) * qt_Opacity;
}
