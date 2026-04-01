// Neural Noise Animation - Adapted from https://codepen.io/ksenia-k/pen/vYwgrWv
class NeuralNoiseAnimation extends BaseAnimation {
    setup() {
        // Initialize WebGL context
        this.gl = null;
        this.shaderProgram = null;
        this.uniforms = {};
        this.vertexBuffer = null;
        
        // Animation parameters
        this.time = 0;
        this.hotspots = [];
        
        // Data-driven parameters
        this.noiseIntensity = 1.0;
        this.colorShift = 0;
        
        // For WebGL animations, we need a separate canvas for the WebGL context
        this.glCanvas = document.createElement('canvas');
        this.glCanvas.width = this.canvas.width;
        this.glCanvas.height = this.canvas.height;
        this.renderElement = this.glCanvas;
        
        // Initialize WebGL
        this.initWebGL();
        
        // Create autonomous hotspots
        this.createHotspots();
    }
    
    initWebGL() {
        // Get WebGL context from the dedicated WebGL canvas
        this.gl = this.glCanvas.getContext('webgl') || this.glCanvas.getContext('experimental-webgl');
        
        if (!this.gl) {
            console.error('WebGL not supported');
            return;
        }
        
        // Vertex shader source
        const vsSource = `
            precision mediump float;
            varying vec2 vUv;
            attribute vec2 a_position;
            
            void main() {
                vUv = .5 * (a_position + 1.);
                gl_Position = vec4(a_position, 0.0, 1.0);
            }
        `;
        
        // Fragment shader source - adapted to use multiple hotspots
        const fsSource = `
            precision mediump float;
            
            varying vec2 vUv;
            uniform float u_time;
            uniform float u_ratio;
            uniform vec2 u_hotspot1;
            uniform vec2 u_hotspot2;
            uniform vec2 u_hotspot3;
            uniform float u_intensity;
            uniform float u_color_shift;
            
            vec2 rotate(vec2 uv, float th) {
                return mat2(cos(th), sin(th), -sin(th), cos(th)) * uv;
            }
            
            float neuro_shape(vec2 uv, float t, float p) {
                vec2 sine_acc = vec2(0.);
                vec2 res = vec2(0.);
                float scale = 8.;
                
                for (int j = 0; j < 15; j++) {
                    uv = rotate(uv, 1.);
                    sine_acc = rotate(sine_acc, 1.);
                    vec2 layer = uv * scale + float(j) + sine_acc - t;
                    sine_acc += sin(layer) + 2.4 * p;
                    res += (.5 + .5 * cos(layer)) / scale;
                    scale *= (1.2);
                }
                return res.x + res.y;
            }
            
            void main() {
                vec2 uv = .5 * vUv;
                uv.x *= u_ratio;
                
                // Calculate influence from multiple hotspots
                float p = 0.0;
                
                vec2 h1 = vUv - u_hotspot1;
                h1.x *= u_ratio;
                p += .3 * pow(1. - clamp(length(h1), 0., 1.), 2.);
                
                vec2 h2 = vUv - u_hotspot2;
                h2.x *= u_ratio;
                p += .3 * pow(1. - clamp(length(h2), 0., 1.), 2.);
                
                vec2 h3 = vUv - u_hotspot3;
                h3.x *= u_ratio;
                p += .3 * pow(1. - clamp(length(h3), 0., 1.), 2.);
                
                float t = .001 * u_time;
                vec3 color = vec3(0.);
                
                float noise = neuro_shape(uv, t, p);
                
                noise = 1.2 * pow(noise, 3.) * u_intensity;
                noise += pow(noise, 10.);
                noise = max(.0, noise - .5);
                noise *= (1. - length(vUv - .5));
                
                // Color based on data
                float colorAngle = u_color_shift;
                color = normalize(vec3(
                    .2 + .3 * sin(colorAngle),
                    .5 + .4 * cos(colorAngle),
                    .5 + .5 * sin(colorAngle + 1.57)
                ));
                
                color = color * noise;
                
                gl_FragColor = vec4(color, noise * 0.9);
            }
        `;
        
        // Create shaders
        const vertexShader = this.createShader(vsSource, this.gl.VERTEX_SHADER);
        const fragmentShader = this.createShader(fsSource, this.gl.FRAGMENT_SHADER);
        
        if (!vertexShader || !fragmentShader) return;
        
        // Create shader program
        this.shaderProgram = this.createShaderProgram(vertexShader, fragmentShader);
        if (!this.shaderProgram) return;
        
        // Get uniform locations
        this.uniforms = {
            u_time: this.gl.getUniformLocation(this.shaderProgram, 'u_time'),
            u_ratio: this.gl.getUniformLocation(this.shaderProgram, 'u_ratio'),
            u_hotspot1: this.gl.getUniformLocation(this.shaderProgram, 'u_hotspot1'),
            u_hotspot2: this.gl.getUniformLocation(this.shaderProgram, 'u_hotspot2'),
            u_hotspot3: this.gl.getUniformLocation(this.shaderProgram, 'u_hotspot3'),
            u_intensity: this.gl.getUniformLocation(this.shaderProgram, 'u_intensity'),
            u_color_shift: this.gl.getUniformLocation(this.shaderProgram, 'u_color_shift')
        };
        
        // Create vertex buffer
        const vertices = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
        this.vertexBuffer = this.gl.createBuffer();
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.vertexBuffer);
        this.gl.bufferData(this.gl.ARRAY_BUFFER, vertices, this.gl.STATIC_DRAW);
        
        // Set up attribute
        this.gl.useProgram(this.shaderProgram);
        const positionLocation = this.gl.getAttribLocation(this.shaderProgram, 'a_position');
        this.gl.enableVertexAttribArray(positionLocation);
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.vertexBuffer);
        this.gl.vertexAttribPointer(positionLocation, 2, this.gl.FLOAT, false, 0, 0);
        
        // Set initial uniforms
        this.gl.uniform1f(this.uniforms.u_ratio, this.glCanvas.width / this.glCanvas.height);
        
        // Enable blending for transparency
        this.gl.enable(this.gl.BLEND);
        this.gl.blendFunc(this.gl.SRC_ALPHA, this.gl.ONE_MINUS_SRC_ALPHA);
    }
    
    createShader(source, type) {
        const shader = this.gl.createShader(type);
        this.gl.shaderSource(shader, source);
        this.gl.compileShader(shader);
        
        if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
            console.error('Shader compile error:', this.gl.getShaderInfoLog(shader));
            this.gl.deleteShader(shader);
            return null;
        }
        
        return shader;
    }
    
    createShaderProgram(vertexShader, fragmentShader) {
        const program = this.gl.createProgram();
        this.gl.attachShader(program, vertexShader);
        this.gl.attachShader(program, fragmentShader);
        this.gl.linkProgram(program);
        
        if (!this.gl.getProgramParameter(program, this.gl.LINK_STATUS)) {
            console.error('Shader program link error:', this.gl.getProgramInfoLog(program));
            return null;
        }
        
        return program;
    }
    
    createHotspots() {
        // Create 3 autonomous hotspots that drift around
        for (let i = 0; i < 3; i++) {
            this.hotspots.push({
                x: Math.random(),
                y: Math.random(),
                vx: (Math.random() - 0.5) * 0.001,
                vy: (Math.random() - 0.5) * 0.001,
                phase: Math.random() * Math.PI * 2
            });
        }
    }
    
    updateHotspots() {
        this.hotspots.forEach(hotspot => {
            // Update position
            hotspot.x += hotspot.vx;
            hotspot.y += hotspot.vy;
            
            // Add some organic movement
            hotspot.x += Math.sin(this.time * 0.0001 + hotspot.phase) * 0.0005;
            hotspot.y += Math.cos(this.time * 0.0001 + hotspot.phase) * 0.0005;
            
            // Bounce off edges
            if (hotspot.x < 0 || hotspot.x > 1) {
                hotspot.vx *= -1;
                hotspot.x = Math.max(0, Math.min(1, hotspot.x));
            }
            if (hotspot.y < 0 || hotspot.y > 1) {
                hotspot.vy *= -1;
                hotspot.y = Math.max(0, Math.min(1, hotspot.y));
            }
        });
    }
    
    draw() {
        if (!this.gl || !this.shaderProgram) return;
        
        this.time += 16;
        
        // Update hotspots
        this.updateHotspots();
        
        // Clear WebGL canvas
        this.gl.viewport(0, 0, this.glCanvas.width, this.glCanvas.height);
        this.gl.clearColor(0, 0, 0, 0);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT);
        
        // Update uniforms
        this.gl.useProgram(this.shaderProgram);
        this.gl.uniform1f(this.uniforms.u_time, this.time);
        this.gl.uniform1f(this.uniforms.u_intensity, this.noiseIntensity);
        this.gl.uniform1f(this.uniforms.u_color_shift, this.colorShift);
        
        // Update hotspot positions
        if (this.hotspots.length >= 3) {
            this.gl.uniform2f(this.uniforms.u_hotspot1, this.hotspots[0].x, 1 - this.hotspots[0].y);
            this.gl.uniform2f(this.uniforms.u_hotspot2, this.hotspots[1].x, 1 - this.hotspots[1].y);
            this.gl.uniform2f(this.uniforms.u_hotspot3, this.hotspots[2].x, 1 - this.hotspots[2].y);
        }
        
        // Draw to WebGL canvas
        this.gl.drawArrays(this.gl.TRIANGLE_STRIP, 0, 4);
        
    }
    
    onDataUpdate() {
        if (this.data.weather) {
            // Noise intensity responds to weather conditions
            if (this.data.weather.conditions === 'rain') {
                this.noiseIntensity = 1.5; // More intense during rain
            } else if (this.data.weather.conditions === 'clear') {
                this.noiseIntensity = 0.8; // Calmer in clear weather
            } else {
                this.noiseIntensity = 1.0;
            }
            
            // Color shifts with temperature
            // Map temperature (0-40°C) to color angle (0-2π)
            this.colorShift = (this.data.weather.temperature / 40) * Math.PI * 2;
            
            // Wind affects hotspot speed
            const windFactor = this.data.weather.windSpeed / 50; // Normalize to 0-1
            this.hotspots.forEach(hotspot => {
                const baseSpeed = 0.001;
                hotspot.vx = (Math.random() - 0.5) * baseSpeed * (1 + windFactor);
                hotspot.vy = (Math.random() - 0.5) * baseSpeed * (1 + windFactor);
            });
        }
    }
    
    stop() {
        // Clean up WebGL resources
        if (this.gl) {
            if (this.vertexBuffer) {
                this.gl.deleteBuffer(this.vertexBuffer);
            }
            if (this.shaderProgram) {
                this.gl.deleteProgram(this.shaderProgram);
            }
        }
        super.stop();
    }
}
