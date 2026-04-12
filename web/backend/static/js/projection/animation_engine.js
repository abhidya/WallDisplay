// Animation Engine - Core framework for projection animations
class AnimationEngine {
    constructor() {
        this.animations = new Map();
        this.animationClasses = new Map();
        this.maskImage = null;
        this.data = {
            weather: null,
            transit: null
        };
        
        // Register built-in animations
        this.registerBuiltInAnimations();
    }
    
    registerBuiltInAnimations() {
        // These will be loaded from individual script files
        if (typeof NeuralNoiseAnimation !== 'undefined') {
            this.animationClasses.set('neural_noise', NeuralNoiseAnimation);
        }
        if (typeof MovingCloudsAnimation !== 'undefined') {
            this.animationClasses.set('moving_clouds', MovingCloudsAnimation);
        }
        if (typeof KoiFishAnimation !== 'undefined') {
            this.animationClasses.set('koi_fish', KoiFishAnimation);
        }
        if (typeof SwimmingFishAnimation !== 'undefined') {
            this.animationClasses.set('swimming_fish', SwimmingFishAnimation);
        }
        if (typeof BlobFishAnimation !== 'undefined') {
            this.animationClasses.set('blob_fish', BlobFishAnimation);
        }
        if (typeof FishPondAnimation !== 'undefined') {
            this.animationClasses.set('fish_pond', FishPondAnimation);
        }
        if (typeof KoiPond8BitAnimation !== 'undefined') {
            this.animationClasses.set('koi_pond_8bit', KoiPond8BitAnimation);
        }
        if (typeof PokedexAnimation !== 'undefined') {
            this.animationClasses.set('pokedex', PokedexAnimation);
        }
        if (typeof MoonViewAnimation !== 'undefined') {
            this.animationClasses.set('moon_view', MoonViewAnimation);
        }
        if (typeof MedusesAnimation !== 'undefined') {
            this.animationClasses.set('meduses', MedusesAnimation);
        }
        if (typeof KelpForestAnimation !== 'undefined') {
            this.animationClasses.set('kelp_forest', KelpForestAnimation);
        }
        if (typeof TrainUpInTheCloudSeaAnimation !== 'undefined') {
            this.animationClasses.set('train_up_in_the_cloud_sea', TrainUpInTheCloudSeaAnimation);
        }
        if (typeof CyberFuji2020Animation !== 'undefined') {
            this.animationClasses.set('cyber_fuji_2020', CyberFuji2020Animation);
        }
        if (typeof WhaleRaymarchingAnimation !== 'undefined') {
            this.animationClasses.set('whale_raymarching', WhaleRaymarchingAnimation);
        }
        if (typeof FractalLandAnimation !== 'undefined') {
            this.animationClasses.set('fractal_land', FractalLandAnimation);
        }
        if (typeof SwarmingAnchovetaAnimation !== 'undefined') {
            this.animationClasses.set('swarming_anchoveta', SwarmingAnchovetaAnimation);
        }
        if (typeof SpectrumBarsAnimation !== 'undefined') {
            this.animationClasses.set('spectrum_bars', SpectrumBarsAnimation);
        }
        if (typeof WebGLFlowersAnimation !== 'undefined') {
            this.animationClasses.set('webgl_flowers', WebGLFlowersAnimation);
        }
        if (typeof RainstormAnimation !== 'undefined') {
            this.animationClasses.set('rainstorm', RainstormAnimation);
        }
        if (typeof PrideSpectrumAnimation !== 'undefined') {
            this.animationClasses.set('pride_spectrum', PrideSpectrumAnimation);
        }

        const importedManifest = window.ImportedShadertoyAnimationsManifest || [];
        importedManifest.forEach((entry) => {
            const AnimationClass = window[entry.className];
            if (AnimationClass) {
                this.animationClasses.set(entry.id, AnimationClass);
            }
        });

        if (typeof StarPsfAnimation !== 'undefined') {
            this.animationClasses.set('star_psf', StarPsfAnimation);
        }
        if (typeof AlienTechAnimation !== 'undefined') {
            this.animationClasses.set('alien_tech', AlienTechAnimation);
        }
        if (typeof MazeAutomataAnimation !== 'undefined') {
            this.animationClasses.set('maze_automata', MazeAutomataAnimation);
        }
        if (typeof PlanetOuterSpaceAnimation !== 'undefined') {
            this.animationClasses.set('planet_outer_space', PlanetOuterSpaceAnimation);
        }
        if (typeof AlienTunnelAnimation !== 'undefined') {
            this.animationClasses.set('alien_tunnel', AlienTunnelAnimation);
        }
        if (typeof AlienWaterworldAnimation !== 'undefined') {
            this.animationClasses.set('alien_waterworld', AlienWaterworldAnimation);
        }
        if (typeof AlienSpaceJockeyAnimation !== 'undefined') {
            this.animationClasses.set('alien_space_jockey', AlienSpaceJockeyAnimation);
        }
        if (typeof AlienCoreAnimation !== 'undefined') {
            this.animationClasses.set('alien_core', AlienCoreAnimation);
        }
        if (typeof VolcanicAnimation !== 'undefined') {
            this.animationClasses.set('volcanic', VolcanicAnimation);
        }
        if (typeof Kepler256oAnimation !== 'undefined') {
            this.animationClasses.set('kepler_256o', Kepler256oAnimation);
        }
        if (typeof NightSkylineBufferedAnimation !== 'undefined') {
            this.animationClasses.set('night_skyline_buffered', NightSkylineBufferedAnimation);
        }
        if (typeof Vaporwave0001Animation !== 'undefined') {
            this.animationClasses.set('vaporwave_0001', Vaporwave0001Animation);
        }
        if (typeof AnimeBackground3Animation !== 'undefined') {
            this.animationClasses.set('anime_background_3', AnimeBackground3Animation);
    }
        }
        if (typeof GridAndLinesAnimation !== 'undefined') {
            this.animationClasses.set('grid_and_lines', GridAndLinesAnimation);
        }
        if (typeof AnimeBackgroundAnimation !== 'undefined') {
            this.animationClasses.set('anime_background', AnimeBackgroundAnimation);
        }            console.warn(`Animation type '${type}' not found`);
            return null;
        }
        
        const animation = new AnimationClass(zone, container, this.maskImage);
        animation.externalClock = true;
        animation.init();
        
        // Store reference
        this.animations.set(zone.id, animation);
        
        // Provide initial data if available
        if (this.data.weather || this.data.transit) {
            animation.updateData(this.data);
        }
        
        return animation;
    }

    renderFrame(timestamp) {
        this.animations.forEach(animation => {
            if (animation?.renderFrame) {
                animation.renderFrame(timestamp);
            }
        });
    }
    
    updateData(data) {
        this.data = { ...this.data, ...data };
        
        // Update all running animations
        this.animations.forEach(animation => {
            animation.updateData(this.data);
        });
    }
    
    destroy() {
        // Stop all animations
        this.animations.forEach(animation => {
            if (animation.stop) {
                animation.stop();
            }
        });
        
        this.animations.clear();
    }
}

// Base Animation Class
class BaseAnimation {
    constructor(zone, container, maskImage) {
        this.zone = zone;
        this.container = container;
        this.maskImage = maskImage;
        this.canvas = null;
        this.ctx = null;
        this.animationId = null;
        this.isRunning = false;
        this.data = {};
        
        // Mask canvas for clipping
        this.maskCanvas = null;
        this.maskCtx = null;
        this.tempCanvas = null;
        this.tempCtx = null;
        this.externalClock = false;
        this.renderElement = null;
    }
    
    init() {
        // Create main canvas
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'animation-canvas';
        this.canvas.width = this.zone.bounds.width;
        this.canvas.height = this.zone.bounds.height;
        this.container.appendChild(this.canvas);
        
        this.ctx = this.canvas.getContext('2d');
        
        // Create mask canvas if mask image is provided
        if (this.maskImage) {
            this.maskCanvas = document.createElement('canvas');
            this.maskCanvas.width = this.zone.bounds.width;
            this.maskCanvas.height = this.zone.bounds.height;
            this.maskCtx = this.maskCanvas.getContext('2d');
            
            // Draw the mask portion for this zone
            this.maskCtx.drawImage(
                this.maskImage,
                this.zone.bounds.x, this.zone.bounds.y,
                this.zone.bounds.width, this.zone.bounds.height,
                0, 0,
                this.zone.bounds.width, this.zone.bounds.height
            );
            
            // Convert black pixels to transparent for proper masking
            const imageData = this.maskCtx.getImageData(0, 0, this.maskCanvas.width, this.maskCanvas.height);
            const data = imageData.data;
            
            for (let i = 0; i < data.length; i += 4) {
                // If pixel is black (or very dark), make it transparent
                if (data[i] < 10 && data[i + 1] < 10 && data[i + 2] < 10) {
                    data[i + 3] = 0; // Set alpha to 0 (transparent)
                }
            }
            
            this.maskCtx.putImageData(imageData, 0, 0);
        }
        
        // Call child class setup
        this.setup();

        if (this.renderElement && this.renderElement !== this.canvas && !this.maskImage) {
            this.renderElement.className = 'animation-canvas';
            this.renderElement.width = this.zone.bounds.width;
            this.renderElement.height = this.zone.bounds.height;
            this.container.appendChild(this.renderElement);
            this.canvas.style.display = 'none';
        }
    }
    
    setup() {
        // Override in child classes
    }
    
    start() {
        if (this.isRunning) return;
        this.isRunning = true;
        if (!this.externalClock) {
            this.animate();
        }
    }
    
    stop() {
        this.isRunning = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }

        if (this.gl) {
            const loseContext = this.gl.getExtension && this.gl.getExtension('WEBGL_lose_context');
            if (loseContext && loseContext.loseContext) {
                loseContext.loseContext();
            }
            this.gl = null;
        }

        if (this.glCanvas) {
            this.glCanvas.width = 1;
            this.glCanvas.height = 1;
            this.glCanvas = null;
        }
    }
    
    animate() {
        if (!this.isRunning) return;
        this.renderFrame(performance.now());

        if (this.externalClock) {
            return;
        }

        // Continue animation
        this.animationId = requestAnimationFrame(() => this.animate());
    }

    renderFrame(_timestamp) {
        if (!this.isRunning) return;

        if (this.renderElement && this.renderElement !== this.canvas && !this.maskCanvas) {
            this.draw();
            return;
        }

        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // If we have a mask, set up clipping
        if (this.maskCanvas) {
            // Save the current state
            this.ctx.save();
            
            // Draw animation to a temporary canvas first
            if (!this.tempCanvas) {
                this.tempCanvas = document.createElement('canvas');
                this.tempCanvas.width = this.canvas.width;
                this.tempCanvas.height = this.canvas.height;
                this.tempCtx = this.tempCanvas.getContext('2d');
            } else if (this.tempCanvas.width !== this.canvas.width || this.tempCanvas.height !== this.canvas.height) {
                this.tempCanvas.width = this.canvas.width;
                this.tempCanvas.height = this.canvas.height;
                this.tempCtx = this.tempCanvas.getContext('2d');
            }
            const tempCtx = this.tempCtx;
            tempCtx.clearRect(0, 0, this.tempCanvas.width, this.tempCanvas.height);
            
            // Store original context and replace with temp
            const originalCtx = this.ctx;
            this.ctx = tempCtx;
            
            // Draw animation to temp canvas
            this.draw();
            
            // Restore original context
            this.ctx = originalCtx;
            
            // Apply the animation to main canvas
            this.ctx.drawImage(this.tempCanvas, 0, 0);
            
            // Apply mask using destination-in composite operation
            this.ctx.globalCompositeOperation = 'destination-in';
            this.ctx.drawImage(this.maskCanvas, 0, 0);
            
            // Restore composite operation
            this.ctx.restore();
        } else {
            // No mask, draw normally
            this.draw();
        }
    }
    
    draw() {
        // Override in child classes
    }
    
    updateData(data) {
        this.data = { ...this.data, ...data };
        this.onDataUpdate();
    }
    
    onDataUpdate() {
        // Override in child classes to respond to data changes
    }
    
    // Utility functions
    getZoneAspectRatio() {
        return this.zone.bounds.width / this.zone.bounds.height;
    }
    
    getZoneArea() {
        return this.zone.area;
    }

    getRenderElement() {
        return this.renderElement || this.canvas;
    }

    // Convert normalized coordinates (0-1) to canvas coordinates
    toCanvasX(normalizedX) {
        return normalizedX * this.canvas.width;
    }
    
    toCanvasY(normalizedY) {
        return normalizedY * this.canvas.height;
    }
}
