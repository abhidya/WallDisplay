class MedusesAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.glCanvas = document.createElement('canvas');
        this.glCanvas.width = this.canvas.width;
        this.glCanvas.height = this.canvas.height;

        this.gl = null;
        this.program = null;
        this.vertexBuffer = null;
        this.uniforms = {};
        this.noiseTexture = null;

        this.initWebGL();
    }

    initWebGL() {
        this.gl =
            this.glCanvas.getContext('webgl2', { alpha: false, antialias: true }) ||
            this.glCanvas.getContext('webgl2');

        if (!this.gl) {
            console.error('MedusesAnimation requires WebGL2');
            return;
        }

        const vertexSource = `#version 300 es
            in vec2 a_position;
            void main() {
                gl_Position = vec4(a_position, 0.0, 1.0);
            }
        `;

        const fragmentSource = `#version 300 es
            precision highp float;

            out vec4 fragColor;
            uniform vec2 iResolution;
            uniform float iTime;
            uniform sampler2D iChannel0;

            const int numTentacle = 2;
            const bool fog = true;
            const bool reflection = true;
            float magic_value = 0.0;

            float sphere(vec3 p, vec3 o, float r) {
                vec3 d = p - o;
                return length(d) - r;
            }

            float cylinder(vec2 p, vec2 o, float r) {
                return length(p - o) - r;
            }

            float fOpIntersectionRound(float a, float b, float r) {
                vec2 u = max(vec2(r + a, r + b), vec2(0.0));
                return min(-r, max(a, b)) + length(u);
            }

            float fOpDifferenceRound(float a, float b, float r) {
                return fOpIntersectionRound(a, -b, r);
            }

            float pModPolar(inout vec2 p, float repetitions) {
                float angle = 2.0 * 3.14159265 / repetitions;
                float a = atan(p.y, p.x) + angle / 2.0;
                float r = length(p);
                float c = floor(a / angle);
                a = mod(a, angle) - angle / 2.0;
                p = vec2(cos(a), sin(a)) * r;
                if (abs(c) >= (repetitions / 2.0)) {
                    c = abs(c);
                }
                return c;
            }

            vec4 hsv_to_rgb(float h) {
                float c = 1.0;
                h = mod(h * 6.0, 6.0);
                float x = c * (1.0 - abs(mod(h, 2.0) - 1.0));
                vec4 color;

                if (0.0 <= h && h < 1.0) {
                    color = vec4(c, x, 0.0, 1.0);
                } else if (1.0 <= h && h < 2.0) {
                    color = vec4(x, c, 0.0, 1.0);
                } else if (2.0 <= h && h < 3.0) {
                    color = vec4(0.0, c, x, 1.0);
                } else if (3.0 <= h && h < 4.0) {
                    color = vec4(0.0, x, c, 1.0);
                } else if (4.0 <= h && h < 5.0) {
                    color = vec4(x, 0.0, c, 1.0);
                } else if (5.0 <= h && h < 6.0) {
                    color = vec4(c, 0.0, x, 1.0);
                } else {
                    color = vec4(0.0, 0.0, 0.0, 1.0);
                }

                return color;
            }

            mat2 rot2d(float a) {
                float c = cos(a);
                float s = sin(a);
                return mat2(c, -s, s, c);
            }

            float tentacle(vec3 p, float pulse) {
                return cylinder(
                    p.xz,
                    vec2(
                        0.3 + 0.1 * cos(p.y + 2.0 * pulse + 3.0 * iTime),
                        0.2 * sin(p.y + 3.0 * pulse + iTime + 0.1)
                    ),
                    0.1 * exp(p.y * 0.5)
                );
            }

            float medusa(vec3 p) {
                float d = sphere(p, vec3(0.0), 0.8);
                float pulse = -0.7 - 0.2 * cos(iTime);
                d = fOpDifferenceRound(d, sphere(p, vec3(0.0, pulse, 0.0), 1.0), 0.1);

                vec3 q = p;
                q.xz = rot2d(0.3 * iTime) * q.xz;
                vec3 q2 = q;
                pModPolar(q.zx, 5.0);
                q.y -= 0.3 * pulse;

                d = fOpDifferenceRound(d, cylinder(q.xy, vec2(0.0), 0.3), 0.1);

                vec3 q3 = q2;
                pModPolar(q2.xz, float(numTentacle));

                float te = tentacle(q2, pulse);
                q3.xz = rot2d(3.14159265 * 0.5) * q3.xz;
                pModPolar(q3.xz, float(numTentacle));
                te = min(te, tentacle(q3, pulse));
                te = max(te, p.y - 0.3);
                te = fOpDifferenceRound(te, p.y + 5.0, 2.0);

                d = min(d, te);
                return d;
            }

            vec3 curve(float y) {
                return vec3(0.01 * cos(y + iTime), y, 0.01 * sin(y * 0.8 + 0.9 * iTime));
            }

            mat3 localSpace(float y) {
                float eps = 0.001;
                vec3 forward = normalize(curve(y + eps) - curve(y - eps));
                vec3 right = vec3(1.0, 0.0, 0.0);
                vec3 depth = normalize(cross(right, forward));
                right = normalize(cross(forward, depth));
                return mat3(right, forward, depth);
            }

            float mapScene(vec3 p) {
                p.y -= iTime * 0.4;
                vec3 period = vec3(7.0);
                vec3 id = floor((p - period * 0.5) / period);
                p.y -= 1.0 + sin(id.x + id.y + id.z);

                float y = p.y + id.x + id.y + id.z;
                p = transpose(localSpace(y)) * p;
                vec3 q = mod(p - period * 0.5, period) - period * 0.5;
                return medusa(q);
            }

            vec3 rm(vec3 ro, vec3 rd, out float st) {
                vec3 p = ro;
                st = 1.0;

                for (int i = 0; i < 80; ++i) {
                    float d = mapScene(p);
                    if (abs(d) < 0.01) {
                        st = float(i) / 80.0;
                        break;
                    }
                    p += rd * d * 0.7;
                }
                return p;
            }

            vec3 shade(vec3 p, vec3 origin, vec3 n, float st) {
                float f = fog ? 0.1 : 0.05;
                vec3 color = vec3(1.0) * exp(-distance(p, origin) * f) * (1.0 + st);
                color *= vec3(0.18 + 0.06 * st, 0.28 + 0.08 * st, 0.35 - 0.04 * st);
                float noise = texture(iChannel0, vec2((p.x + p.y + p.z) * 0.1, 0.25)).x;
                color *= mix(vec3(1.0), hsv_to_rgb((p.x + p.y + p.z) * 0.2 + iTime).rgb, 0.5 * noise);
                return color;
            }

            vec3 grad(vec3 p) {
                vec2 eps = vec2(0.01, 0.0);
                return normalize(vec3(
                    mapScene(p + eps.xyy) - mapScene(p - eps.xyy),
                    mapScene(p + eps.yxy) - mapScene(p - eps.yxy),
                    mapScene(p + eps.yyx) - mapScene(p - eps.yyx)
                ));
            }

            void main() {
                float bpm = 100.0;
                float beat_sec = bpm / 60.0;
                float fq = 2.0 * 3.14159265 * beat_sec;

                if (iTime > 168.0 && iTime < 206.0) {
                    magic_value = pow(
                        abs(sin(0.25 * (iTime + 0.1) * fq)) +
                        abs(cos(0.25 * (iTime + 0.1) * fq)),
                        1.0
                    );
                }

                vec2 uv = gl_FragCoord.xy / iResolution.xy;
                uv = 2.0 * uv - 1.0;
                uv.x *= iResolution.x / iResolution.y;

                vec3 origin = vec3(3.0, 0.0, iTime);
                vec3 direction = normalize(vec3(uv, magic_value * 0.1 + 0.9 - 0.7 * length(uv)));

                if (iTime > 168.0 && iTime < 206.0) {
                    direction.xy = rot2d((float(int(iTime * beat_sec)) - 0.053) * 0.3) * direction.xy;
                }

                float st = 0.0;
                vec3 p = rm(origin, direction, st);
                vec3 n = grad(p);
                vec3 color = shade(p, origin, n, st);

                if (reflection) {
                    vec3 rd = reflect(direction, n);
                    float rst = st;
                    vec3 p2 = rm(p + 0.1 * rd, rd, rst);
                    color = mix(color, shade(p2, origin, grad(p2), rst), 0.05);
                }

                if (fog) {
                    color += vec3(0.0, 0.0, 0.0);
                }

                fragColor = vec4(color, 1.0);
            }
        `;

        const vertexShader = this.createShader(vertexSource, this.gl.VERTEX_SHADER);
        const fragmentShader = this.createShader(fragmentSource, this.gl.FRAGMENT_SHADER);
        if (!vertexShader || !fragmentShader) {
            return;
        }

        this.program = this.gl.createProgram();
        this.gl.attachShader(this.program, vertexShader);
        this.gl.attachShader(this.program, fragmentShader);
        this.gl.linkProgram(this.program);

        if (!this.gl.getProgramParameter(this.program, this.gl.LINK_STATUS)) {
            console.error('MedusesAnimation link error:', this.gl.getProgramInfoLog(this.program));
            return;
        }

        this.vertexBuffer = this.gl.createBuffer();
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.vertexBuffer);
        this.gl.bufferData(
            this.gl.ARRAY_BUFFER,
            new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
            this.gl.STATIC_DRAW
        );

        this.gl.useProgram(this.program);
        const positionLocation = this.gl.getAttribLocation(this.program, 'a_position');
        this.gl.enableVertexAttribArray(positionLocation);
        this.gl.vertexAttribPointer(positionLocation, 2, this.gl.FLOAT, false, 0, 0);

        this.uniforms = {
            resolution: this.gl.getUniformLocation(this.program, 'iResolution'),
            time: this.gl.getUniformLocation(this.program, 'iTime'),
            channel0: this.gl.getUniformLocation(this.program, 'iChannel0'),
        };

        this.noiseTexture = this.createNoiseTexture();
    }

    createShader(source, type) {
        const shader = this.gl.createShader(type);
        this.gl.shaderSource(shader, source);
        this.gl.compileShader(shader);

        if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
            console.error('MedusesAnimation shader error:', this.gl.getShaderInfoLog(shader));
            this.gl.deleteShader(shader);
            return null;
        }

        return shader;
    }

    createNoiseTexture() {
        const size = 256;
        const data = new Uint8Array(size * size * 4);

        for (let i = 0; i < size * size; i += 1) {
            const value = Math.floor(Math.random() * 256);
            const offset = i * 4;
            data[offset] = value;
            data[offset + 1] = value;
            data[offset + 2] = value;
            data[offset + 3] = 255;
        }

        const texture = this.gl.createTexture();
        this.gl.bindTexture(this.gl.TEXTURE_2D, texture);
        this.gl.texImage2D(
            this.gl.TEXTURE_2D,
            0,
            this.gl.RGBA,
            size,
            size,
            0,
            this.gl.RGBA,
            this.gl.UNSIGNED_BYTE,
            data
        );
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_MIN_FILTER, this.gl.LINEAR);
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_MAG_FILTER, this.gl.LINEAR);
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_WRAP_S, this.gl.REPEAT);
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_WRAP_T, this.gl.REPEAT);
        return texture;
    }

    draw() {
        if (!this.gl || !this.program) {
            this.ctx.fillStyle = '#000';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            return;
        }

        if (this.glCanvas.width !== this.canvas.width || this.glCanvas.height !== this.canvas.height) {
            this.glCanvas.width = this.canvas.width;
            this.glCanvas.height = this.canvas.height;
        }

        this.time += 16;

        this.gl.viewport(0, 0, this.glCanvas.width, this.glCanvas.height);
        this.gl.clearColor(0, 0, 0, 1);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);
        this.gl.useProgram(this.program);

        this.gl.uniform2f(this.uniforms.resolution, this.glCanvas.width, this.glCanvas.height);
        this.gl.uniform1f(this.uniforms.time, this.time * 0.001);

        this.gl.activeTexture(this.gl.TEXTURE0);
        this.gl.bindTexture(this.gl.TEXTURE_2D, this.noiseTexture);
        this.gl.uniform1i(this.uniforms.channel0, 0);

        this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);
        this.ctx.drawImage(this.glCanvas, 0, 0, this.canvas.width, this.canvas.height);
    }
}

window.MedusesAnimation = MedusesAnimation;
