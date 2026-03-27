class TrainUpInTheCloudSeaAnimation extends BaseAnimation {
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
            console.error('TrainUpInTheCloudSeaAnimation requires WebGL2');
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

            float noise(vec2 x){
                vec2 f = fract(x);
                vec2 u = f*f*f*(f*(f*6.0-15.0)+10.0);
                vec2 p = floor(x);
                float a = texture(iChannel0, (p+vec2(0.0, 0.0))/1024.0).x;
                float b = texture(iChannel0, (p+vec2(1.0,0.0))/1024.0).x;
                float c = texture(iChannel0, (p+vec2(0.0,1.0))/1024.0).x;
                float d = texture(iChannel0, (p+vec2(1.0,1.0))/1024.0).x;
                return a+(b-a)*u.x+(c-a)*u.y+(a-b-c+d)*u.x*u.y;
            }

            float fbm(vec2 x, int detail){
                float a = 0.0;
                float b = 1.0;
                float t = 0.0;
                for(int i = 0; i < detail; i++){
                    float n = noise(x);
                    a += b*n;
                    t += b;
                    b *= 0.7;
                    x *= 2.0;
                }
                return a/t;
            }

            float fbm2(vec2 x, int detail){
                float a = 0.0;
                float b = 1.0;
                float t = 0.0;
                for(int i = 0; i < detail; i++){
                    float n = noise(x);
                    a += b*n;
                    t += b;
                    b *= 0.9;
                    x *= 2.0;
                }
                return a/t;
            }

            float box(vec2 uv, float x1, float x2, float y1, float y2){
                return (uv.x > x1 && uv.x < x2 && uv.y > y1 && uv.y < y2)?1.0:0.0;
            }

            #define dot2(v) dot(v, v)
            #define layer(dh, v) if (uv.y < h + midlevel - (dh) ) return vec4(v, 1.0);

            vec4 foreground(vec2 uv, float t){
                float midlevel;
                float h;
                float disp;
                float dist;
                vec2 uv2;

                uv.y -= 0.2;

                midlevel = -0.1;
                disp = 1.7;
                dist = 1.0;
                uv2 = uv + vec2(t/dist + 40.0, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.12, vec3(0.43, 0.32, 0.31));
                layer(0.08, vec3(0.55, 0.42, 0.41));
                layer(0.04, vec3(0.66, 0.42, 0.40));
                layer(0.0, vec3(0.77, 0.48, 0.46));

                midlevel = 0.05;
                disp = 1.7;
                dist = 2.0;
                uv2 = uv + vec2(t/dist + 38.0, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.1, vec3(0.95, 0.66, 0.48));
                layer(0.04, vec3(0.98, 0.76, 0.64));
                layer(0.0, vec3(0.95, 0.80, 0.77));

                return vec4(0.95, 0.80, 0.77, 0.0);
            }

            vec4 backgroundLayer(vec2 uv, float t){
                float midlevel;
                float h;
                float disp;
                float dist;
                vec2 uv2;

                midlevel = 0.3;
                disp = 0.9;
                dist = 10.0;
                uv2 = uv + vec2(t/dist + 32.5, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.14, vec3(0.48, 0.19, 0.20));
                layer(0.1, vec3(0.68, 0.28, 0.19));
                layer(0.07, vec3(0.88, 0.38, 0.24));
                layer(0.0, vec3(0.95, 0.45, 0.30));

                midlevel = 0.35;
                disp = 1.0;
                dist = 15.0;
                uv2 = uv + vec2(t/dist + 30.0, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.04, vec3(0.98, 0.76, 0.64));
                layer(0.0, vec3(0.95, 0.80, 0.77));

                midlevel = 0.35;
                disp = 3.5;
                dist = 20.0;
                uv2 = uv + vec2(t/dist + 27.5, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.12, vec3(0.43, 0.32, 0.31));
                layer(0.08, vec3(0.55, 0.42, 0.41));
                layer(0.04, vec3(0.66, 0.42, 0.40));
                layer(0.0, vec3(0.77, 0.48, 0.46));

                midlevel = 0.45;
                disp = 2.0;
                dist = 25.0;
                uv2 = uv + vec2(t/dist + 23.0, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.04, vec3(0.98, 0.57, 0.36));
                layer(0.0, vec3(1.0, 0.62, 0.44));

                midlevel = 0.5;
                disp = 2.3;
                dist = 30.0;
                uv2 = uv + vec2(t/dist + 20.5, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.12, vec3(0.41, 0.27, 0.27));
                layer(0.08, vec3(0.53, 0.35, 0.32));
                layer(0.04, vec3(0.80, 0.24, 0.17));
                layer(0.0, vec3(0.99, 0.29, 0.20));

                midlevel = 0.5;
                disp = 2.5;
                dist = 35.0;
                uv2 = uv + vec2(t/dist + 18.0, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.1, vec3(0.88, 0.38, 0.24));
                layer(0.05, vec3(0.98, 0.42, 0.28));
                layer(0.0, vec3(1.0, 0.48, 0.35));

                midlevel = 0.6;
                disp = 2.0;
                dist = 40.0;
                uv2 = uv + vec2(t/dist + 18.0, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.1, vec3(0.95, 0.66, 0.48));
                layer(0.0, vec3(1.0, 0.76, 0.60));

                midlevel = 0.75;
                disp = 3.5;
                dist = 45.0;
                uv2 = uv + vec2(t/dist + 15.5, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.2, vec3(1.0, 0.55, 0.33));
                layer(0.15, vec3(0.98, 0.50, 0.24));
                layer(0.1, vec3(0.90, 0.55, 0.40));
                layer(0.0, vec3(1.0, 0.62, 0.44));

                midlevel = 0.7;
                disp = 2.7;
                dist = 50.0;
                uv2 = uv + vec2(t/dist + 12.0, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.04, vec3(0.73, 0.36, 0.30));
                layer(0.0, vec3(0.80, 0.40, 0.34));

                midlevel = 0.8;
                disp = 2.7;
                dist = 60.0;
                uv2 = uv + vec2(t/dist + 9.5, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.1, vec3(0.93, 0.58, 0.35));
                layer(0.0, vec3(1.0, 0.76, 0.60));

                midlevel = 0.9;
                disp = 3.0;
                dist = 70.0;
                uv2 = uv + vec2(t/dist + 7.0, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.1, vec3(0.56, 0.25, 0.22));
                layer(0.05, vec3(0.60, 0.30, 0.27));
                layer(0.0, vec3(0.74, 0.35, 0.30));

                midlevel = 1.0;
                disp = 5.0;
                dist = 100.0;
                uv2 = uv + vec2(t/dist + 3.5, 0.0);
                h = (fbm(uv2, 8) - 0.5)*disp;
                layer(0.1, vec3(0.92, 0.85, 0.82));
                layer(0.0, vec3(1.0, 0.94, 0.91));

                return vec4(0.58, 0.7, 1.0, 1.0);
            }

            void main() {
                vec2 fragCoord = gl_FragCoord.xy;
                vec2 uv = fragCoord / iResolution.y;
                float t = iTime * 4.0;
                vec4 bg = backgroundLayer(uv, t);

                vec4 fg = vec4(0.0);
                const int n = 5;
                if (uv.y < 0.5) {
                    for (int i = 0; i < n; i++) {
                        fg += foreground(uv, t + 4.0 * float(i) / float(n) / 60.0) / float(n);
                    }
                }

                vec3 col = bg.rgb;
                float k;
                float h;
                float dist;
                vec2 uv2;
                uv.y -= 0.2;

                k = 1.0;
                uv2 = fract(uv * 9.0);
                float wagon = 1.0;
                wagon *= 1.0 - step(0.45, uv.x);
                wagon *= 1.0 - step(0.115, uv.y);
                wagon *= step(0.103, uv.y);
                wagon *= step(0.05, 1.0 - abs(uv2.x * 2.0 - 1.0));

                float join = 1.0;
                join *= 1.0 - step(0.45, uv.x);
                join *= 1.0 - step(0.11, uv.y);
                join *= step(0.107, uv.y);

                float roof = 1.0;
                roof *= 1.0 - step(0.45, uv.x);
                roof *= 1.0 - step(0.117, uv.y);
                roof *= step(0.11, uv.y);
                roof *= step(0.15, 1.0 - abs(uv2.x * 2.0 - 1.0));

                float loco = box(uv, 0.45, 0.5, 0.103, 0.112);
                float chem1 = box(uv, 0.49, 0.495, 0.103, 0.12);
                float chem2 = box(uv, 0.488, 0.496, 0.12, 0.123);
                float locoRoof = box(uv, 0.443, 0.47, 0.11, 0.117);

                float wheel = 1.0 - step(0.00004, dot2(uv - vec2(0.457, 0.106)));
                wheel += 1.0 - step(0.00002, dot2(uv - vec2(0.487, 0.105)));
                wheel += 1.0 - step(0.00002, dot2(uv - vec2(0.497, 0.105)));

                if (uv.x < 0.45 && uv.y > 0.025 && uv.y < 0.2) {
                    wheel += 1.0 - step(0.002, dot2(uv2 - vec2(0.2, 0.95)));
                    wheel += 1.0 - step(0.002, dot2(uv2 - vec2(0.8, 0.95)));
                }

                col = mix(col, vec3(0.18, 0.12, 0.15), join);
                col = mix(col, vec3(0.48, 0.19, 0.20), wagon);
                col = mix(col, vec3(0.18, 0.12, 0.15), roof);
                col = mix(col, vec3(0.38, 0.19, 0.20), loco);
                col = mix(col, vec3(0.38, 0.19, 0.20), chem1);
                col = mix(col, vec3(0.18, 0.12, 0.15), locoRoof);
                col = mix(col, vec3(0.18, 0.12, 0.15), chem2 + wheel);

                dist = 5.0;
                uv2 = uv + vec2(t / dist + 3.5, 0.0);
                uv2.x -= t / dist * 0.2;
                h = fbm2(uv2, 8) - 0.55;

                if (uv.x < 0.49) {
                    float x = -uv.x + 0.49;
                    float y = abs(uv.y + h * 0.4 - 0.16 * sqrt(x) - 0.12) - 0.8 * x * exp(-x * 10.0);
                    if (y < 0.0) col = vec3(1.0, 0.94, 0.91);
                    if (y < -0.02) col = vec3(0.92, 0.85, 0.82);
                }

                dist = 5.0;
                uv2 = uv + vec2(t / dist + 32.5, 0.0);
                uv2.x = fract(uv2.x * 3.0);
                k = 1.0;
                k *= smoothstep(0.001, 0.003, abs(uv2.y - pow(uv2.x - 0.5, 2.0) * 0.15 - 0.12));
                k *= min(step(0.05, 1.0 - abs(uv2.x * 2.0 - 1.0)) + step(0.17, uv2.y), 1.0);
                k *= min(smoothstep(0.02, 0.05, 1.0 - abs(uv2.x * 2.0 - 1.0)) + step(0.177, uv2.y), 1.0);
                k *= min(
                    step(0.1, uv2.y) + smoothstep(-0.09, -0.085, -uv2.y - 0.001 / (1.0 - abs(uv2.x * 2.0 - 1.0))),
                    1.0
                );
                k *= min(
                    smoothstep(0.05, 0.2, 1.0 - abs(fract(uv2.x * 16.0) * 2.0 - 1.0)) +
                    step(0.12, uv2.y - pow(uv2.x - 0.5, 2.0) * 0.15) +
                    step(-0.1, -uv2.y),
                    1.0
                );
                col = mix(vec3(0.29, 0.09, 0.08) * smoothstep(-0.08, 0.08, uv.y), col, k);

                col = mix(col, fg.rgb, fg.a);

                vec2 vignetteUv = fragCoord / iResolution.xy;
                col *= 0.5 + 0.5 * pow(16.0 * vignetteUv.x * vignetteUv.y * (1.0 - vignetteUv.x) * (1.0 - vignetteUv.y), 0.2);
                fragColor = vec4(col, 1.0);
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
            console.error('TrainUpInTheCloudSeaAnimation link error:', this.gl.getProgramInfoLog(this.program));
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
            console.error('TrainUpInTheCloudSeaAnimation shader error:', this.gl.getShaderInfoLog(shader));
            this.gl.deleteShader(shader);
            return null;
        }

        return shader;
    }

    createNoiseTexture() {
        const size = 1024;
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

window.TrainUpInTheCloudSeaAnimation = TrainUpInTheCloudSeaAnimation;
