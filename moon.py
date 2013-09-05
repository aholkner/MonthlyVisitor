import bacon

moon_image = bacon.Image('res/moon.jpg')

shader = bacon.Shader(vertex_source=
    """
    precision highp float;
    attribute vec3 a_Position;
    attribute vec2 a_TexCoord0;
    attribute vec4 a_Color;

    varying vec2 v_TexCoord0;
    varying vec4 v_Color;
    varying vec2 v_Position;

    uniform mat4 g_Projection;

    void main()
    {
        gl_Position = g_Projection * vec4(a_Position, 1.0);
        v_TexCoord0 = a_TexCoord0;
        v_Color = a_Color;
        v_Position = a_Position.xy;
    }
    """,

    fragment_source=
    """
    precision highp float;
    
    uniform sampler2D g_Texture0;
    uniform vec2 center;
    uniform float radius;
    uniform float g_Time;
    
    varying vec2 v_TexCoord0;
    varying vec4 v_Color;
    varying vec2 v_Position;

    void main()
    {
        // Standard vertex color and texture
        vec4 color = v_Color * texture2D(g_Texture0, v_TexCoord0);

        vec3 normal = vec3((v_Position - center) / radius, 0.0);
        normal.z = 1.0 - sqrt(normal.x * normal.x + normal.y * normal.y);

        float angle = g_Time;
        vec3 light;
        light.x = cos(angle);
        light.y = 0.0;
        light.z = sin(angle);
        
        // Direct diffuse
        float illum = max(0.0, dot(light, normal));
        
        // Rim
        illum += pow(max(0.0, -light.z), 5.0) * pow(1.0 - normal.z, 10.0);

        gl_FragColor = color * clamp(illum, 0.0, 1.0);
    }
    """)

uniform_center = shader.uniforms['center']
uniform_radius = shader.uniforms['radius']

class Moon(object):
    def __init__(self):
        pass

    def draw(self):
        uniform_center.value = (self.x, self.y)
        uniform_radius.value = 240
        bacon.set_shader(shader)
        bacon.draw_image(moon_image, 
            self.x - moon_image.width / 2,
            self.y - moon_image.height / 2)
        bacon.set_shader(None)

