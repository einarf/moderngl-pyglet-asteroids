#version 330

#if defined VERTEX_SHADER

uniform mat4 m_view;
uniform mat4 m_proj;

in vec3 in_position;
in vec2 in_texcoord_0;
out vec2 uv0;

void main() {
    gl_Position = m_proj * m_view * vec4(in_position, 1.0);
    uv0 = in_texcoord_0;
}

#elif defined FRAGMENT_SHADER

out vec4 fragColor;
uniform sampler2D texture0;
uniform vec2 scale;
in vec2 uv0;

void main() {
    fragColor = texture(texture0, uv0 * scale);
}
#endif
