class ShadertoySinglePassAnimation extends BaseAnimation {
    setup() {
        this.time = 0;
        this.frame = 0;
        this.mouse = { x: 0.5, y: 0.5 };
        this.glCanvas = document.createElement('canvas');
        this.glCanvas.width = this.canvas.width;
        this.glCanvas.height = this.canvas.height;
        this.gl = null;
        this.program = null;
        this.vertexBuffer = null;
        this.uniforms = {};
        this.channelStates = new Array(4).fill(null);
        this.channelResolutionData = new Float32Array(12);
        this.channelDefinitions = [];
        this.shaderLoaded = false;
        this.loadShaderDefinition();
    }

    getShaderAssetPath() {
        return null;
    }

    getChannelDefinitions() {
        return [];
    }

    async loadShaderDefinition() {
        const assetPath = this.getShaderAssetPath();
        if (!assetPath) {
            console.error('ShadertoySinglePassAnimation missing asset path');
            return;
        }

        try {
            const response = await fetch(assetPath);
            const payload = await response.json();
            const shader = Array.isArray(payload) ? payload[0] : payload;
            const commonCode = (shader?.renderpass || [])
                .filter((pass) => pass.type === 'common' && pass.code)
                .map((pass) => pass.code)
                .join('\n');
            const imagePass = shader?.renderpass?.find((pass) => pass.type === 'image');
            if (!imagePass?.code) {
                throw new Error('No image pass found');
            }

            this.channelDefinitions = this.mergeChannelDefinitions(
                this.getAutoChannelDefinitions(imagePass),
                this.getChannelDefinitions()
            );
            this.initWebGL(`${commonCode}\n${imagePass.code}`);
            await this.loadChannels(this.channelDefinitions);
            this.shaderLoaded = true;
        } catch (error) {
            console.error('Failed to load Shadertoy shader asset', assetPath, error);
        }
    }

    getAutoChannelDefinitions(pass) {
        return (pass?.inputs || [])
            .map((input) => this.resolveInputDefinition(input))
            .filter(Boolean);
    }

    mergeChannelDefinitions(autoDefinitions, manualDefinitions) {
        const merged = new Map();
        autoDefinitions.forEach((definition) => {
            merged.set(definition.channel, definition);
        });
        manualDefinitions.forEach((definition) => {
            merged.set(definition.channel, definition);
        });
        return Array.from(merged.values());
    }

    resolveInputDefinition(input) {
        const channel = input?.channel;
        if (channel == null || channel < 0 || channel > 3) {
            return null;
        }

        const sampler = input.sampler || {};
        if (input.type === 'texture') {
            return {
                channel,
                kind: 'image',
                src: this.resolveMediaSource(input.filepath),
                fallbackSrc: this.resolveRemoteSource(input.filepath),
                filter: this.normalizeSamplerFilter(sampler.filter),
                wrap: this.normalizeSamplerWrap(sampler.wrap),
                vflip: this.normalizeSamplerBoolean(sampler.vflip),
            };
        }

        if (input.type === 'music' || input.type === 'musicstream' || input.type === 'mic') {
            return {
                channel,
                kind: 'audio',
                filter: this.normalizeSamplerFilter(sampler.filter),
                wrap: this.normalizeSamplerWrap(sampler.wrap),
                seed: channel + 1.37,
            };
        }

        if (input.type === 'keyboard') {
            return {
                channel,
                kind: 'keyboard',
            };
        }

        return null;
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

    initWebGL(shaderCode) {
        this.gl =
            this.glCanvas.getContext('webgl2', { alpha: false, antialias: true }) ||
            this.glCanvas.getContext('webgl2');

        if (!this.gl) {
            console.error('ShadertoySinglePassAnimation requires WebGL2');
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
            uniform vec3 iResolution;
            uniform float iTime;
            uniform vec4 iMouse;
            uniform int iFrame;
            uniform sampler2D iChannel0;
            uniform sampler2D iChannel1;
            uniform sampler2D iChannel2;
            uniform sampler2D iChannel3;
            uniform vec3 iChannelResolution[4];
            ${shaderCode}
            void main() {
                mainImage(fragColor, gl_FragCoord.xy);
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
            console.error('ShadertoySinglePassAnimation link error:', this.gl.getProgramInfoLog(this.program));
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
            mouse: this.gl.getUniformLocation(this.program, 'iMouse'),
            frame: this.gl.getUniformLocation(this.program, 'iFrame'),
            channelResolution: this.gl.getUniformLocation(this.program, 'iChannelResolution[0]'),
            channels: [0, 1, 2, 3].map((index) => this.gl.getUniformLocation(this.program, `iChannel${index}`)),
        };

        this.ensureFallbackChannels();
    }

    createShader(source, type) {
        const shader = this.gl.createShader(type);
        this.gl.shaderSource(shader, source);
        this.gl.compileShader(shader);
        if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
            console.error('ShadertoySinglePassAnimation shader error:', this.gl.getShaderInfoLog(shader));
            this.gl.deleteShader(shader);
            return null;
        }
        return shader;
    }

    ensureFallbackChannels() {
        for (let channel = 0; channel < 4; channel += 1) {
            if (this.channelStates[channel]) {
                continue;
            }
            this.channelStates[channel] = this.createDataTexture(1, 1, new Uint8Array([0, 0, 0, 255]), {
                filter: 'linear',
                wrap: 'clamp',
                dynamic: false,
            });
        }
    }

    async loadChannels(channelDefinitions = this.channelDefinitions) {
        if (!this.gl || !channelDefinitions.length) {
            this.ensureFallbackChannels();
            return;
        }

        await Promise.all(
            channelDefinitions.map((definition) =>
                this.loadChannel(definition).catch((error) => {
                    console.warn('Failed to load Shadertoy channel', definition, error);
                })
            )
        );
        this.ensureFallbackChannels();
    }

    async loadChannel(definition) {
        const channel = definition.channel;
        if (channel == null || channel < 0 || channel > 3) {
            return;
        }

        if (definition.kind === 'image') {
            this.channelStates[channel] = await this.loadImageChannel(definition);
            return;
        }

        if (definition.kind === 'audio') {
            this.channelStates[channel] = this.createAudioTexture(definition);
            return;
        }

        if (definition.kind === 'keyboard') {
            this.channelStates[channel] = this.createKeyboardTexture();
        }
    }

    async loadImageChannel(definition) {
        const image = await this.loadImageWithFallback(definition.src, definition.fallbackSrc);

        const texture = this.gl.createTexture();
        this.gl.bindTexture(this.gl.TEXTURE_2D, texture);
        this.gl.pixelStorei(this.gl.UNPACK_FLIP_Y_WEBGL, definition.vflip ? 1 : 0);
        this.gl.texImage2D(this.gl.TEXTURE_2D, 0, this.gl.RGBA, this.gl.RGBA, this.gl.UNSIGNED_BYTE, image);
        this.configureSampler(definition);
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

    createAudioTexture(definition) {
        const width = definition.width || 512;
        const height = definition.height || 2;
        const data = new Uint8Array(width * height * 4);
        const textureState = this.createDataTexture(width, height, data, {
            filter: definition.filter || 'linear',
            wrap: definition.wrap || 'clamp',
            dynamic: true,
        });
        textureState.audioSeed = definition.seed || 0;
        return textureState;
    }

    createKeyboardTexture() {
        return this.createDataTexture(256, 3, new Uint8Array(256 * 3 * 4), {
            filter: 'nearest',
            wrap: 'clamp',
            dynamic: false,
        });
    }

    createDataTexture(width, height, data, options = {}) {
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

    bindChannels() {
        this.channelResolutionData.fill(1);
        for (let channel = 0; channel < 4; channel += 1) {
            const channelState = this.channelStates[channel];
            if (!channelState) {
                continue;
            }
            if (channelState.dynamic) {
                this.updateAudioTexture(channelState);
            }

            this.gl.activeTexture(this.gl.TEXTURE0 + channel);
            this.gl.bindTexture(this.gl.TEXTURE_2D, channelState.texture);
            if (this.uniforms.channels[channel]) {
                this.gl.uniform1i(this.uniforms.channels[channel], channel);
            }

            const baseIndex = channel * 3;
            this.channelResolutionData[baseIndex] = channelState.width || 1;
            this.channelResolutionData[baseIndex + 1] = channelState.height || 1;
            this.channelResolutionData[baseIndex + 2] = 1;
        }

        if (this.uniforms.channelResolution) {
            this.gl.uniform3fv(this.uniforms.channelResolution, this.channelResolutionData);
        }
    }

    draw() {
        if (!this.shaderLoaded || !this.gl || !this.program) {
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
        this.gl.uniform3f(this.uniforms.resolution, this.glCanvas.width, this.glCanvas.height, 1.0);
        this.gl.uniform1f(this.uniforms.time, this.time * 0.001);
        this.gl.uniform4f(this.uniforms.mouse, this.mouse.x, this.mouse.y, this.mouse.x, this.mouse.y);
        if (this.uniforms.frame) {
            this.gl.uniform1i(this.uniforms.frame, this.frame);
        }
        this.bindChannels();
        this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);
        this.ctx.drawImage(this.glCanvas, 0, 0, this.canvas.width, this.canvas.height);
        this.frame += 1;
    }
}

window.ShadertoySinglePassAnimation = ShadertoySinglePassAnimation;
