class ShadertoyMultiPassAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.frame = 0;
        this.mouse = { x: 0, y: 0, down: 0 };
        this.shaderLoaded = false;
        this.gl = null;
        this.programs = {};
        this.targets = {};
        this.uniformLocations = {};
        this.channelResolution = new Float32Array(12);
        this.workSize = this.getWorkSize();
        this.glCanvas = document.createElement('canvas');
        this.glCanvas.width = this.workSize;
        this.glCanvas.height = this.workSize;
        this.setupPointerTracking();
        this.loadShaderDefinition();
    }

    getShaderAssetPath() {
        return null;
    }

    getWorkSize() {
        return 720;
    }

    getExternalChannelDefinitions() {
        return {};
    }

    setupPointerTracking() {
        const update = (event) => {
            const rect = this.canvas.getBoundingClientRect();
            const x = ((event.clientX - rect.left) / rect.width) * this.workSize;
            const y = this.workSize - ((event.clientY - rect.top) / rect.height) * this.workSize;
            this.mouse.x = x;
            this.mouse.y = y;
        };

        this.canvas.addEventListener('pointerdown', (event) => {
            update(event);
            this.mouse.down = 1;
        });
        this.canvas.addEventListener('pointermove', update);
        const reset = () => {
            this.mouse.down = 0;
        };
        this.canvas.addEventListener('pointerup', reset);
        this.canvas.addEventListener('pointerleave', reset);
    }

    async loadShaderDefinition() {
        const assetPath = this.getShaderAssetPath();
        if (!assetPath) {
            console.error('ShadertoyMultiPassAnimation missing asset path');
            return;
        }

        try {
            const response = await fetch(assetPath);
            const payload = await response.json();
            const shader = Array.isArray(payload) ? payload[0] : payload;
            if (!shader?.renderpass?.length) {
                throw new Error('No render passes found');
            }

            this.initWebGL();
            await this.buildRuntime(shader);
            this.shaderLoaded = true;
        } catch (error) {
            console.error('Failed to load Shadertoy multipass shader', assetPath, error);
        }
    }

    initWebGL() {
        this.gl =
            this.glCanvas.getContext('webgl2', { alpha: false, antialias: false }) ||
            this.glCanvas.getContext('webgl2');
        if (!this.gl) {
            throw new Error('ShadertoyMultiPassAnimation requires WebGL2');
        }

        const floatExt = this.gl.getExtension('EXT_color_buffer_float');
        if (!floatExt) {
            throw new Error('EXT_color_buffer_float is required for multipass Shadertoy animations');
        }

        this.vertexBuffer = this.gl.createBuffer();
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.vertexBuffer);
        this.gl.bufferData(
            this.gl.ARRAY_BUFFER,
            new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
            this.gl.STATIC_DRAW
        );

        this.keyboardTexture = this.createByteTexture(256, 3, null, {
            filter: 'linear',
            wrap: 'clamp',
        });
    }

    async buildRuntime(shader) {
        const commonCode = (shader.renderpass.find((pass) => pass.type === 'common')?.code || '');
        const passMap = {};
        shader.renderpass.forEach((pass) => {
            passMap[pass.name || pass.type] = pass;
        });

        this.externalTextures = await this.loadExternalTextures();
        this.targets = {
            A: this.createPingPongTarget(this.workSize, this.workSize, { floatTexture: true, filter: 'nearest' }),
            B: this.createPingPongTarget(this.workSize, this.workSize, { floatTexture: true, filter: 'nearest' }),
            C: this.createRenderTarget(this.workSize, this.workSize, { floatTexture: true, filter: 'nearest' }),
            D: this.createRenderTarget(this.workSize, this.workSize, { floatTexture: false, filter: 'linear' }),
        };

        const order = [
            ['A', passMap['Buffer A']],
            ['B', passMap['Buffer B']],
            ['C', passMap['Buffer C']],
            ['D', passMap['Buffer D']],
            ['Image', passMap.Image],
        ];

        order.forEach(([key, pass]) => {
            if (!pass?.code) {
                throw new Error(`Missing pass ${key}`);
            }
            const built = this.createProgram(commonCode, pass.code);
            this.programs[key] = built.program;
            this.uniformLocations[key] = built.uniforms;
        });
    }

    async loadExternalTextures() {
        const definitions = this.getExternalChannelDefinitions();
        const entries = await Promise.all(
            Object.entries(definitions).map(async ([name, def]) => {
                const image = await new Promise((resolve, reject) => {
                    const element = new Image();
                    element.onload = () => resolve(element);
                    element.onerror = reject;
                    element.src = def.src;
                });

                const texture = this.gl.createTexture();
                this.gl.bindTexture(this.gl.TEXTURE_2D, texture);
                this.gl.pixelStorei(this.gl.UNPACK_FLIP_Y_WEBGL, def.vflip ? 1 : 0);
                this.gl.texImage2D(this.gl.TEXTURE_2D, 0, this.gl.RGBA, this.gl.RGBA, this.gl.UNSIGNED_BYTE, image);
                this.configureSampler({
                    filter: def.filter || 'linear',
                    wrap: def.wrap || 'clamp',
                });
                if (def.filter === 'mipmap') {
                    this.gl.generateMipmap(this.gl.TEXTURE_2D);
                }
                this.gl.pixelStorei(this.gl.UNPACK_FLIP_Y_WEBGL, 0);

                return [name, { texture, width: image.width, height: image.height }];
            })
        );

        return Object.fromEntries(entries);
    }

    createProgram(commonCode, shaderCode) {
        const vertexSource = `#version 300 es
            in vec2 a_position;
            void main() {
                gl_Position = vec4(a_position, 0.0, 1.0);
            }
        `;

        const fragmentSource = `#version 300 es
            precision highp float;
            precision highp sampler2D;
            out vec4 fragColor;
            uniform vec3 iResolution;
            uniform float iTime;
            uniform vec4 iMouse;
            uniform int iFrame;
            uniform sampler2D iChannel0;
            uniform sampler2D iChannel1;
            uniform sampler2D iChannel2;
            uniform sampler2D iChannel3;
            uniform vec3 iChannelResolution[4];
            ${commonCode}
            ${shaderCode}
            void main() {
                mainImage(fragColor, gl_FragCoord.xy);
            }
        `;

        const vertexShader = this.compileShader(vertexSource, this.gl.VERTEX_SHADER);
        const fragmentShader = this.compileShader(fragmentSource, this.gl.FRAGMENT_SHADER);
        const program = this.gl.createProgram();
        this.gl.attachShader(program, vertexShader);
        this.gl.attachShader(program, fragmentShader);
        this.gl.linkProgram(program);

        if (!this.gl.getProgramParameter(program, this.gl.LINK_STATUS)) {
            throw new Error(this.gl.getProgramInfoLog(program) || 'Unknown program link error');
        }

        this.gl.useProgram(program);
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.vertexBuffer);
        const positionLocation = this.gl.getAttribLocation(program, 'a_position');
        this.gl.enableVertexAttribArray(positionLocation);
        this.gl.vertexAttribPointer(positionLocation, 2, this.gl.FLOAT, false, 0, 0);

        return {
            program,
            uniforms: {
                resolution: this.gl.getUniformLocation(program, 'iResolution'),
                time: this.gl.getUniformLocation(program, 'iTime'),
                mouse: this.gl.getUniformLocation(program, 'iMouse'),
                frame: this.gl.getUniformLocation(program, 'iFrame'),
                channelResolution: this.gl.getUniformLocation(program, 'iChannelResolution[0]'),
                channels: [0, 1, 2, 3].map((index) => this.gl.getUniformLocation(program, `iChannel${index}`)),
            },
        };
    }

    compileShader(source, type) {
        const shader = this.gl.createShader(type);
        this.gl.shaderSource(shader, source);
        this.gl.compileShader(shader);
        if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
            throw new Error(this.gl.getShaderInfoLog(shader) || 'Shader compilation failed');
        }
        return shader;
    }

    configureSampler(options = {}) {
        const filter = options.filter === 'nearest' ? this.gl.NEAREST : this.gl.LINEAR;
        const minFilter =
            options.filter === 'mipmap'
                ? this.gl.LINEAR_MIPMAP_LINEAR
                : filter;
        const wrap = options.wrap === 'repeat' ? this.gl.REPEAT : this.gl.CLAMP_TO_EDGE;
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_MIN_FILTER, minFilter);
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_MAG_FILTER, filter);
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_WRAP_S, wrap);
        this.gl.texParameteri(this.gl.TEXTURE_2D, this.gl.TEXTURE_WRAP_T, wrap);
    }

    createTexture(width, height, options = {}) {
        const texture = this.gl.createTexture();
        this.gl.bindTexture(this.gl.TEXTURE_2D, texture);
        if (options.floatTexture) {
            this.gl.texImage2D(
                this.gl.TEXTURE_2D,
                0,
                this.gl.RGBA32F,
                width,
                height,
                0,
                this.gl.RGBA,
                this.gl.FLOAT,
                null
            );
        } else {
            this.gl.texImage2D(
                this.gl.TEXTURE_2D,
                0,
                this.gl.RGBA8,
                width,
                height,
                0,
                this.gl.RGBA,
                this.gl.UNSIGNED_BYTE,
                null
            );
        }
        this.configureSampler(options);
        return texture;
    }

    createByteTexture(width, height, data, options = {}) {
        const texture = this.gl.createTexture();
        this.gl.bindTexture(this.gl.TEXTURE_2D, texture);
        this.gl.texImage2D(
            this.gl.TEXTURE_2D,
            0,
            this.gl.RGBA,
            width,
            height,
            0,
            this.gl.RGBA,
            this.gl.UNSIGNED_BYTE,
            data
        );
        this.configureSampler(options);
        return {
            texture,
            width,
            height,
        };
    }

    createFramebuffer(texture) {
        const framebuffer = this.gl.createFramebuffer();
        this.gl.bindFramebuffer(this.gl.FRAMEBUFFER, framebuffer);
        this.gl.framebufferTexture2D(this.gl.FRAMEBUFFER, this.gl.COLOR_ATTACHMENT0, this.gl.TEXTURE_2D, texture, 0);
        return framebuffer;
    }

    createRenderTarget(width, height, options = {}) {
        const texture = this.createTexture(width, height, options);
        const framebuffer = this.createFramebuffer(texture);
        return { texture, framebuffer, width, height };
    }

    createPingPongTarget(width, height, options = {}) {
        const read = this.createRenderTarget(width, height, options);
        const write = this.createRenderTarget(width, height, options);
        return { read, write };
    }

    bindPassInputs(uniforms, inputs) {
        this.channelResolution.fill(1);
        for (let channel = 0; channel < 4; channel += 1) {
            const input = inputs[channel] || this.keyboardTexture;
            const texture = input.texture || input;
            const width = input.width || 1;
            const height = input.height || 1;

            this.gl.activeTexture(this.gl.TEXTURE0 + channel);
            this.gl.bindTexture(this.gl.TEXTURE_2D, texture);
            if (uniforms.channels[channel]) {
                this.gl.uniform1i(uniforms.channels[channel], channel);
            }

            const baseIndex = channel * 3;
            this.channelResolution[baseIndex] = width;
            this.channelResolution[baseIndex + 1] = height;
            this.channelResolution[baseIndex + 2] = 1;
        }

        if (uniforms.channelResolution) {
            this.gl.uniform3fv(uniforms.channelResolution, this.channelResolution);
        }
    }

    renderPass(key, target, inputs) {
        const program = this.programs[key];
        const uniforms = this.uniformLocations[key];
        this.gl.useProgram(program);
        this.gl.uniform3f(uniforms.resolution, target.width, target.height, 1.0);
        this.gl.uniform1f(uniforms.time, this.time * 0.001);
        this.gl.uniform4f(uniforms.mouse, this.mouse.x, this.mouse.y, this.mouse.down, 0.0);
        this.gl.uniform1i(uniforms.frame, this.frame);
        this.bindPassInputs(uniforms, inputs);
        this.gl.bindFramebuffer(this.gl.FRAMEBUFFER, target.framebuffer);
        this.gl.viewport(0, 0, target.width, target.height);
        this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);
    }

    drawFinalPass(inputs) {
        const program = this.programs.Image;
        const uniforms = this.uniformLocations.Image;
        this.gl.useProgram(program);
        this.gl.uniform3f(uniforms.resolution, this.workSize, this.workSize, 1.0);
        this.gl.uniform1f(uniforms.time, this.time * 0.001);
        this.gl.uniform4f(uniforms.mouse, this.mouse.x, this.mouse.y, this.mouse.down, 0.0);
        this.gl.uniform1i(uniforms.frame, this.frame);
        this.bindPassInputs(uniforms, inputs);
        this.gl.bindFramebuffer(this.gl.FRAMEBUFFER, null);
        this.gl.viewport(0, 0, this.glCanvas.width, this.glCanvas.height);
        this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);
    }

    draw() {
        if (!this.shaderLoaded || !this.gl) {
            this.ctx.fillStyle = '#000';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            return;
        }

        this.time += 16;
        this.gl.clearColor(0, 0, 0, 1);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);

        const previousA = this.targets.A.read;
        const previousB = this.targets.B.read;
        const previousD = this.targets.D;

        this.renderPass('A', this.targets.A.write, {
            0: previousA,
            1: previousB,
            3: previousD,
        });

        this.renderPass('B', this.targets.B.write, {
            0: this.targets.A.write,
            1: previousB,
            3: this.keyboardTexture,
        });

        this.renderPass('C', this.targets.C, {
            0: this.targets.A.write,
            1: this.targets.B.write,
            3: this.keyboardTexture,
        });

        this.renderPass('D', this.targets.D, {
            0: this.targets.C,
            1: this.externalTextures.main,
            3: this.keyboardTexture,
        });

        this.drawFinalPass({
            0: this.targets.D,
            3: this.keyboardTexture,
        });

        [this.targets.A.read, this.targets.A.write] = [this.targets.A.write, this.targets.A.read];
        [this.targets.B.read, this.targets.B.write] = [this.targets.B.write, this.targets.B.read];
        this.frame += 1;

        this.ctx.drawImage(this.glCanvas, 0, 0, this.canvas.width, this.canvas.height);
    }
}

window.ShadertoyMultiPassAnimation = ShadertoyMultiPassAnimation;
