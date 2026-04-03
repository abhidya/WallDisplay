class ShadertoyMultiPassAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.frame = 0;
        this.mouse = { x: 0, y: 0, down: 0 };
        this.shaderLoaded = false;
        this.gl = null;
        this.channelResolution = new Float32Array(12);
        this.workSize = this.getWorkSize();
        this.glCanvas = document.createElement('canvas');
        this.glCanvas.width = this.workSize;
        this.glCanvas.height = this.workSize;
        this.passDescriptors = [];
        this.bufferTargets = new Map();
        this.externalTextures = new Map();
        this.manualExternalDefinitions = {};
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

        this.keyboardTexture = this.createByteTexture(256, 3, new Uint8Array(256 * 3 * 4), {
            filter: 'nearest',
            wrap: 'clamp',
        });
        this.fallbackTexture = this.createByteTexture(1, 1, new Uint8Array([0, 0, 0, 255]), {
            filter: 'linear',
            wrap: 'clamp',
        });
    }

    async buildRuntime(shader) {
        const commonCode = (shader.renderpass || [])
            .filter((pass) => pass.type === 'common' && pass.code)
            .map((pass) => pass.code)
            .join('\n');

        this.manualExternalDefinitions = this.getExternalChannelDefinitions() || {};
        this.externalTextures = await this.loadExternalTextures(shader);
        this.passDescriptors = [];
        this.bufferTargets = new Map();

        (shader.renderpass || []).forEach((pass, index) => {
            if (!pass?.code || pass.type === 'common') {
                return;
            }
            if (pass.type !== 'buffer' && pass.type !== 'image') {
                return;
            }

            const built = this.createProgram(commonCode, pass.code);
            const descriptor = {
                pass,
                index,
                program: built.program,
                uniforms: built.uniforms,
            };

            if (pass.type === 'buffer') {
                const output = (pass.outputs || [])[0];
                if (!output?.id) {
                    throw new Error(`Buffer pass missing output id at index ${index}`);
                }
                this.bufferTargets.set(
                    output.id,
                    this.createPingPongTarget(this.workSize, this.workSize, {
                        floatTexture: true,
                        filter: 'nearest',
                    })
                );
                descriptor.targetId = output.id;
            }

            this.passDescriptors.push(descriptor);
        });

        if (!this.passDescriptors.some((descriptor) => descriptor.pass.type === 'image')) {
            throw new Error('No image pass found');
        }
    }

    async loadExternalTextures(shader) {
        const definitions = this.getExternalInputDefinitions(shader);
        const entries = await Promise.all(
            definitions.map(async (definition) => {
                try {
                    return [definition.key, await this.loadExternalTexture(definition)];
                } catch (error) {
                    console.warn('Failed to load Shadertoy external input', definition, error);
                    return [definition.key, this.fallbackTexture];
                }
            })
        );

        return new Map(entries);
    }

    getExternalInputDefinitions(shader) {
        const seen = new Set();
        const definitions = [];

        (shader.renderpass || []).forEach((pass) => {
            (pass.inputs || []).forEach((input) => {
                if (input.type === 'buffer') {
                    return;
                }
                const definition = this.resolveInputDefinition(input);
                if (!definition || seen.has(definition.key)) {
                    return;
                }
                seen.add(definition.key);
                definitions.push(definition);
            });
        });

        return definitions;
    }

    resolveInputDefinition(input) {
        const key = this.getInputKey(input);
        const override = this.lookupExternalDefinition(input);
        const sampler = input.sampler || {};
        const filter = override?.filter || this.normalizeSamplerFilter(sampler.filter);
        const wrap = override?.wrap || this.normalizeSamplerWrap(sampler.wrap);
        const vflip = override?.vflip ?? this.normalizeSamplerBoolean(sampler.vflip);

        if (override?.kind === 'image' || (!override?.kind && input.type === 'texture')) {
            return {
                key,
                kind: 'image',
                src: override?.src || this.resolveMediaSource(input.filepath),
                fallbackSrc: override?.fallbackSrc || this.resolveRemoteSource(input.filepath),
                filter,
                wrap,
                vflip,
            };
        }

        if (override?.kind === 'audio' || input.type === 'music' || input.type === 'musicstream' || input.type === 'mic') {
            return {
                key,
                kind: 'audio',
                filter,
                wrap,
                seed: override?.seed || input.channel + 1.37,
                width: override?.width,
                height: override?.height,
            };
        }

        if (override?.kind === 'keyboard' || input.type === 'keyboard') {
            return {
                key,
                kind: 'keyboard',
            };
        }

        return null;
    }

    lookupExternalDefinition(input) {
        const definitions = this.manualExternalDefinitions || {};
        const filepath = input?.filepath || '';
        const basename = filepath ? filepath.split('/').pop() : '';
        const keys = [input?.id, filepath, basename, String(input?.channel)]
            .filter(Boolean);

        for (const key of keys) {
            if (definitions[key]) {
                return definitions[key];
            }
        }

        const values = Object.values(definitions);
        if (values.length === 1 && input?.type === 'texture') {
            return values[0];
        }

        return null;
    }

    getInputKey(input) {
        return input?.id || `${input?.type || 'unknown'}:${input?.filepath || input?.channel || 'na'}`;
    }

    resolveMediaSource(filepath) {
        if (!filepath) {
            return null;
        }
        if (/^https?:\/\//.test(filepath)) {
            return filepath;
        }
        const filename = filepath.split('/').pop();
        return filename ? `/backend-static/assets/shadertoy/media/${filename}` : null;
    }

    resolveRemoteSource(filepath) {
        if (!filepath || /^https?:\/\//.test(filepath) || filepath.startsWith('/presets/')) {
            return null;
        }
        return `https://www.shadertoy.com${filepath}`;
    }

    normalizeSamplerFilter(filter) {
        if (filter === 'nearest' || filter === 'mipmap') {
            return filter;
        }
        return 'linear';
    }

    normalizeSamplerWrap(wrap) {
        return wrap === 'repeat' ? 'repeat' : 'clamp';
    }

    normalizeSamplerBoolean(value) {
        return value === true || value === 'true' || value === 1 || value === '1';
    }

    async loadExternalTexture(definition) {
        if (definition.kind === 'image') {
            return this.loadImageTexture(definition);
        }
        if (definition.kind === 'audio') {
            return this.createAudioTexture(definition);
        }
        if (definition.kind === 'keyboard') {
            return this.keyboardTexture;
        }
        return this.fallbackTexture;
    }

    async loadImageTexture(definition) {
        const image = await this.loadImageWithFallback(definition.src, definition.fallbackSrc);

        const texture = this.gl.createTexture();
        this.gl.bindTexture(this.gl.TEXTURE_2D, texture);
        this.gl.pixelStorei(this.gl.UNPACK_FLIP_Y_WEBGL, definition.vflip ? 1 : 0);
        this.gl.texImage2D(this.gl.TEXTURE_2D, 0, this.gl.RGBA, this.gl.RGBA, this.gl.UNSIGNED_BYTE, image);
        this.configureSampler({
            filter: definition.filter,
            wrap: definition.wrap,
        });
        if (definition.filter === 'mipmap') {
            this.gl.generateMipmap(this.gl.TEXTURE_2D);
        }
        this.gl.pixelStorei(this.gl.UNPACK_FLIP_Y_WEBGL, 0);

        return {
            texture,
            width: image.width,
            height: image.height,
            dynamic: false,
        };
    }

    loadImageWithFallback(src, fallbackSrc) {
        const attempt = (candidate) =>
            new Promise((resolve, reject) => {
                if (!candidate) {
                    reject(new Error('Missing image source'));
                    return;
                }
                const element = new Image();
                if (/^https?:\/\//.test(candidate)) {
                    element.crossOrigin = 'anonymous';
                }
                element.onload = () => resolve(element);
                element.onerror = () => reject(new Error(`Failed to load ${candidate}`));
                element.src = candidate;
            });

        return attempt(src).catch((error) => {
            if (!fallbackSrc || fallbackSrc === src) {
                throw error;
            }
            return attempt(fallbackSrc);
        });
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
            data,
            dynamic: Boolean(options.dynamic),
        };
    }

    createAudioTexture(definition) {
        const width = definition.width || 512;
        const height = definition.height || 2;
        const data = new Uint8Array(width * height * 4);
        const textureState = this.createByteTexture(width, height, data, {
            filter: definition.filter || 'linear',
            wrap: definition.wrap || 'clamp',
            dynamic: true,
        });
        textureState.audioSeed = definition.seed || 0;
        return textureState;
    }

    updateAudioTexture(channelState) {
        if (!channelState?.dynamic || !channelState.data) {
            return;
        }

        const { width, height, data } = channelState;
        const time = this.time * 0.001;
        for (let x = 0; x < width; x += 1) {
            const phase = (x / width) * Math.PI * 2;
            const waveform = 0.5 + 0.5 * Math.sin(phase * 6 + time * 2 + channelState.audioSeed);
            const fft = 0.5 + 0.5 * Math.sin(phase * 2 + time * 0.75 + channelState.audioSeed * 0.5);
            for (let y = 0; y < height; y += 1) {
                const index = (y * width + x) * 4;
                const value = y === 0 ? fft : waveform;
                const byteValue = Math.max(0, Math.min(255, Math.round(value * 255)));
                data[index] = byteValue;
                data[index + 1] = byteValue;
                data[index + 2] = byteValue;
                data[index + 3] = 255;
            }
        }

        this.gl.bindTexture(this.gl.TEXTURE_2D, channelState.texture);
        this.gl.texSubImage2D(
            this.gl.TEXTURE_2D,
            0,
            0,
            0,
            width,
            height,
            this.gl.RGBA,
            this.gl.UNSIGNED_BYTE,
            data
        );
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
            const input = inputs[channel] || this.fallbackTexture;
            const texture = input.texture || input;
            const width = input.width || 1;
            const height = input.height || 1;

            if (input.dynamic) {
                this.updateAudioTexture(input);
            }

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

    resolvePassInputs(pass) {
        const inputs = {};
        (pass.inputs || []).forEach((input) => {
            const channel = input.channel;
            if (channel == null || channel < 0 || channel > 3) {
                return;
            }

            if (input.type === 'buffer') {
                const target = this.bufferTargets.get(input.id);
                if (target?.read) {
                    inputs[channel] = target.read;
                }
                return;
            }

            if (input.type === 'keyboard') {
                inputs[channel] = this.keyboardTexture;
                return;
            }

            const external = this.externalTextures.get(this.getInputKey(input));
            if (external) {
                inputs[channel] = external;
            }
        });

        return inputs;
    }

    renderPass(descriptor, target, inputs) {
        const { program, uniforms } = descriptor;
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

    drawFinalPass(descriptor, inputs) {
        const { program, uniforms } = descriptor;
        this.gl.useProgram(program);
        this.gl.uniform3f(uniforms.resolution, this.glCanvas.width, this.glCanvas.height, 1.0);
        this.gl.uniform1f(uniforms.time, this.time * 0.001);
        this.gl.uniform4f(uniforms.mouse, this.mouse.x, this.mouse.y, this.mouse.down, 0.0);
        this.gl.uniform1i(uniforms.frame, this.frame);
        this.bindPassInputs(uniforms, inputs);
        this.gl.bindFramebuffer(this.gl.FRAMEBUFFER, null);
        this.gl.viewport(0, 0, this.glCanvas.width, this.glCanvas.height);
        this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);
    }

    draw() {
        if (!this.shaderLoaded || !this.gl || !this.passDescriptors.length) {
            this.ctx.fillStyle = '#000';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            return;
        }

        this.time += 16;
        this.gl.clearColor(0, 0, 0, 1);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);

        this.passDescriptors.forEach((descriptor) => {
            const inputs = this.resolvePassInputs(descriptor.pass);
            if (descriptor.pass.type === 'buffer') {
                const target = this.bufferTargets.get(descriptor.targetId);
                if (target?.write) {
                    this.renderPass(descriptor, target.write, inputs);
                }
                return;
            }
            this.drawFinalPass(descriptor, inputs);
        });

        this.bufferTargets.forEach((target) => {
            [target.read, target.write] = [target.write, target.read];
        });
        this.frame += 1;
        this.ctx.drawImage(this.glCanvas, 0, 0, this.canvas.width, this.canvas.height);
    }
}

window.ShadertoyMultiPassAnimation = ShadertoyMultiPassAnimation;
